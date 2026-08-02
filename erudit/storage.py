"""Снапшот партии на диске.

Сервер держит состояние в памяти, а на диск пишет после каждого события:
ноутбук может уснуть или получить обновление посреди партии, и терять её
из-за этого не хочется.

В снапшоте есть токены игроков — без них не восстановить вход по старой
ссылке. Поэтому файлы снапшотов в репозиторий не попадают.
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

from erudit.board import PlacedTile
from erudit.config import TileSet
from erudit.game import Game, Player, WordSource
from erudit.tiles import Bag, Tile

FORMAT_VERSION = 1
FINISHED_TTL_SECONDS = 7 * 24 * 3600


def to_dict(game: Game) -> dict:
    return {
        "version": FORMAT_VERSION,
        "id": game.id,
        "tileset": game.tileset.id,
        "status": game.status,
        "current": game.current,
        "pass_streak": game.pass_streak,
        "move_no": game.move_no,
        "log": game.log,
        "players": [
            {
                "id": p.id,
                "name": p.name,
                "token": p.token,
                "score": p.score,
                "rack": [_tile(t) for t in p.rack],
            }
            for p in game.players
        ],
        "bag": [_tile(t) for t in game.bag.tiles()],
        "board": [
            {
                "row": row,
                "col": col,
                "tile_id": cell.tile_id,
                "letter": cell.letter,
                "is_blank": cell.is_blank,
                "player_id": cell.player_id,
                "move_no": cell.move_no,
            }
            for row, col, cell in game.board.occupied()
        ],
    }


def from_dict(data: dict, tileset: TileSet, dictionary: WordSource) -> Game:
    if data.get("version") != FORMAT_VERSION:
        raise ValueError(f"неизвестная версия снапшота: {data.get('version')}")
    if data.get("tileset") != tileset.id:
        raise ValueError(f"снапшот другого набора: {data.get('tileset')}")

    game = Game(data["id"], tileset, dictionary, random.Random())
    game.status = data["status"]
    game.current = int(data["current"])
    game.pass_streak = int(data["pass_streak"])
    game.move_no = int(data["move_no"])
    game.log = list(data.get("log", []))
    game.players = [
        Player(
            id=p["id"],
            name=p["name"],
            token=p["token"],
            rack=[_untile(t) for t in p["rack"]],
            score=int(p["score"]),
            connected=False,
        )
        for p in data["players"]
    ]
    game.bag = Bag.restore([_untile(t) for t in data["bag"]], game.rng)
    for cell in data["board"]:
        game.board.put(
            cell["row"],
            cell["col"],
            PlacedTile(
                tile_id=cell["tile_id"],
                letter=cell["letter"],
                is_blank=cell["is_blank"],
                player_id=cell["player_id"],
                move_no=cell["move_no"],
            ),
        )
    return game


def save(game: Game, directory: Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{game.id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(to_dict(game), ensure_ascii=False), encoding="utf-8"
    )
    os.replace(tmp, path)
    return path


def load_all(
    directory: Path, tileset: TileSet, dictionary: WordSource
) -> dict[str, Game]:
    """Читает все снапшоты. Испорченный файл пропускается, а не роняет старт."""
    directory = Path(directory)
    games: dict[str, Game] = {}
    if not directory.exists():
        return games
    for path in sorted(directory.glob("*.json")):
        try:
            game = from_dict(
                json.loads(path.read_text(encoding="utf-8")), tileset, dictionary
            )
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
        games[game.id] = game
    return games


def prune_finished(directory: Path, ttl_seconds: int = FINISHED_TTL_SECONDS) -> int:
    """Удаляет снапшоты законченных партий старше TTL. Возвращает число удалённых."""
    directory = Path(directory)
    if not directory.exists():
        return 0
    removed = 0
    deadline = time.time() - ttl_seconds
    for path in directory.glob("*.json"):
        if path.stat().st_mtime > deadline:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            path.unlink(missing_ok=True)
            removed += 1
            continue
        if data.get("status") == "finished":
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def _tile(tile: Tile) -> dict:
    return {"id": tile.id, "letter": tile.letter, "value": tile.value}


def _untile(data: dict) -> Tile:
    return Tile(id=int(data["id"]), letter=data["letter"], value=int(data["value"]))
