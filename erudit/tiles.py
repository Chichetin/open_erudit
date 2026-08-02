"""Фишки и мешок.

Мешок перемешивается только через переданный `random.Random`: партия обязана
воспроизводиться по seed'у, иначе разбирать баг по снапшоту невозможно.
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from erudit.config import TileSet


@dataclass(frozen=True)
class Tile:
    id: int
    letter: str | None  # None у пустышки
    value: int

    @property
    def is_blank(self) -> bool:
        return self.letter is None


def build_tiles(tileset: TileSet) -> list[Tile]:
    """Полный набор фишек партии со сквозными уникальными id."""
    tiles: list[Tile] = []
    next_id = 0
    for spec in tileset.tiles:
        for _ in range(spec.count):
            tiles.append(Tile(id=next_id, letter=spec.letter, value=spec.value))
            next_id += 1
    for _ in range(tileset.blank_count):
        tiles.append(Tile(id=next_id, letter=None, value=tileset.blank_value))
        next_id += 1
    return tiles


class Bag:
    def __init__(self, tiles: list[Tile], rng: random.Random) -> None:
        self._tiles = list(tiles)
        self._rng = rng
        self._rng.shuffle(self._tiles)

    @classmethod
    def restore(cls, tiles: list[Tile], rng: random.Random) -> Bag:
        """Мешок из снапшота: порядок фишек сохраняется как есть."""
        bag = cls([], rng)
        bag._tiles = list(tiles)
        return bag

    def draw(self, n: int) -> list[Tile]:
        """Берёт до n фишек. Из пустого мешка возвращает пустой список."""
        n = max(0, min(n, len(self._tiles)))
        drawn = self._tiles[-n:] if n else []
        del self._tiles[len(self._tiles) - n :]
        return list(reversed(drawn))

    def put_back(self, tiles: Iterable[Tile]) -> None:
        self._tiles.extend(tiles)
        self._rng.shuffle(self._tiles)

    def tiles(self) -> list[Tile]:
        """Содержимое мешка. Только для снапшота — игроку не показывается."""
        return list(self._tiles)

    def __len__(self) -> int:
        return len(self._tiles)
