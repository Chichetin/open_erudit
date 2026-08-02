import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.sessions import GameRegistry, is_valid_game_id


@pytest.fixture
def registry(tileset, dictionary, tmp_path):
    return GameRegistry(tileset, dictionary, games_dir=tmp_path)


@pytest.fixture
def client(registry):
    return TestClient(create_app(registry))


def test_game_id_pattern():
    assert is_valid_game_id("abcdef1234")
    assert not is_valid_game_id("../etc/passwd")
    assert not is_valid_game_id("ABCDEF1234")
    assert not is_valid_game_id("short")
    assert not is_valid_game_id("a" * 17)


def test_created_game_is_active_with_two_players(registry):
    game = registry.create()
    assert is_valid_game_id(game.id)
    assert game.status == "active"
    assert [p.id for p in game.players] == ["p1", "p2"]
    assert all(len(p.rack) == 7 for p in game.players)


def test_tokens_are_unique_and_long(registry):
    game = registry.create()
    tokens = {p.token for p in game.players}
    assert len(tokens) == 2
    assert all(len(t) >= 24 for t in tokens)


def test_authenticate_matches_the_right_player(registry):
    game = registry.create()
    found = registry.authenticate(game.id, game.players[1].token)
    assert found is not None and found[1].id == "p2"


def test_authenticate_rejects_foreign_and_empty_tokens(registry):
    game = registry.create()
    assert registry.authenticate(game.id, "не тот токен") is None
    assert registry.authenticate(game.id, "") is None
    assert registry.authenticate("deadbeef99", game.players[0].token) is None


def test_links_carry_the_token_in_the_hash(registry):
    game = registry.create()
    links = registry.links("http://localhost:8000/", game)
    assert links[0] == f"http://localhost:8000/g/{game.id}#{game.players[0].token}"
    assert len(links) == 2


def test_lobby_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Создать партию" in response.text


def test_post_games_returns_two_links(client):
    response = client.post("/games")
    assert response.status_code == 200
    data = response.json()
    assert is_valid_game_id(data["game_id"])
    assert len(data["links"]) == 2
    assert all(f"/g/{data['game_id']}#" in link for link in data["links"])


def test_game_page_served_for_existing_game(client):
    game_id = client.post("/games").json()["game_id"]
    response = client.get(f"/g/{game_id}")
    assert response.status_code == 200
    assert game_id in response.text


def test_game_page_404_for_unknown_and_malformed_ids(client):
    assert client.get("/g/deadbeef99").status_code == 404
    assert client.get("/g/..%2F..%2Fetc").status_code == 404


def test_too_many_games_rejected(tileset, dictionary, tmp_path):
    registry = GameRegistry(tileset, dictionary, games_dir=tmp_path, max_games=2)
    registry.create()
    registry.create()
    with pytest.raises(RuntimeError):
        registry.create()
