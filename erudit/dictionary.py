"""Словарь: базовый набор с диска плюс правки, сделанные по ходу партии.

Режим свободный: любой игрок добавляет слово без подтверждения соперника.
Спор решается за столом, а не кодом, — задача словаря лишь не потерять правку.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from erudit.config import DICTIONARY_DIR

BASE_PATH = DICTIONARY_DIR / "nouns.txt"
OVERRIDES_PATH = DICTIONARY_DIR / "overrides.json"


def normalize(word: str) -> str:
    return word.strip().upper()


def load_base(path: Path = BASE_PATH) -> set[str]:
    path = Path(path)
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as fh:
        return {normalize(line) for line in fh if line.strip()}


class Dictionary:
    def __init__(self, base: set[str], overrides_path: Path) -> None:
        self.base = base
        self.overrides_path = Path(overrides_path)
        self.allowed: set[str] = set()
        self.banned: set[str] = set()
        self.journal: list[dict] = []
        self._read_overrides()

    def __contains__(self, word: object) -> bool:
        if not isinstance(word, str):
            return False
        key = normalize(word)
        return key in self.allowed or (key in self.base and key not in self.banned)

    def add(self, word: str, player_id: str) -> None:
        key = normalize(word)
        if not key:
            return
        self.allowed.add(key)
        self.banned.discard(key)
        self._record(key, "allow", player_id)
        self._write_overrides()

    def ban(self, word: str, player_id: str) -> None:
        key = normalize(word)
        if not key:
            return
        self.banned.add(key)
        self.allowed.discard(key)
        self._record(key, "ban", player_id)
        self._write_overrides()

    def _record(self, word: str, action: str, player_id: str) -> None:
        self.journal.append(
            {
                "word": word,
                "action": action,
                "player": player_id,
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        )

    def __len__(self) -> int:
        return len((self.base | self.allowed) - self.banned)

    # --- overrides.json ---------------------------------------------------

    def _read_overrides(self) -> None:
        if not self.overrides_path.exists():
            return
        raw = json.loads(self.overrides_path.read_text(encoding="utf-8"))
        self.allowed = {normalize(w) for w in raw.get("allowed", [])}
        self.banned = {normalize(w) for w in raw.get("banned", [])}
        self.journal = list(raw.get("journal", []))

    def _write_overrides(self) -> None:
        payload = {
            "allowed": sorted(self.allowed),
            "banned": sorted(self.banned),
            "journal": self.journal,
        }
        self.overrides_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.overrides_path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(tmp, self.overrides_path)


def load_dictionary(
    base_path: Path = BASE_PATH, overrides_path: Path = OVERRIDES_PATH
) -> Dictionary:
    return Dictionary(load_base(base_path), overrides_path)
