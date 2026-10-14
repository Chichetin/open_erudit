"""Порядок фишек на стойке (`app/static/js/rackorder.js`).

Без node тест пропускается: движок обязан тестироваться и без него.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

RACK_ORDER_JS = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "rackorder.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="нет node")


def run_js(expression: str):
    script = f"""
import {{ arrange, moveTo }} from {json.dumps(str(RACK_ORDER_JS))};
const ids = (tiles) => tiles.map((tile) => tile.id);
const rack = (...list) => list.map((id) => ({{ id }}));
process.stdout.write(JSON.stringify({expression}));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr.strip()[-2000:])
    return json.loads(result.stdout)


def test_saved_order_wins_over_server_order():
    assert run_js("ids(arrange([3, 1, 2], rack(1, 2, 3)))") == [3, 1, 2]


def test_new_tiles_go_to_the_end_and_gone_ones_drop_out():
    # 2 сыграна, 8 и 9 пришли из мешка
    assert run_js("ids(arrange([3, 2, 1], rack(1, 3, 8, 9)))") == [3, 1, 8, 9]


def test_empty_order_keeps_server_order():
    assert run_js("ids(arrange([], rack(5, 4, 6)))") == [5, 4, 6]


@pytest.mark.parametrize(
    ("tile", "index", "expected"),
    [
        (3, 0, [3, 1, 2, 4]),
        (1, 3, [2, 3, 4, 1]),
        (1, 2, [2, 3, 1, 4]),
        (4, 1, [1, 4, 2, 3]),
        (2, 99, [1, 3, 4, 2]),
        (2, -5, [2, 1, 3, 4]),
    ],
)
def test_move_to(tile, index, expected):
    assert run_js(f"moveTo([1, 2, 3, 4], {tile}, {index})") == expected
