"""Партия: ходы, пас, обмен, конец игры.

Единственный арбитр. Всё, что приходит снаружи, проверяется заново и до того,
как изменится хоть что-то в состоянии: отклонённый ход обязан не оставлять
следов.
"""

from __future__ import annotations

import random
import secrets
from dataclasses import dataclass, field
from typing import Literal, Protocol

from erudit.board import Board, PlacedTile
from erudit.config import TileSet
from erudit.rules import (
    FormedWord,
    MoveError,
    Placement,
    collect_words,
    overlay_from_placements,
    validate_geometry,
)
from erudit.scoring import score_move
from erudit.tiles import Bag, Tile, build_tiles

Status = Literal["waiting", "active", "finished"]

MAX_PASS_STREAK = 6


class WordSource(Protocol):
    def __contains__(self, word: object) -> bool: ...


@dataclass
class Player:
    id: str
    name: str
    token: str
    rack: list[Tile] = field(default_factory=list)
    score: int = 0
    connected: bool = False

    def rack_value(self) -> int:
        return sum(tile.value for tile in self.rack)


@dataclass(frozen=True)
class Preview:
    valid: bool
    words: tuple[tuple[str, int], ...] = ()
    total: int = 0
    error: str | None = None
    unknown_words: tuple[str, ...] = ()


@dataclass(frozen=True)
class CheckedMove:
    """Ход, прошедший все проверки. Существует, чтобы play и preview считали
    одно и то же одним и тем же кодом."""

    placements: list[Placement]
    blank_ids: frozenset[int]
    words: list[FormedWord]
    total: int
    per_word: list[tuple[str, int]]


@dataclass(frozen=True)
class MoveResult:
    player_id: str
    total: int
    words: tuple[tuple[str, int], ...]
    move_no: int
    finished: bool


class Game:
    def __init__(
        self,
        game_id: str,
        tileset: TileSet,
        dictionary: WordSource,
        rng: random.Random | None = None,
        max_players: int = 2,
    ) -> None:
        self.id = game_id
        self.tileset = tileset
        self.dictionary = dictionary
        self.rng = rng if rng is not None else random.Random()
        self.max_players = max_players
        self.board = Board(tileset.board_size)
        self.bag = Bag(build_tiles(tileset), self.rng)
        self.players: list[Player] = []
        self.current = 0
        self.pass_streak = 0
        self.move_no = 0
        self.status: Status = "waiting"
        self.log: list[dict] = []

    # --- участники ------------------------------------------------------

    def add_player(self, name: str) -> Player:
        if len(self.players) >= self.max_players:
            raise MoveError("В партии уже достаточно игроков")
        player = Player(
            id=f"p{len(self.players) + 1}",
            name=name,
            token=secrets.token_urlsafe(24),
        )
        self.players.append(player)
        return player

    def player_by_id(self, player_id: str) -> Player:
        for player in self.players:
            if player.id == player_id:
                return player
        raise MoveError("Игрок не найден")

    @property
    def current_player(self) -> Player | None:
        if not self.players or self.status != "active":
            return None
        return self.players[self.current]

    def start(self) -> None:
        if self.status != "waiting":
            raise MoveError("Партия уже начата")
        if len(self.players) < 2:
            raise MoveError("Нужны двое игроков")
        for player in self.players:
            player.rack = self.bag.draw(self.tileset.rack_size)
        self.status = "active"
        self.current = 0
        self._log("start", player_id=None, text="Партия началась")

    # --- ход ------------------------------------------------------------

    def preview(self, player_id: str, placements: list[Placement]) -> Preview:
        """Те же проверки, что и в play, но без изменения состояния."""
        try:
            player = self._require_turn(player_id)
            checked = self._evaluate(player, placements)
        except MoveError as exc:
            return Preview(valid=False, error=exc.message, unknown_words=exc.unknown_words)
        return Preview(valid=True, words=tuple(checked.per_word), total=checked.total)

    def play(self, player_id: str, placements: list[Placement]) -> MoveResult:
        player = self._require_turn(player_id)
        checked = self._evaluate(player, placements)

        # с этого места состояние меняется — все проверки уже позади
        self.move_no += 1
        for placement in checked.placements:
            self.board.put(
                placement.row,
                placement.col,
                PlacedTile(
                    tile_id=placement.tile_id,
                    letter=placement.letter,
                    is_blank=placement.tile_id in checked.blank_ids,
                    player_id=player.id,
                    move_no=self.move_no,
                ),
            )
        used = {p.tile_id for p in checked.placements}
        player.rack = [tile for tile in player.rack if tile.id not in used]
        player.score += checked.total
        player.rack.extend(self.bag.draw(self.tileset.rack_size - len(player.rack)))
        self.pass_streak = 0

        self._log(
            "move",
            player_id=player.id,
            text=f"{player.name}: {', '.join(w for w, _ in checked.per_word)} — {checked.total}",
            words=[list(item) for item in checked.per_word],
            score=checked.total,
            move_no=self.move_no,
        )

        went_out = player if not player.rack and len(self.bag) == 0 else None
        finished = self._maybe_finish(went_out)
        if not finished:
            self._advance()
        return MoveResult(
            player_id=player.id,
            total=checked.total,
            words=tuple(checked.per_word),
            move_no=self.move_no,
            finished=finished,
        )

    def do_pass(self, player_id: str) -> None:
        player = self._require_turn(player_id)
        self.pass_streak += 1
        self._log("pass", player_id=player.id, text=f"{player.name}: пас")
        if not self._maybe_finish():
            self._advance()

    def exchange(self, player_id: str, tile_ids: list[int]) -> None:
        player = self._require_turn(player_id)
        if not tile_ids:
            raise MoveError("Выберите фишки для обмена")
        if len(self.bag) < self.tileset.rack_size:
            raise MoveError("В мешке слишком мало фишек для обмена")
        if len(set(tile_ids)) != len(tile_ids):
            raise MoveError("Одна и та же фишка выбрана дважды")
        rack_ids = {tile.id for tile in player.rack}
        if not set(tile_ids) <= rack_ids:
            raise MoveError("Этих фишек нет на вашей стойке")

        given = [tile for tile in player.rack if tile.id in set(tile_ids)]
        player.rack = [tile for tile in player.rack if tile.id not in set(tile_ids)]
        # сначала берём новые, только потом возвращаем старые — иначе игрок
        # может вытянуть обратно те же фишки
        player.rack.extend(self.bag.draw(len(given)))
        self.bag.put_back(given)

        self.pass_streak += 1
        self._log(
            "exchange",
            player_id=player.id,
            text=f"{player.name}: обмен {len(given)} фишек",
            count=len(given),
        )
        if not self._maybe_finish():
            self._advance()

    def allow_word(self, word: str, player_id: str) -> None:
        add = getattr(self.dictionary, "add", None)
        if add is None:
            raise MoveError("Словарь не поддерживает правку")
        add(word, player_id)
        player = self.player_by_id(player_id)
        self._log(
            "dictionary",
            player_id=player.id,
            text=f"{player.name} добавил слово {word.upper()}",
            word=word.upper(),
        )

    # --- внутреннее -------------------------------------------------------

    def _require_turn(self, player_id: str) -> Player:
        if self.status != "active":
            raise MoveError("Партия не идёт")
        player = self.player_by_id(player_id)
        if self.players[self.current].id != player_id:
            raise MoveError("Сейчас не ваш ход")
        return player

    def _blank_ids(self, player: Player, placements: list[Placement]) -> frozenset[int]:
        by_id = {tile.id: tile for tile in player.rack}
        return frozenset(p.tile_id for p in placements if by_id[p.tile_id].is_blank)

    def _evaluate(self, player: Player, placements: list[Placement]) -> CheckedMove:
        """Полная проверка хода без единого изменения состояния."""
        if not placements:
            raise MoveError("Ход пуст: положите хотя бы одну фишку")

        by_id = {tile.id: tile for tile in player.rack}
        for placement in placements:
            tile = by_id.get(placement.tile_id)
            if tile is None:
                raise MoveError("Этой фишки нет на вашей стойке")
            letter = placement.letter.upper()
            if tile.is_blank:
                if not self._is_known_letter(letter):
                    raise MoveError("Выберите букву для пустышки")
            elif letter != tile.letter:
                raise MoveError("Буква не совпадает с фишкой")

        normalized = [
            Placement(p.row, p.col, p.tile_id, p.letter.upper()) for p in placements
        ]
        direction = validate_geometry(self.board, normalized, self.tileset.center)
        blank_ids = self._blank_ids(player, normalized)
        overlay = overlay_from_placements(normalized, blank_ids=blank_ids)
        words = collect_words(self.board, overlay, direction)
        if not words:
            raise MoveError("Ход не образует ни одного слова")

        unknown = tuple(word.text for word in words if word.text not in self.dictionary)
        if unknown:
            raise MoveError("Нет в словаре: " + ", ".join(unknown), unknown_words=unknown)

        total, per_word = score_move(words, self.tileset, tiles_used=len(normalized))
        return CheckedMove(
            placements=normalized,
            blank_ids=blank_ids,
            words=words,
            total=total,
            per_word=per_word,
        )

    def _is_known_letter(self, letter: str) -> bool:
        return any(spec.letter == letter for spec in self.tileset.tiles)

    def _advance(self) -> None:
        self.current = (self.current + 1) % len(self.players)

    def _maybe_finish(self, went_out: Player | None = None) -> bool:
        if went_out is None and self.pass_streak < MAX_PASS_STREAK:
            return False
        self._finish(went_out)
        return True

    def _finish(self, went_out: Player | None) -> None:
        bonus = 0
        for player in self.players:
            if player is went_out:
                continue
            penalty = player.rack_value()
            player.score -= penalty
            bonus += penalty
        if went_out is not None:
            went_out.score += bonus
            self._log(
                "finish",
                player_id=went_out.id,
                text=f"{went_out.name} вышел первым и получает {bonus}",
            )
        else:
            self._log("finish", player_id=None, text="Партия окончена: шесть пасов подряд")
        self.status = "finished"

    def winners(self) -> list[Player]:
        if not self.players:
            return []
        best = max(player.score for player in self.players)
        return [player for player in self.players if player.score == best]

    def _log(self, kind: str, player_id: str | None, text: str, **extra) -> None:
        self.log.append({"type": kind, "player": player_id, "text": text, **extra})
