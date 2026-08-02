"""Загрузка набора: доска, бонусы, фишки, номиналы.

Всё, что отличает один вариант игры от другого, лежит в JSON, а не в коде.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TILESETS_DIR = DATA_DIR / "tilesets"
DICTIONARY_DIR = DATA_DIR / "dictionary"
GAMES_DIR = DATA_DIR / "games"

DEFAULT_TILESET = TILESETS_DIR / "scrabble_ru.json"

# Символы раскладки бонусов.
TRIPLE_WORD = "T"
DOUBLE_WORD = "D"
TRIPLE_LETTER = "t"
DOUBLE_LETTER = "d"
CENTER = "*"
PLAIN = "."

# Центр действует как удвоение слова: первый ход всегда его накрывает.
WORD_MULTIPLIERS = {TRIPLE_WORD: 3, DOUBLE_WORD: 2, CENTER: 2}
LETTER_MULTIPLIERS = {TRIPLE_LETTER: 3, DOUBLE_LETTER: 2}


@dataclass(frozen=True)
class TileSpec:
    letter: str
    value: int
    count: int


@dataclass(frozen=True)
class TileSet:
    id: str
    name: str
    board_size: int
    rack_size: int
    bingo_bonus: int
    center: tuple[int, int]
    board: tuple[str, ...]
    tiles: tuple[TileSpec, ...]
    blank_count: int
    blank_value: int

    def bonus_at(self, row: int, col: int) -> str:
        return self.board[row][col]

    def word_multiplier(self, row: int, col: int) -> int:
        return WORD_MULTIPLIERS.get(self.bonus_at(row, col), 1)

    def letter_multiplier(self, row: int, col: int) -> int:
        return LETTER_MULTIPLIERS.get(self.bonus_at(row, col), 1)

    def value_of(self, letter: str) -> int:
        for spec in self.tiles:
            if spec.letter == letter:
                return spec.value
        raise KeyError(letter)

    @property
    def total_tiles(self) -> int:
        return sum(spec.count for spec in self.tiles) + self.blank_count


def load_tileset(path: Path = DEFAULT_TILESET) -> TileSet:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    size = int(raw["board_size"])
    board = tuple(raw["board"])
    if len(board) != size or any(len(row) != size for row in board):
        raise ValueError(f"раскладка доски должна быть {size}×{size}")

    center = tuple(raw["center"])
    if len(center) != 2:
        raise ValueError("center должен быть парой координат")

    blanks = raw.get("blanks", {})
    tiles = tuple(
        TileSpec(letter=spec["letter"], value=int(spec["value"]), count=int(spec["count"]))
        for spec in raw["tiles"]
    )
    letters = {spec.letter for spec in tiles}
    if len(letters) != len(tiles):
        raise ValueError("буквы в наборе повторяются")

    return TileSet(
        id=raw["id"],
        name=raw["name"],
        board_size=size,
        rack_size=int(raw["rack_size"]),
        bingo_bonus=int(raw.get("bingo_bonus", 0)),
        center=(int(center[0]), int(center[1])),
        board=board,
        tiles=tiles,
        blank_count=int(blanks.get("count", 0)),
        blank_value=int(blanks.get("value", 0)),
    )
