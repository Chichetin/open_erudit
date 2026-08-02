import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app
from app.sessions import GameRegistry


@pytest.fixture
def registry(tileset, dictionary, tmp_path):
    return GameRegistry(tileset, dictionary, games_dir=tmp_path)


@pytest.fixture
def client(registry):
    return TestClient(create_app(registry))


@pytest.fixture
def game(registry):
    return registry.create()


def hello(socket, token):
    socket.send_json({"type": "hello", "token": token})
    state = recv(socket, "state")
    recv(socket, "presence")  # рассылка о собственном подключении
    return state


def recv(socket, kind):
    """Ждёт сообщение нужного типа, пропуская остальные."""
    for _ in range(20):
        message = socket.receive_json()
        if message["type"] == kind:
            return message
    raise AssertionError(f"не дождались сообщения {kind}")


def set_rack(game, player_id, letters):
    from tests.test_game_flow import set_rack as engine_set_rack

    return engine_set_rack(game, player_id, letters)


def word_placements(rack, word, row, col):
    available = list(rack)
    items = []
    for i, letter in enumerate(word):
        tile = next(t for t in available if t.letter == letter)
        available.remove(tile)
        items.append({"row": row, "col": col + i, "tile_id": tile.id, "letter": letter})
    return items


# --- авторизация ---------------------------------------------------------------


def test_first_message_must_be_hello(client, game):
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        socket.send_json({"type": "pass"})
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_foreign_token_rejected(client, game):
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        socket.send_json({"type": "hello", "token": "чужой"})
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_garbage_first_message_rejected(client, game):
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        socket.send_text("не json")
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_unknown_game_id_rejected(client):
    with client.websocket_connect("/g/deadbeef99/ws") as socket:
        socket.send_json({"type": "hello", "token": "любой"})
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


# --- приватность ----------------------------------------------------------------


def test_state_hides_opponent_rack_and_tokens(client, game):
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        state = hello(socket, game.players[0].token)

    assert state["you"] == "p1"
    assert len(state["rack"]) == 7
    opponent = next(p for p in state["players"] if p["id"] == "p2")
    assert opponent["tiles"] == 7
    assert "rack" not in opponent

    payload = repr(state)
    for player in game.players:
        assert player.token not in payload


def test_state_hides_bag_contents(client, game):
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        state = hello(socket, game.players[0].token)
    assert state["bag"] == 104 - 14
    assert isinstance(state["bag"], int)


# --- ход ------------------------------------------------------------------------


def test_move_out_of_turn_is_rejected_and_changes_nothing(client, game):
    rack = set_rack(game, "p2", "ДОМАКОТ")
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        hello(socket, game.players[1].token)
        socket.send_json({"type": "commit", "placements": word_placements(rack, "ДОМ", 7, 7)})
        error = recv(socket, "error")
    assert "не ваш ход" in error["message"]
    assert game.board.is_empty()
    assert game.player_by_id("p2").score == 0


def test_both_clients_get_new_state_after_a_move(client, game):
    rack = set_rack(game, "p1", "ДОМАКОТ")
    with client.websocket_connect(f"/g/{game.id}/ws") as first:
        hello(first, game.players[0].token)
        with client.websocket_connect(f"/g/{game.id}/ws") as second:
            hello(second, game.players[1].token)

            first.send_json(
                {"type": "commit", "placements": word_placements(rack, "ДОМ", 7, 7)}
            )
            state_one = recv(first, "state")
            state_two = recv(second, "state")

    assert state_one["board"][7][7]["letter"] == "Д"
    assert state_two["board"][7][7]["letter"] == "Д"
    assert state_one["current"] == "p2"
    assert next(p for p in state_two["players"] if p["id"] == "p1")["score"] == 10
    assert state_two["board"][7][7]["is_last"]


def test_draft_returns_preview_without_changing_state(client, game):
    rack = set_rack(game, "p1", "ДОМАКОТ")
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        hello(socket, game.players[0].token)
        socket.send_json({"type": "draft", "placements": word_placements(rack, "ДОМ", 7, 7)})
        preview = recv(socket, "preview")
    assert preview["valid"] and preview["total"] == 10
    assert preview["words"] == [["ДОМ", 10]]
    assert game.board.is_empty()


def test_draft_reports_unknown_word(client, game):
    rack = set_rack(game, "p1", "ЗАМОКИ")
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        hello(socket, game.players[0].token)
        socket.send_json({"type": "draft", "placements": word_placements(rack, "ЗАМОК", 7, 7)})
        preview = recv(socket, "preview")
    assert not preview["valid"]
    assert preview["unknown_words"] == ["ЗАМОК"]


def test_allow_word_makes_the_move_possible(client, game):
    rack = set_rack(game, "p1", "ЗАМОКИ")
    placements = word_placements(rack, "ЗАМОК", 7, 7)
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        hello(socket, game.players[0].token)
        socket.send_json({"type": "allow_word", "word": "замок"})
        recv(socket, "state")
        socket.send_json({"type": "commit", "placements": placements})
        state = recv(socket, "state")
    assert state["board"][7][7]["letter"] == "З"


def test_pass_and_exchange(client, game):
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        hello(socket, game.players[0].token)
        socket.send_json({"type": "pass"})
        state = recv(socket, "state")
        assert state["current"] == "p2"
        assert state["pass_streak"] == 1

        game.current = 0  # вернём ход первому, чтобы проверить обмен
        ids = [tile.id for tile in game.player_by_id("p1").rack[:2]]
        socket.send_json({"type": "exchange", "tile_ids": ids})
        state = recv(socket, "state")
        assert state["pass_streak"] == 2
        assert len(state["rack"]) == 7


def test_journal_arrives_inside_state(client, game):
    # отдельного сообщения на запись журнала нет: журнал целиком лежит в state
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        hello(socket, game.players[0].token)
        socket.send_json({"type": "pass"})
        state = recv(socket, "state")
    assert [entry["type"] for entry in state["log"]] == ["start", "pass"]


# --- мусор от клиента -------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        {"type": "commit", "placements": "не список"},
        {"type": "commit", "placements": [{"row": 0}]},
        {"type": "commit", "placements": [{"row": 0, "col": 0, "tile_id": 1, "letter": "ДОМ"}]},
        {"type": "exchange", "tile_ids": ["не число"]},
        {"type": "allow_word", "word": "!!!"},
        {"type": "чего-то новенькое"},
    ],
)
def test_garbage_messages_get_an_error_not_a_crash(client, game, message):
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        hello(socket, game.players[0].token)
        socket.send_json(message)
        error = recv(socket, "error")
        assert error["message"]
        # сокет жив и продолжает работать
        socket.send_json({"type": "hello", "token": game.players[0].token})
        assert recv(socket, "state")["you"] == "p1"


def test_oversized_message_is_rejected(client, game):
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        hello(socket, game.players[0].token)
        socket.send_json({"type": "draft", "placements": [], "junk": "я" * 9000})
        error = recv(socket, "error")
    assert "длинное" in error["message"]


# --- переподключение ---------------------------------------------------------------


def test_reconnect_restores_the_same_game(client, game):
    rack = set_rack(game, "p1", "ДОМАКОТ")
    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        hello(socket, game.players[0].token)
        socket.send_json({"type": "commit", "placements": word_placements(rack, "ДОМ", 7, 7)})
        recv(socket, "state")

    with client.websocket_connect(f"/g/{game.id}/ws") as socket:
        state = hello(socket, game.players[0].token)

    assert state["board"][7][7]["letter"] == "Д"
    assert next(p for p in state["players"] if p["id"] == "p1")["score"] == 10
    assert state["current"] == "p2"


def test_presence_shows_who_is_online(client, game):
    with client.websocket_connect(f"/g/{game.id}/ws") as first:
        hello(first, game.players[0].token)
        with client.websocket_connect(f"/g/{game.id}/ws") as second:
            hello(second, game.players[1].token)
            presence = recv(first, "presence")
            online = {p["id"]: p["connected"] for p in presence["players"]}
            assert online == {"p1": True, "p2": True}

        presence = recv(first, "presence")
        online = {p["id"]: p["connected"] for p in presence["players"]}
        assert online == {"p1": True, "p2": False}
