import random

import pytest

from erudit.config import load_tileset
from erudit.game import MAX_PASS_STREAK, Game
from erudit.rules import MoveError, Placement
from erudit.tiles import Tile

TILESET = load_tileset()
WORDS = {"ДОМ", "ДОМА", "ДОМЫ", "КОТ", "КОТЫ", "ОСЫ", "ОС", "ТЫ", "КО", "МЫ", "ОМ", "ДО", "АД"}


def new_game(seed: int = 1, dictionary=None) -> Game:
    game = Game("test1234", TILESET, dictionary or set(WORDS), random.Random(seed))
    game.add_player("Первый")
    game.add_player("Второй")
    game.start()
    return game


def set_rack(game: Game, player_id: str, letters: str) -> list[Tile]:
    """Подменяет стойку на нужные буквы, чтобы тест не зависел от раздачи."""
    player = game.player_by_id(player_id)
    rack = [
        Tile(id=900 + i, letter=(None if ch == "?" else ch), value=(0 if ch == "?" else TILESET.value_of(ch)))
        for i, ch in enumerate(letters)
    ]
    player.rack = rack
    return rack


def place(rack: list[Tile], word: str, row: int, col: int, horizontal: bool = True):
    """Собирает размещения из фишек стойки по буквам слова."""
    available = list(rack)
    items = []
    for i, letter in enumerate(word):
        tile = next(t for t in available if t.letter == letter)
        available.remove(tile)
        items.append(
            Placement(
                row=row + (0 if horizontal else i),
                col=col + (i if horizontal else 0),
                tile_id=tile.id,
                letter=letter,
            )
        )
    return items


def snapshot(game: Game):
    return (
        [[cell for cell in row] for row in game.board._cells],
        {p.id: (list(p.rack), p.score) for p in game.players},
        game.current,
        game.move_no,
    )


# --- очередь и проверки -------------------------------------------------------


def test_first_player_moves_first():
    game = new_game()
    assert game.current_player.id == "p1"


def test_move_out_of_turn_rejected():
    game = new_game()
    rack = set_rack(game, "p2", "ДОМАКОТ")
    with pytest.raises(MoveError, match="не ваш ход"):
        game.play("p2", place(rack, "ДОМ", 7, 7))


def test_move_with_tiles_not_on_rack_rejected():
    game = new_game()
    set_rack(game, "p1", "ДОМАКОТ")
    with pytest.raises(MoveError, match="нет на вашей стойке"):
        game.play("p1", [Placement(7, 7, 12345, "Д")])


def test_letter_must_match_the_tile():
    game = new_game()
    rack = set_rack(game, "p1", "ДОМАКОТ")
    items = place(rack, "ДОМ", 7, 7)
    items[0] = Placement(items[0].row, items[0].col, items[0].tile_id, "К")
    with pytest.raises(MoveError, match="не совпадает"):
        game.play("p1", items)


def test_rejected_move_changes_nothing():
    game = new_game()
    rack = set_rack(game, "p1", "ДОМАКОТ")
    before = snapshot(game)
    with pytest.raises(MoveError):
        game.play("p1", place(rack, "ДОМ", 0, 0))  # мимо центра
    assert snapshot(game) == before


def test_unknown_word_is_reported_with_the_word_list():
    game = new_game()
    rack = set_rack(game, "p1", "ДОМАКОТ")
    with pytest.raises(MoveError) as exc:
        game.play("p1", place(rack, "ТОК", 7, 7))
    assert exc.value.unknown_words == ("ТОК",)
    assert game.board.is_empty()


# --- удачный ход --------------------------------------------------------------


def test_successful_move_scores_and_refills_rack():
    game = new_game()
    rack = set_rack(game, "p1", "ДОМАКОТ")
    result = game.play("p1", place(rack, "ДОМ", 7, 7))
    assert result.total == 10  # Д2+О1+М2 = 5, центр ×2
    player = game.player_by_id("p1")
    assert player.score == 10
    assert len(player.rack) == TILESET.rack_size
    assert game.current_player.id == "p2"
    assert game.pass_streak == 0


def test_move_writes_a_log_entry():
    game = new_game()
    rack = set_rack(game, "p1", "ДОМАКОТ")
    game.play("p1", place(rack, "ДОМ", 7, 7))
    entry = game.log[-1]
    assert entry["type"] == "move"
    assert entry["player"] == "p1"
    assert entry["words"] == [["ДОМ", 10]]


def test_blank_takes_the_chosen_letter():
    game = new_game()
    rack = set_rack(game, "p1", "?ОМАКОТ")
    items = [
        Placement(7, 7, rack[0].id, "Д"),
        Placement(7, 8, rack[1].id, "О"),
        Placement(7, 9, rack[2].id, "М"),
    ]
    result = game.play("p1", items)
    assert result.total == (0 + 1 + 2) * 2
    placed = game.board.get(7, 7)
    assert placed.letter == "Д" and placed.is_blank


def test_preview_does_not_change_state():
    game = new_game()
    rack = set_rack(game, "p1", "ДОМАКОТ")
    before = snapshot(game)
    preview = game.preview("p1", place(rack, "ДОМ", 7, 7))
    assert preview.valid and preview.total == 10
    assert preview.words == (("ДОМ", 10),)
    assert snapshot(game) == before


def test_preview_reports_unknown_words():
    game = new_game()
    rack = set_rack(game, "p1", "ДОМАКОТ")
    preview = game.preview("p1", place(rack, "ТОК", 7, 7))
    assert not preview.valid
    assert preview.unknown_words == ("ТОК",)


def test_rack_is_not_refilled_from_empty_bag():
    game = new_game()
    rack = set_rack(game, "p1", "ДОМАКОТ")
    game.bag.draw(len(game.bag))
    game.play("p1", place(rack, "ДОМ", 7, 7))
    assert len(game.player_by_id("p1").rack) == 4


# --- пас и обмен ---------------------------------------------------------------


def test_pass_moves_the_turn_and_counts():
    game = new_game()
    game.do_pass("p1")
    assert game.current_player.id == "p2"
    assert game.pass_streak == 1


def test_six_passes_finish_the_game():
    game = new_game()
    for i in range(MAX_PASS_STREAK):
        game.do_pass(game.current_player.id)
    assert game.status == "finished"
    assert game.pass_streak == MAX_PASS_STREAK


def test_exchange_swaps_tiles_and_loses_the_turn():
    game = new_game()
    player = game.player_by_id("p1")
    ids = [tile.id for tile in player.rack[:3]]
    before = len(game.bag)
    game.exchange("p1", ids)
    assert len(player.rack) == TILESET.rack_size
    assert len(game.bag) == before
    assert game.current_player.id == "p2"
    assert game.pass_streak == 1


def test_exchange_cannot_return_the_same_tiles():
    game = new_game()
    player = game.player_by_id("p1")
    ids = [tile.id for tile in player.rack]
    game.exchange("p1", ids)
    assert not ({tile.id for tile in player.rack} & set(ids))


def test_exchange_rejected_when_bag_is_almost_empty():
    game = new_game()
    game.bag.draw(len(game.bag) - 3)
    player = game.player_by_id("p1")
    with pytest.raises(MoveError, match="мало фишек"):
        game.exchange("p1", [player.rack[0].id])


def test_exchange_of_foreign_tiles_rejected():
    game = new_game()
    with pytest.raises(MoveError, match="нет на вашей стойке"):
        game.exchange("p1", [12345])


# --- конец партии ---------------------------------------------------------------


def test_going_out_gives_opponent_remainder():
    game = new_game()
    rack = set_rack(game, "p1", "ДОМ")
    set_rack(game, "p2", "ЪЩ")  # 10 + 10
    game.bag.draw(len(game.bag))
    result = game.play("p1", place(rack, "ДОМ", 7, 7))
    assert result.finished
    assert game.status == "finished"
    assert game.player_by_id("p1").score == 10 + 20
    assert game.player_by_id("p2").score == -20


def test_six_passes_subtract_remainders_from_everyone():
    game = new_game()
    set_rack(game, "p1", "Ъ")
    set_rack(game, "p2", "Щ")
    for _ in range(MAX_PASS_STREAK):
        game.do_pass(game.current_player.id)
    assert game.player_by_id("p1").score == -10
    assert game.player_by_id("p2").score == -10


def test_no_moves_after_the_game_is_finished():
    game = new_game()
    for _ in range(MAX_PASS_STREAK):
        game.do_pass(game.current_player.id)
    with pytest.raises(MoveError, match="не идёт"):
        game.do_pass("p1")


def test_winners():
    game = new_game()
    game.player_by_id("p1").score = 30
    game.player_by_id("p2").score = 12
    assert [p.id for p in game.winners()] == ["p1"]


def test_full_two_player_game_reaches_finished():
    game = new_game()
    rack1 = set_rack(game, "p1", "ДОМАКОТ")
    game.play("p1", place(rack1, "ДОМ", 7, 7))

    # ОСЫ вниз от буквы О, уже стоящей на (7,8)
    rack2 = set_rack(game, "p2", "СЫАБВГД")
    game.play("p2", [Placement(8, 8, rack2[0].id, "С"), Placement(9, 8, rack2[1].id, "Ы")])
    assert game.board.get(9, 8).letter == "Ы"
    assert game.player_by_id("p2").score > 0

    # мешок пуст, у первого осталась одна фишка — он выходит и партия кончается
    game.bag.draw(len(game.bag))
    last = set_rack(game, "p1", "Ы")
    game.play("p1", [Placement(7, 10, last[0].id, "Ы")])
    assert game.status == "finished"
    assert not game.player_by_id("p1").rack
    assert game.log[-1]["type"] == "finish"
