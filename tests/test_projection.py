"""Проекция — единственное место, где решается, что игрок вправе видеть.

Поэтому приватность проверяется здесь, а не размазана по тестам сервера.
"""

import random

from erudit.game import Game
from erudit.projection import for_player


def make_game(tileset, dictionary):
    game = Game("abcdef1234", tileset, dictionary, random.Random(7))
    game.add_player("Первый")
    game.add_player("Второй")
    game.start()
    return game


def test_own_rack_is_visible_in_full(tileset, dictionary):
    game = make_game(tileset, dictionary)
    state = for_player(game, "p1")
    assert [t["id"] for t in state["rack"]] == [t.id for t in game.players[0].rack]


def test_opponent_rack_is_only_a_count(tileset, dictionary):
    game = make_game(tileset, dictionary)
    state = for_player(game, "p1")
    opponent = next(p for p in state["players"] if p["id"] == "p2")
    assert opponent["tiles"] == 7
    assert set(opponent) == {"id", "name", "score", "tiles", "connected", "is_you"}


def test_bag_is_only_a_count(tileset, dictionary):
    game = make_game(tileset, dictionary)
    state = for_player(game, "p1")
    assert state["bag"] == 90


def test_no_token_ever_leaks(tileset, dictionary):
    game = make_game(tileset, dictionary)
    payload = repr([for_player(game, "p1"), for_player(game, "p2")])
    for player in game.players:
        assert player.token not in payload


def test_no_opponent_tile_ids_leak(tileset, dictionary):
    game = make_game(tileset, dictionary)
    state = for_player(game, "p1")
    mine = {t.id for t in game.players[0].rack}
    theirs = {t.id for t in game.players[1].rack}
    seen = {t["id"] for t in state["rack"]}
    assert seen == mine
    assert not (seen & theirs)


def test_spectator_without_player_id_sees_no_rack(tileset, dictionary):
    game = make_game(tileset, dictionary)
    state = for_player(game, "нет такого")
    assert state["rack"] == []
    assert all(not p["is_you"] for p in state["players"])
