"""Итоги партии считаются по журналу — проверяем на настоящих ходах и на
подготовленном журнале, где проще собрать редкие случаи вроде бинго."""

from erudit.stats import summarize
from tests.test_game_flow import new_game, place, set_rack


def by_id(summary):
    return {item["id"]: item for item in summary["players"]}


def test_real_moves_are_counted():
    game = new_game()
    first = game.play("p1", place(set_rack(game, "p1", "ДОМКОТЫ"), "ДОМ", 7, 6))
    second = game.play("p2", place(set_rack(game, "p2", "АКОТЫСД"), "А", 7, 9))
    game.do_pass("p1")

    stats = by_id(summarize(game))
    assert stats["p1"]["moves"] == 1 and stats["p1"]["passes"] == 1
    assert stats["p1"]["best"] == {"words": ["ДОМ"], "score": first.total}
    assert stats["p2"]["longest"] == "ДОМА"
    assert stats["p2"]["average"] == second.total


def test_move_log_records_how_many_tiles_were_used():
    game = new_game()
    game.play("p1", place(set_rack(game, "p1", "ДОМКОТЫ"), "ДОМ", 7, 6))
    assert game.log[-1]["tiles"] == 3


def test_timeline_starts_at_zero_and_ends_with_final_scores():
    game = new_game()
    game.play("p1", place(set_rack(game, "p1", "ДОМКОТЫ"), "ДОМ", 7, 6))
    game.do_pass("p2")
    timeline = summarize(game)["timeline"]
    assert timeline[0] == [0, 0]
    assert timeline[-1] == [game.players[0].score, game.players[1].score]
    assert len(timeline) == 3


def test_handmade_log_bingo_average_and_penalty_point():
    game = new_game()
    game.log = [
        {"type": "start", "player": None, "text": ""},
        {"type": "move", "player": "p1", "text": "", "words": [["КОТ", 5]], "score": 5, "tiles": 3},
        {"type": "move", "player": "p2", "text": "", "words": [["СОБАКАМИ", 70]], "score": 70, "tiles": 7},
        {"type": "exchange", "player": "p1", "text": "", "count": 2},
        {"type": "move", "player": "p2", "text": "", "words": [["ОСА", 4], ["ОС", 2]], "score": 6, "tiles": 1},
        {"type": "finish", "player": "p2", "text": ""},
    ]
    game.players[0].score = 5 - 3
    game.players[1].score = 76 + 3
    game.status = "finished"

    summary = summarize(game)
    stats = by_id(summary)
    assert stats["p2"]["bingos"] == 1
    assert stats["p2"]["average"] == 38.0
    assert stats["p2"]["best"] == {"words": ["СОБАКАМИ"], "score": 70}
    assert stats["p1"]["exchanges"] == 1
    # после ходов 5:76, итог со штрафами — отдельной точкой
    assert summary["timeline"][-2:] == [[5, 76], [2, 79]]


def test_player_without_moves():
    game = new_game()
    stats = by_id(summarize(game))
    assert stats["p1"]["moves"] == 0
    assert stats["p1"]["average"] == 0
    assert stats["p1"]["best"] is None and stats["p1"]["longest"] is None
