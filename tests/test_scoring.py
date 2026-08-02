import dataclasses

from erudit.board import Board
from erudit.config import load_tileset
from erudit.rules import HORIZONTAL, VERTICAL, collect_words, overlay_from_placements
from erudit.scoring import score_move

from tests.test_rules import board_with, placements

TILESET = load_tileset()


def score(board: Board, items, direction, blank_ids=frozenset()):
    overlay = overlay_from_placements(items, blank_ids=blank_ids)
    words = collect_words(board, overlay, direction)
    return score_move(words, TILESET, tiles_used=len(items))


def test_reference_example_doma_is_12():
    # эталон, посчитанный вручную: Д2+О1+М2+А1 = 6, центр удваивает слово
    board = Board(15)
    items = placements((7, 7, "Д"), (7, 8, "О"), (7, 9, "М"), (7, 10, "А"))
    total, per_word = score(board, items, HORIZONTAL)
    assert per_word == [("ДОМА", 12)]
    assert total == 12


def test_letter_multiplier_applies_to_one_letter_only():
    # (7,11) — удвоение буквы: К=2 превращается в 4
    board = board_with((7, 7, HORIZONTAL, "ДОМА"))
    items = placements((7, 11, "К"))
    total, per_word = score(board, items, HORIZONTAL)
    assert per_word == [("ДОМАК", 2 + 1 + 2 + 1 + 2 * 2)]
    assert total == 10


def test_two_word_multipliers_are_multiplied():
    # строка 4: удвоение слова в столбцах 4 и 10 — слово через оба даёт ×4
    board = Board(15)
    items = placements(*[(4, c, "А") for c in range(4, 11)])
    total, _ = score(board, items, HORIZONTAL)
    assert total == 7 * 2 * 2


def test_center_bonus_does_not_apply_twice():
    # второй ход проходит через центр, но клетка уже закрыта — множителя нет
    board = board_with((7, 7, HORIZONTAL, "ДОМА"))
    items = placements((6, 7, "К"), (8, 7, "Т"))
    total, per_word = score(board, items, VERTICAL)
    assert per_word == [("КДТ", 2 + 2 + 1)]
    assert total == 5


def test_new_cell_bonus_counts_in_both_words():
    # (8,8) — удвоение буквы; С=1 удваивается и в главном, и в перпендикулярном
    board = board_with((7, 7, HORIZONTAL, "КОТ"))
    items = placements((8, 8, "С"), (8, 9, "Ы"))
    total, per_word = score(board, items, HORIZONTAL)
    assert dict(per_word)["СЫ"] == 1 * 2 + 4
    assert dict(per_word)["ОС"] == 1 + 1 * 2
    assert total == 6 + 3 + dict(per_word)["ТЫ"]


def test_blank_scores_zero_but_keeps_word_multiplier():
    board = Board(15)
    items = placements((7, 7, "Д"), (7, 8, "О"), (7, 9, "М"), (7, 10, "А"))
    # пустышка на месте Д (tile_id 0), центр по-прежнему удваивает слово
    total, per_word = score(board, items, HORIZONTAL, blank_ids=frozenset({0}))
    assert per_word == [("ДОМА", (0 + 1 + 2 + 1) * 2)]
    assert total == 8


def test_blank_ignores_letter_multiplier():
    board = board_with((7, 7, HORIZONTAL, "ДОМА"))
    items = placements((7, 11, "К"))  # клетка удвоения буквы
    total, _ = score(board, items, HORIZONTAL, blank_ids=frozenset({0}))
    assert total == 2 + 1 + 2 + 1 + 0


def test_move_total_sums_all_words():
    board = board_with((7, 7, HORIZONTAL, "КОТ"))
    items = placements((8, 7, "О"), (8, 8, "С"), (8, 9, "Ы"))
    total, per_word = score(board, items, HORIZONTAL)
    assert total == sum(points for _, points in per_word)
    assert len(per_word) == 4


def test_bingo_bonus_added_after_multipliers():
    tileset = dataclasses.replace(TILESET, bingo_bonus=50)
    board = Board(15)
    items = placements(*[(7, 7 + i, "А") for i in range(7)])
    overlay = overlay_from_placements(items)
    words = collect_words(board, overlay, HORIZONTAL)
    total, _ = score_move(words, tileset, tiles_used=7)
    # 7 фишек по 1 очку, из них одна на удвоении буквы (7,11): 8, центр ×2 = 16
    assert total == 16 + 50


def test_bingo_bonus_not_added_for_fewer_tiles():
    tileset = dataclasses.replace(TILESET, bingo_bonus=50)
    board = Board(15)
    items = placements(*[(7, 7 + i, "А") for i in range(6)])
    overlay = overlay_from_placements(items)
    words = collect_words(board, overlay, HORIZONTAL)
    total, _ = score_move(words, tileset, tiles_used=6)
    assert total == 14
