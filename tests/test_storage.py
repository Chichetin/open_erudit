import json
import random
import time

from fastapi.testclient import TestClient

from app.main import create_app
from app.sessions import GameRegistry
from erudit import storage
from erudit.game import Game
from erudit.rules import Placement

from tests.test_game_flow import place, set_rack
from tests.test_ws import hello, recv, word_placements


def make_game(tileset, dictionary):
    game = Game("abcdef1234", tileset, dictionary, random.Random(5))
    game.add_player("Первый")
    game.add_player("Второй")
    game.start()
    return game


def test_roundtrip_preserves_everything(tileset, dictionary, tmp_path):
    game = make_game(tileset, dictionary)
    rack = set_rack(game, "p1", "ДОМАКОТ")
    game.play("p1", place(rack, "ДОМ", 7, 7))

    storage.save(game, tmp_path)
    restored = storage.load_all(tmp_path, tileset, dictionary)["abcdef1234"]

    assert restored.status == game.status
    assert restored.current == game.current
    assert restored.move_no == game.move_no
    assert restored.pass_streak == game.pass_streak
    assert restored.log == game.log
    assert len(restored.bag) == len(game.bag)
    assert [(p.id, p.name, p.token, p.score) for p in restored.players] == [
        (p.id, p.name, p.token, p.score) for p in game.players
    ]
    assert [t.id for t in restored.players[0].rack] == [
        t.id for t in game.players[0].rack
    ]
    placed = restored.board.get(7, 7)
    assert (placed.letter, placed.player_id, placed.move_no) == ("Д", "p1", 1)


def test_restored_game_can_be_played_on(tileset, dictionary, tmp_path):
    game = make_game(tileset, dictionary)
    rack = set_rack(game, "p1", "ДОМАКОТ")
    game.play("p1", place(rack, "ДОМ", 7, 7))
    storage.save(game, tmp_path)

    restored = storage.load_all(tmp_path, tileset, dictionary)["abcdef1234"]
    rack2 = set_rack(restored, "p2", "СЫАБВГД")
    result = restored.play(
        "p2", [Placement(8, 8, rack2[0].id, "С"), Placement(9, 8, rack2[1].id, "Ы")]
    )
    assert result.total > 0


def test_blank_keeps_its_letter_after_reload(tileset, dictionary, tmp_path):
    game = make_game(tileset, dictionary)
    rack = set_rack(game, "p1", "?ОМАКОТ")
    game.play(
        "p1",
        [
            Placement(7, 7, rack[0].id, "Д"),
            Placement(7, 8, rack[1].id, "О"),
            Placement(7, 9, rack[2].id, "М"),
        ],
    )
    storage.save(game, tmp_path)
    restored = storage.load_all(tmp_path, tileset, dictionary)["abcdef1234"]
    cell = restored.board.get(7, 7)
    assert cell.letter == "Д" and cell.is_blank


def test_save_is_atomic_and_leaves_no_temp_files(tileset, dictionary, tmp_path):
    game = make_game(tileset, dictionary)
    storage.save(game, tmp_path)
    assert (tmp_path / "abcdef1234.json").exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_broken_snapshot_is_skipped_not_fatal(tileset, dictionary, tmp_path):
    (tmp_path / "broken1234.json").write_text("{ это не json", encoding="utf-8")
    game = make_game(tileset, dictionary)
    storage.save(game, tmp_path)
    assert set(storage.load_all(tmp_path, tileset, dictionary)) == {"abcdef1234"}


def test_snapshot_of_another_version_is_skipped(tileset, dictionary, tmp_path):
    game = make_game(tileset, dictionary)
    path = storage.save(game, tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = 999
    path.write_text(json.dumps(data), encoding="utf-8")
    assert storage.load_all(tmp_path, tileset, dictionary) == {}


def test_prune_removes_old_finished_games_only(tileset, dictionary, tmp_path):
    active = make_game(tileset, dictionary)
    storage.save(active, tmp_path)

    finished = make_game(tileset, dictionary)
    finished.id = "finished99"
    finished.status = "finished"
    old = storage.save(finished, tmp_path)
    stale = time.time() - 8 * 24 * 3600
    import os

    os.utime(old, (stale, stale))
    os.utime(tmp_path / "abcdef1234.json", (stale, stale))

    assert storage.prune_finished(tmp_path) == 1
    assert not old.exists()
    assert (tmp_path / "abcdef1234.json").exists()


# --- сервер ---------------------------------------------------------------------


def test_game_survives_server_restart(tileset, dictionary, tmp_path):
    first_registry = GameRegistry(tileset, dictionary, games_dir=tmp_path)
    client = TestClient(create_app(first_registry))
    game_id = client.post("/games").json()["game_id"]
    game = first_registry.get(game_id)
    token = game.players[0].token
    rack = set_rack(game, "p1", "ДОМАКОТ")

    with client.websocket_connect(f"/g/{game_id}/ws") as socket:
        hello(socket, token)
        socket.send_json({"type": "commit", "placements": word_placements(rack, "ДОМ", 7, 7)})
        recv(socket, "state")

    # «перезапуск»: новый реестр из той же папки снапшотов
    second_registry = GameRegistry(tileset, dictionary, games_dir=tmp_path)
    second_registry.restore()
    restarted = TestClient(create_app(second_registry))

    with restarted.websocket_connect(f"/g/{game_id}/ws") as socket:
        state = hello(socket, token)

    assert state["board"][7][7]["letter"] == "Д"
    assert next(p for p in state["players"] if p["id"] == "p1")["score"] == 10
    assert state["current"] == "p2"


def test_snapshot_is_written_after_every_move(tileset, dictionary, tmp_path):
    registry = GameRegistry(tileset, dictionary, games_dir=tmp_path)
    client = TestClient(create_app(registry))
    game_id = client.post("/games").json()["game_id"]
    game = registry.get(game_id)
    snapshot = tmp_path / f"{game_id}.json"
    assert snapshot.exists()

    with client.websocket_connect(f"/g/{game_id}/ws") as socket:
        hello(socket, game.players[0].token)
        socket.send_json({"type": "pass"})
        recv(socket, "state")

    assert json.loads(snapshot.read_text(encoding="utf-8"))["pass_streak"] == 1
