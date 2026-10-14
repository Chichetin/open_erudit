"""Персональный вид партии.

Единственное место, где состояние превращается в то, что уходит игроку.
Своя стойка видна целиком, чужая — только количеством, мешок — только
количеством, токенов нет никогда. Невышедшие буквы — мешок вместе с
чужой стойкой, без разбивки: их любой игрок и так сосчитает по доске. Никакой другой код не сериализует Game
для отправки, поэтому приватность проверяется одним тестом — на эту функцию.
"""

from __future__ import annotations

from collections import Counter

from erudit.game import Game, Player
from erudit.stats import summarize
from erudit.tiles import Tile


def tile_to_dict(tile: Tile) -> dict:
    return {"id": tile.id, "letter": tile.letter, "value": tile.value}


def for_player(game: Game, player_id: str) -> dict:
    me = next((p for p in game.players if p.id == player_id), None)
    current = game.players[game.current].id if game.players else None
    last_move_no = game.move_no

    return {
        "type": "state",
        "game_id": game.id,
        "status": game.status,
        "you": player_id,
        "current": current if game.status == "active" else None,
        "your_turn": game.status == "active" and current == player_id,
        "board": _board(game, last_move_no),
        "bonuses": list(game.tileset.board),
        "center": list(game.tileset.center),
        "rack_size": game.tileset.rack_size,
        # алфавит нужен клиенту для диалога выбора буквы у пустышки
        "alphabet": [spec.letter for spec in game.tileset.tiles],
        "rack": [tile_to_dict(tile) for tile in me.rack] if me else [],
        "players": [_player(p, me) for p in game.players],
        "bag": len(game.bag),
        "unseen": _unseen(game, me),
        "move_no": game.move_no,
        "pass_streak": game.pass_streak,
        "log": list(game.log),
        "winners": [p.id for p in game.winners()] if game.status == "finished" else [],
        "rematch": _rematch(game, me),
        "stats": summarize(game) if game.status == "finished" else None,
    }


def _rematch(game: Game, me: Player | None) -> dict | None:
    """Ссылка на реванш — только со своим токеном, чужой не уходит никогда."""
    if game.rematch is None or me is None:
        return None
    token = game.rematch["tokens"].get(me.id)
    if token is None:
        return None
    return {"game_id": game.rematch["game_id"], "token": token}


def _player(player: Player, me: Player | None) -> dict:
    return {
        "id": player.id,
        "name": player.name,
        "score": player.score,
        "tiles": len(player.rack),
        "connected": player.connected,
        "is_you": me is not None and player.id == me.id,
    }


def _unseen(game: Game, me: Player | None) -> list[dict]:
    """Сколько каких фишек ещё не вышло — с точки зрения этого игрока."""
    hidden = list(game.bag.tiles())
    for player in game.players:
        if player is not me:
            hidden.extend(player.rack)
    counts = Counter(tile.letter for tile in hidden)

    specs = [(spec.letter, spec.value) for spec in game.tileset.tiles]
    specs.append((None, game.tileset.blank_value))
    return [
        {"letter": letter, "value": value, "count": counts[letter]}
        for letter, value in specs
    ]


def _board(game: Game, last_move_no: int) -> list[list[dict | None]]:
    size = game.board.size
    cells: list[list[dict | None]] = [[None] * size for _ in range(size)]
    for row, col, placed in game.board.occupied():
        cells[row][col] = {
            "letter": placed.letter,
            "is_blank": placed.is_blank,
            "player": placed.player_id,
            "is_last": placed.move_no == last_move_no,
        }
    return cells
