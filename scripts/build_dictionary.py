#!/usr/bin/env python
"""Генерация базового словаря из pymorphy3. Запускается один раз, вручную:

    uv run --group tools python scripts/build_dictionary.py

Оставляем существительные в именительном падеже единственного числа —
то, что в «Эрудите» разрешено выкладывать. Имена, фамилии, отчества,
топонимы, организации, торговые марки и аббревиатуры отсеиваются.

Ожидаемый результат — около 68 тысяч слов. Если получилось радикально другое
число, не коммитить результат, а разбираться, что изменилось в pymorphy3.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = PROJECT_ROOT / "data" / "dictionary" / "nouns.txt"

REQUIRED = {"NOUN", "sing", "nomn"}
FORBIDDEN = {"Name", "Surn", "Patr", "Geox", "Orgn", "Trad", "Abbr", "Init"}

RUSSIAN = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюя")
MIN_LENGTH = 2
EXPECTED_RANGE = (60_000, 80_000)


def is_russian_word(word: str) -> bool:
    return len(word) >= MIN_LENGTH and all(ch in RUSSIAN for ch in word)


def collect_words() -> set[str]:
    import pymorphy3

    morph = pymorphy3.MorphAnalyzer()
    words: set[str] = set()
    for word, tag, *_ in morph.dictionary.iter_known_words():
        grammemes = set(tag.grammemes)
        if not REQUIRED <= grammemes or grammemes & FORBIDDEN:
            continue
        if not is_russian_word(word):
            continue
        words.add(word.upper())
    return words


def main() -> int:
    words = collect_words()
    print(f"отобрано слов: {len(words)}")
    low, high = EXPECTED_RANGE
    if not low <= len(words) <= high:
        print(
            f"это сильно отличается от ожидаемых {low}–{high} — "
            "результат не записан, разберитесь сначала",
            file=sys.stderr,
        )
        return 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(sorted(words)) + "\n", encoding="utf-8")
    print(f"записано в {OUTPUT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
