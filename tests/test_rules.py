import pytest

from erudit.board import Board, PlacedTile
from erudit.rules import (
    HORIZONTAL,
    VERTICAL,
    MoveError,
    Placement,
    collect_words,
    overlay_from_placements,
    validate_geometry,
)

CENTER = (7, 7)


def board_with(*words: tuple[int, int, str, str]) -> Board:
    """Доска с уже выложенными словами: (row, col, направление, буквы)."""
    board = Board(15)
    for row, col, direction, letters in words:
        for i, letter in enumerate(letters):
            r = row + (i if direction == VERTICAL else 0)
            c = col + (i if direction == HORIZONTAL else 0)
            board.put(r, c, PlacedTile(1000 + r * 15 + c, letter, False, "p1", 1))
    return board


def placements(*items: tuple[int, int, str]) -> list[Placement]:
    return [
        Placement(row=r, col=c, tile_id=i, letter=letter)
        for i, (r, c, letter) in enumerate(items)
    ]


def words_for(board: Board, items: list[Placement], direction) -> list[str]:
    return [w.text for w in collect_words(board, overlay_from_placements(items), direction)]


# --- геометрия ---------------------------------------------------------------


def test_empty_placement_rejected():
    with pytest.raises(MoveError):
        validate_geometry(Board(15), [], CENTER)


def test_first_move_must_cover_center():
    with pytest.raises(MoveError, match="центральную"):
        validate_geometry(Board(15), placements((0, 0, "Д"), (0, 1, "О")), CENTER)


def test_first_move_over_center_accepted():
    assert validate_geometry(Board(15), placements((7, 6, "Д"), (7, 7, "О")), CENTER) == HORIZONTAL


def test_move_must_touch_existing_tiles():
    board = board_with((7, 7, HORIZONTAL, "ДОМ"))
    with pytest.raises(MoveError, match="касаться"):
        validate_geometry(board, placements((0, 0, "К"), (0, 1, "О")), CENTER)


def test_touching_move_accepted():
    board = board_with((7, 7, HORIZONTAL, "ДОМ"))
    assert validate_geometry(board, placements((8, 7, "У"), (9, 7, "Б")), CENTER) == VERTICAL


def test_diagonal_move_rejected():
    board = board_with((7, 7, HORIZONTAL, "ДОМ"))
    with pytest.raises(MoveError, match="одной строке"):
        validate_geometry(board, placements((8, 7, "У"), (9, 8, "Б")), CENTER)


def test_gap_rejected():
    board = board_with((7, 7, HORIZONTAL, "ДОМ"))
    with pytest.raises(MoveError, match="разрыв"):
        validate_geometry(board, placements((8, 7, "У"), (10, 7, "Б")), CENTER)


def test_gap_closed_by_existing_tile_accepted():
    # столбец 7: строка 7 — Д (старая), 8 — пусто, 9 — Р (старая)
    board = board_with((7, 7, HORIZONTAL, "ДОМ"), (9, 7, HORIZONTAL, "РОТ"))
    assert validate_geometry(board, placements((6, 7, "У"), (8, 7, "А")), CENTER) == VERTICAL


def test_occupied_cell_rejected():
    board = board_with((7, 7, HORIZONTAL, "ДОМ"))
    with pytest.raises(MoveError, match="занята"):
        validate_geometry(board, placements((7, 8, "У")), CENTER)


def test_out_of_bounds_rejected():
    with pytest.raises(MoveError, match="вне доски"):
        validate_geometry(Board(15), placements((7, 15, "У")), CENTER)


def test_two_tiles_in_one_cell_rejected():
    with pytest.raises(MoveError, match="одной клетке"):
        validate_geometry(Board(15), placements((7, 7, "У"), (7, 7, "Б")), CENTER)


def test_same_tile_twice_rejected():
    items = [Placement(7, 7, 1, "У"), Placement(7, 8, 1, "Б")]
    with pytest.raises(MoveError, match="дважды"):
        validate_geometry(Board(15), items, CENTER)


# --- сбор слов ---------------------------------------------------------------


def test_single_word_on_empty_board():
    board = Board(15)
    items = placements((7, 7, "Д"), (7, 8, "О"), (7, 9, "М"))
    assert words_for(board, items, HORIZONTAL) == ["ДОМ"]


def test_one_tile_completing_word_vertically():
    board = board_with((7, 7, VERTICAL, "ОМ"))
    items = placements((6, 7, "Д"))
    direction = validate_geometry(board, items, CENTER)
    assert words_for(board, items, direction) == ["ДОМ"]


def test_one_tile_at_crossing_gives_two_words():
    #   столбец 7: ОМ вниз от (7,7);  строка 6: О_ — новая Д на (6,7) даёт ДОМ и ДО
    board = board_with((7, 7, VERTICAL, "ОМ"), (6, 8, HORIZONTAL, "О"))
    items = placements((6, 7, "Д"))
    direction = validate_geometry(board, items, CENTER)
    assert sorted(words_for(board, items, direction)) == ["ДО", "ДОМ"]


def test_perpendicular_words_are_collected():
    # горизонтальное КОТ, ход вниз от каждой буквы даёт перпендикулярные слова
    board = board_with((7, 7, HORIZONTAL, "КОТ"))
    items = placements((8, 7, "О"), (8, 8, "С"), (8, 9, "Ы"))
    direction = validate_geometry(board, items, CENTER)
    assert sorted(words_for(board, items, direction)) == ["КО", "ОС", "ОСЫ", "ТЫ"]


def test_word_extended_on_both_sides():
    board = board_with((7, 7, HORIZONTAL, "ОМ"))
    items = placements((7, 6, "Д"), (7, 9, "А"))
    direction = validate_geometry(board, items, CENTER)
    assert words_for(board, items, direction) == ["ДОМА"]


def test_single_letter_sequences_are_not_words():
    board = Board(15)
    items = placements((7, 7, "Д"), (7, 8, "О"))
    overlay = overlay_from_placements(items)
    words = collect_words(board, overlay, HORIZONTAL)
    assert [w.text for w in words] == ["ДО"]


def test_new_cells_are_marked():
    board = board_with((7, 7, VERTICAL, "ОМ"))
    items = placements((6, 7, "Д"))
    words = collect_words(board, overlay_from_placements(items), VERTICAL)
    assert [(c.letter, c.is_new) for c in words[0].cells] == [
        ("Д", True),
        ("О", False),
        ("М", False),
    ]


def test_blank_is_marked_in_word():
    board = Board(15)
    items = placements((7, 7, "Д"), (7, 8, "О"))
    overlay = overlay_from_placements(items, blank_ids=frozenset({1}))
    words = collect_words(board, overlay, HORIZONTAL)
    assert [c.is_blank for c in words[0].cells] == [False, True]
