import pytest

from erudit.config import load_tileset
from erudit.dictionary import Dictionary

TILESET = load_tileset()

# Маленький словарь: тесты сервера не должны зависеть от настоящего nouns.txt.
TEST_WORDS = {
    "ДОМ", "ДОМА", "ДОМЫ", "КОТ", "КОТЫ", "ОСЫ", "ОС", "ТЫ", "КО",
    "МЫ", "ОМ", "ДО", "АД", "СОМ", "ТОК", "РОТ", "НОС",
}


@pytest.fixture
def tileset():
    return TILESET


@pytest.fixture
def dictionary(tmp_path):
    return Dictionary(set(TEST_WORDS), tmp_path / "overrides.json")
