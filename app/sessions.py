"""Реестр партий: создание, поиск, сверка токенов.

Игра выставлена в интернет, поэтому здесь два обязательных правила:
`game_id` проверяется регулярным выражением до любого обращения к диску,
а токен сверяется через `secrets.compare_digest`.
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path

from erudit.config import GAMES_DIR, TileSet, load_tileset
from erudit.dictionary import Dictionary, load_dictionary
from erudit.game import Game, Player

GAME_ID_RE = re.compile(r"^[a-z0-9]{8,16}$")

DEFAULT_NAMES = ("Игрок 1", "Игрок 2")
MAX_GAMES = 50


def new_game_id() -> str:
    return secrets.token_hex(5)


def is_valid_game_id(game_id: str) -> bool:
    return bool(GAME_ID_RE.match(game_id))


class GameRegistry:
    def __init__(
        self,
        tileset: TileSet | None = None,
        dictionary: Dictionary | None = None,
        games_dir: Path = GAMES_DIR,
        max_games: int = MAX_GAMES,
    ) -> None:
        self.tileset = tileset if tileset is not None else load_tileset()
        self.dictionary = dictionary if dictionary is not None else load_dictionary()
        self.games_dir = Path(games_dir)
        self.max_games = max_games
        self.games: dict[str, Game] = {}

    def create(self, names: tuple[str, ...] = DEFAULT_NAMES) -> Game:
        if len(self.games) >= self.max_games:
            self._drop_oldest_finished()
        if len(self.games) >= self.max_games:
            raise RuntimeError("Слишком много партий на сервере")

        game_id = new_game_id()
        while game_id in self.games:
            game_id = new_game_id()

        game = Game(game_id, self.tileset, self.dictionary)
        for name in names:
            game.add_player(name)
        game.start()
        self.games[game_id] = game
        return game

    def get(self, game_id: str) -> Game | None:
        if not is_valid_game_id(game_id):
            return None
        return self.games.get(game_id)

    def authenticate(self, game_id: str, token: str) -> tuple[Game, Player] | None:
        game = self.get(game_id)
        if game is None or not isinstance(token, str) or not token:
            return None
        # compare_digest не принимает строки с не-ASCII, а токен из адресной
        # строки может быть каким угодно — сравниваем байты
        given = token.encode("utf-8", "surrogatepass")
        for player in game.players:
            if secrets.compare_digest(player.token.encode("utf-8"), given):
                return game, player
        return None

    def links(self, base_url: str, game: Game) -> list[str]:
        base = base_url.rstrip("/")
        return [f"{base}/g/{game.id}#{player.token}" for player in game.players]

    def _drop_oldest_finished(self) -> None:
        finished = [g for g in self.games.values() if g.status == "finished"]
        if finished:
            del self.games[finished[0].id]
