"""Сверка клиентской проверки геометрии с движком.

`app/static/js/placement.js` — осознанная копия правил из `erudit/rules.py`.
Копия, за которой никто не следит, расходится с оригиналом; этот тест гоняет
одни и те же расклады через обе реализации и требует одинакового вердикта.

Без node тест пропускается: движок обязан тестироваться и без него.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from erudit.board import Board, PlacedTile
from erudit.projection import for_player
from erudit.rules import MoveError, Placement, validate_geometry

PLACEMENT_JS = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "placement.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="нет node")

# (описание, уже стоящие слова, новые фишки)
CASES = [
    ("первый ход через центр", [], [(7, 7, "Д"), (7, 8, "О")]),
    ("первый ход мимо центра", [], [(0, 0, "Д"), (0, 1, "О")]),
    ("вне доски", [], [(7, 15, "Д")]),
    ("одна фишка в центре", [], [(7, 7, "Д")]),
    ("продолжение слова", [(7, 7, "h", "ДОМ")], [(7, 10, "А")]),
    ("не касается", [(7, 7, "h", "ДОМ")], [(0, 0, "К"), (0, 1, "О")]),
    ("лесенкой", [(7, 7, "h", "ДОМ")], [(8, 7, "У"), (9, 8, "Б")]),
    ("разрыв", [(7, 7, "h", "ДОМ")], [(8, 7, "У"), (10, 7, "Б")]),
    ("разрыв закрыт старой фишкой", [(7, 7, "h", "ДОМ"), (9, 7, "h", "РОТ")], [(6, 7, "У"), (8, 7, "А")]),
    ("клетка занята", [(7, 7, "h", "ДОМ")], [(7, 8, "У")]),
    ("вертикально вниз", [(7, 7, "h", "ДОМ")], [(8, 7, "У"), (9, 7, "Б")]),
    ("две фишки в одной клетке", [], [(7, 7, "Д"), (7, 7, "О")]),
]


def build_board(existing, tileset) -> Board:
    board = Board(tileset.board_size)
    for row, col, direction, letters in existing:
        for i, letter in enumerate(letters):
            r = row + (i if direction == "v" else 0)
            c = col + (i if direction == "h" else 0)
            board.put(r, c, PlacedTile(500 + r * 15 + c, letter, False, "p1", 1))
    return board


def python_verdict(board: Board, placements: list[Placement], center) -> bool:
    try:
        validate_geometry(board, placements, center)
    except MoveError:
        return False
    return True


def js_verdicts(payload: list[dict]) -> list[bool]:
    script = f"""
import {{ checkGeometry }} from {json.dumps(str(PLACEMENT_JS))};
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const cases = JSON.parse(chunks.join(""));
process.stdout.write(JSON.stringify(cases.map((c) => checkGeometry(c.state, c.placements).valid)));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr.strip()[-2000:])
    return json.loads(result.stdout)


def test_js_geometry_matches_the_engine(tileset, dictionary):
    import random

    from erudit.game import Game

    payload = []
    expected = []
    for _, existing, new in CASES:
        board = build_board(existing, tileset)
        placements = [
            Placement(row=r, col=c, tile_id=i, letter=letter)
            for i, (r, c, letter) in enumerate(new)
        ]

        game = Game("abcdef1234", tileset, dictionary, random.Random(1))
        game.add_player("Первый")
        game.add_player("Второй")
        game.start()
        game.board = board
        state = for_player(game, "p1")

        payload.append(
            {
                "state": {
                    "board": state["board"],
                    "bonuses": state["bonuses"],
                    "center": state["center"],
                },
                "placements": [
                    {"row": p.row, "col": p.col, "tile_id": p.tile_id, "letter": p.letter}
                    for p in placements
                ],
            }
        )
        expected.append(python_verdict(board, placements, tileset.center))

    actual = js_verdicts(payload)
    mismatched = [
        (name, want, got)
        for (name, _, _), want, got in zip(CASES, expected, actual, strict=True)
        if want != got
    ]
    assert not mismatched
