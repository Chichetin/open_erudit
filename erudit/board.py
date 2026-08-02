"""Доска и то, что на ней лежит.

Координаты всюду `(row, col)`, 0-индексные, от левого верхнего угла.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class PlacedTile:
    tile_id: int
    letter: str  # у пустышки — буква, назначенная игроком
    is_blank: bool
    player_id: str
    move_no: int


class Board:
    def __init__(self, size: int) -> None:
        self.size = size
        self._cells: list[list[PlacedTile | None]] = [[None] * size for _ in range(size)]

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.size and 0 <= col < self.size

    def get(self, row: int, col: int) -> PlacedTile | None:
        if not self.in_bounds(row, col):
            return None
        return self._cells[row][col]

    def is_occupied(self, row: int, col: int) -> bool:
        return self.get(row, col) is not None

    def put(self, row: int, col: int, tile: PlacedTile) -> None:
        if not self.in_bounds(row, col):
            raise IndexError((row, col))
        if self._cells[row][col] is not None:
            raise ValueError(f"клетка ({row}, {col}) занята")
        self._cells[row][col] = tile

    def is_empty(self) -> bool:
        return all(cell is None for row in self._cells for cell in row)

    def occupied(self) -> Iterator[tuple[int, int, PlacedTile]]:
        for r, row in enumerate(self._cells):
            for c, cell in enumerate(row):
                if cell is not None:
                    yield r, c, cell

    def neighbours(self, row: int, col: int) -> Iterator[tuple[int, int]]:
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            r, c = row + dr, col + dc
            if self.in_bounds(r, c):
                yield r, c
