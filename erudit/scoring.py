"""Подсчёт очков хода.

Правила Scrabble контринтуитивны, поэтому по пунктам:

* бонус клетки действует только в тот ход, когда клетка закрывается;
* если новая клетка входит и в главное, и в перпендикулярное слово, её бонус
  применяется в обоих — это не двойной учёт, а нормальное правило;
* пустышка приносит 0 очков, но словесный множитель под ней работает.
"""

from __future__ import annotations

from erudit.config import TileSet
from erudit.rules import FormedWord


def score_words(words: list[FormedWord], tileset: TileSet) -> list[tuple[str, int]]:
    return [(word.text, score_word(word, tileset)) for word in words]


def score_word(word: FormedWord, tileset: TileSet) -> int:
    total = 0
    word_multiplier = 1
    for cell in word.cells:
        value = 0 if cell.is_blank else tileset.value_of(cell.letter)
        if cell.is_new:
            total += value * tileset.letter_multiplier(cell.row, cell.col)
            word_multiplier *= tileset.word_multiplier(cell.row, cell.col)
        else:
            total += value
    return total * word_multiplier


def score_move(
    words: list[FormedWord], tileset: TileSet, tiles_used: int = 0
) -> tuple[int, list[tuple[str, int]]]:
    """Очки за ход и разбивка по словам."""
    per_word = score_words(words, tileset)
    total = sum(points for _, points in per_word)
    if tileset.bingo_bonus and tiles_used >= tileset.rack_size:
        total += tileset.bingo_bonus
    return total, per_word
