"""Геометрия хода и сбор образованных слов.

Источник истины для правил размещения. Клиентская копия в
`app/static/js/placement.js` существует только ради подсветки и обязана
следовать за этим файлом, а не наоборот.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from erudit.board import Board, PlacedTile

Direction = Literal["h", "v"]
HORIZONTAL: Direction = "h"
VERTICAL: Direction = "v"

Overlay = dict[tuple[int, int], PlacedTile]


@dataclass(frozen=True)
class Placement:
    row: int
    col: int
    tile_id: int
    letter: str  # для пустышки — выбранная игроком буква


class MoveError(Exception):
    """Ход отклонён. Текст показывается игроку, поэтому — по-русски."""

    def __init__(self, message: str, unknown_words: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.message = message
        self.unknown_words = unknown_words


@dataclass(frozen=True)
class WordCell:
    row: int
    col: int
    letter: str
    is_blank: bool
    is_new: bool


@dataclass(frozen=True)
class FormedWord:
    cells: tuple[WordCell, ...]

    @property
    def text(self) -> str:
        return "".join(cell.letter for cell in self.cells)

    def __len__(self) -> int:
        return len(self.cells)


def overlay_from_placements(
    placements: list[Placement],
    blank_ids: frozenset[int] = frozenset(),
    player_id: str = "",
    move_no: int = 0,
) -> Overlay:
    return {
        (p.row, p.col): PlacedTile(
            tile_id=p.tile_id,
            letter=p.letter,
            is_blank=p.tile_id in blank_ids,
            player_id=player_id,
            move_no=move_no,
        )
        for p in placements
    }


def validate_geometry(
    board: Board, placements: list[Placement], center: tuple[int, int]
) -> Direction:
    """Проверяет размещение и возвращает направление хода.

    Порядок проверок важен: игроку показывается первая нарушенная причина.
    """
    if not placements:
        raise MoveError("Ход пуст: положите хотя бы одну фишку")

    coords = [(p.row, p.col) for p in placements]
    for row, col in coords:
        if not board.in_bounds(row, col):
            raise MoveError("Фишка вне доски")
    if len(set(coords)) != len(coords):
        raise MoveError("Две фишки в одной клетке")
    if len({p.tile_id for p in placements}) != len(placements):
        raise MoveError("Одна и та же фишка использована дважды")

    for row, col in coords:
        if board.is_occupied(row, col):
            raise MoveError("Клетка уже занята")

    rows = {r for r, _ in coords}
    cols = {c for _, c in coords}
    if len(rows) == 1:
        direction: Direction = HORIZONTAL
    elif len(cols) == 1:
        direction = VERTICAL
    else:
        raise MoveError("Фишки должны лежать в одной строке или в одном столбце")

    _check_no_gaps(board, coords, direction)

    if board.is_empty():
        if center not in coords:
            raise MoveError("Первый ход должен накрыть центральную клетку")
    elif not any(
        board.is_occupied(r, c) for row, col in coords for r, c in board.neighbours(row, col)
    ):
        raise MoveError("Слово должно касаться уже выложенных фишек")

    return direction


def _check_no_gaps(
    board: Board, coords: list[tuple[int, int]], direction: Direction
) -> None:
    """Между крайними новыми фишками пустых клеток быть не должно.

    Разрыв допустим только там, где уже стоит старая фишка.
    """
    new_cells = set(coords)
    if direction == HORIZONTAL:
        row = coords[0][0]
        line = range(min(c for _, c in coords), max(c for _, c in coords) + 1)
        cells = [(row, c) for c in line]
    else:
        col = coords[0][1]
        line = range(min(r for r, _ in coords), max(r for r, _ in coords) + 1)
        cells = [(r, col) for r in line]

    for r, c in cells:
        if (r, c) not in new_cells and not board.is_occupied(r, c):
            raise MoveError("В слове есть разрыв")


def collect_words(board: Board, overlay: Overlay, direction: Direction) -> list[FormedWord]:
    """Все слова длиной ≥ 2, образованные ходом: главное и перпендикулярные.

    Одна фишка не задаёт направления однозначно, но это и не нужно: главное
    слово длиной 1 отбрасывается, а перпендикулярное собирается для каждой
    новой фишки — так оба варианта попадают в результат сами собой.
    """
    words: list[FormedWord] = []
    seen: set[tuple[tuple[int, int], ...]] = set()

    def add(word: FormedWord | None) -> None:
        if word is None or len(word) < 2:
            return
        key = tuple((cell.row, cell.col) for cell in word.cells)
        if key in seen:
            return
        seen.add(key)
        words.append(word)

    any_cell = next(iter(overlay))
    add(_word_through(board, overlay, any_cell, direction))

    cross: Direction = VERTICAL if direction == HORIZONTAL else HORIZONTAL
    for cell in overlay:
        add(_word_through(board, overlay, cell, cross))

    return words


def _word_through(
    board: Board, overlay: Overlay, start: tuple[int, int], direction: Direction
) -> FormedWord | None:
    dr, dc = (0, 1) if direction == HORIZONTAL else (1, 0)
    row, col = start

    while _filled(board, overlay, row - dr, col - dc):
        row, col = row - dr, col - dc

    cells: list[WordCell] = []
    while _filled(board, overlay, row, col):
        placed = overlay.get((row, col)) or board.get(row, col)
        assert placed is not None
        cells.append(
            WordCell(
                row=row,
                col=col,
                letter=placed.letter,
                is_blank=placed.is_blank,
                is_new=(row, col) in overlay,
            )
        )
        row, col = row + dr, col + dc

    return FormedWord(tuple(cells)) if cells else None


def _filled(board: Board, overlay: Overlay, row: int, col: int) -> bool:
    if not board.in_bounds(row, col):
        return False
    return (row, col) in overlay or board.is_occupied(row, col)
