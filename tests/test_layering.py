"""Граница движка: `erudit/` не знает про HTTP.

Нарушение этой границы — повод переписать, а не обойти, поэтому проверяем не
на словах, а по исходникам.
"""

import ast
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "erudit"
FORBIDDEN = {"app", "fastapi", "starlette", "uvicorn"}


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_engine_does_not_import_the_server():
    for path in sorted(ENGINE.glob("*.py")):
        assert not (imported_roots(path) & FORBIDDEN), path.name
