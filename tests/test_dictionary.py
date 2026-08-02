"""Тесты работают на маленьком поддельном наборе: настоящий nouns.txt не читается."""

import json

import pytest

from erudit.dictionary import Dictionary, load_base

BASE = {"КОТ", "ДОМ", "ЗАМОК"}


@pytest.fixture
def overrides(tmp_path):
    return tmp_path / "overrides.json"


def test_base_words_pass(overrides):
    d = Dictionary(set(BASE), overrides)
    assert "КОТ" in d
    assert "ТРАМВАЙ" not in d


def test_case_does_not_matter(overrides):
    d = Dictionary(set(BASE), overrides)
    assert "кот" in d
    assert "  Кот  " in d


def test_added_word_passes_and_survives_reload(overrides):
    d = Dictionary(set(BASE), overrides)
    d.add("шмель", "p1")
    assert "ШМЕЛЬ" in d
    assert "ШМЕЛЬ" in Dictionary(set(BASE), overrides)


def test_banned_word_stops_passing(overrides):
    d = Dictionary(set(BASE), overrides)
    d.ban("замок", "p2")
    assert "ЗАМОК" not in d
    assert "ЗАМОК" not in Dictionary(set(BASE), overrides)


def test_ban_then_add_restores_the_word(overrides):
    d = Dictionary(set(BASE), overrides)
    d.ban("КОТ", "p1")
    d.add("КОТ", "p2")
    assert "КОТ" in d
    assert "КОТ" not in d.banned


def test_journal_records_the_author(overrides):
    d = Dictionary(set(BASE), overrides)
    d.add("шмель", "p1")
    d.ban("КОТ", "p2")
    raw = json.loads(overrides.read_text(encoding="utf-8"))
    assert [(e["word"], e["action"], e["player"]) for e in raw["journal"]] == [
        ("ШМЕЛЬ", "allow", "p1"),
        ("КОТ", "ban", "p2"),
    ]


def test_overrides_file_is_valid_json(overrides):
    d = Dictionary(set(BASE), overrides)
    d.add("шмель", "p1")
    raw = json.loads(overrides.read_text(encoding="utf-8"))
    assert raw["allowed"] == ["ШМЕЛЬ"]
    assert raw["banned"] == []
    assert not list(overrides.parent.glob("*.tmp"))


def test_missing_base_file_gives_empty_set(tmp_path):
    assert load_base(tmp_path / "nope.txt") == set()


def test_load_base_reads_words(tmp_path):
    path = tmp_path / "nouns.txt"
    path.write_text("кот\nдом\n\nзамок\n", encoding="utf-8")
    assert load_base(path) == BASE


def test_non_string_is_not_in_dictionary(overrides):
    d = Dictionary(set(BASE), overrides)
    assert 42 not in d
