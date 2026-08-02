"""Разбор сообщений клиента.

Всё, что приходит из сокета, — чужой ввод: проверяем типы и границы до того,
как что-то попадёт в движок.
"""

from __future__ import annotations

from erudit.rules import MoveError, Placement

MAX_MESSAGE_BYTES = 8 * 1024
MAX_PLACEMENTS = 16
MAX_WORD_LENGTH = 30
MAX_NAME_LENGTH = 24


def parse_placements(raw: object) -> list[Placement]:
    if not isinstance(raw, list):
        raise MoveError("Испорченный ход")
    if len(raw) > MAX_PLACEMENTS:
        raise MoveError("Слишком много фишек в ходе")

    placements: list[Placement] = []
    for item in raw:
        if not isinstance(item, dict):
            raise MoveError("Испорченный ход")
        try:
            row = int(item["row"])
            col = int(item["col"])
            tile_id = int(item["tile_id"])
            letter = item["letter"]
        except (KeyError, TypeError, ValueError) as exc:
            raise MoveError("Испорченный ход") from exc
        if not isinstance(letter, str) or len(letter) != 1:
            raise MoveError("Испорченный ход")
        placements.append(Placement(row=row, col=col, tile_id=tile_id, letter=letter.upper()))
    return placements


def parse_tile_ids(raw: object) -> list[int]:
    if not isinstance(raw, list) or len(raw) > MAX_PLACEMENTS:
        raise MoveError("Испорченный список фишек")
    try:
        return [int(item) for item in raw]
    except (TypeError, ValueError) as exc:
        raise MoveError("Испорченный список фишек") from exc


def parse_word(raw: object) -> str:
    if not isinstance(raw, str):
        raise MoveError("Испорченное слово")
    word = raw.strip().upper()
    if not word or len(word) > MAX_WORD_LENGTH or not word.isalpha():
        raise MoveError("Так слово не выглядит")
    return word
