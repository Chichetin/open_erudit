"""Значения слов из Викисловаря: разбор на образце разметки, без сети."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.sessions import GameRegistry
from app.wiktionary import Wiktionary, WiktionaryError, parse_definitions

# Та же разметка, что отдаёт Викисловарь, с ловушками: пример внутри пункта,
# пустой тег <link>, вложенный список подвидов, синонимы и другой язык.
SAMPLE = """
<section><h1 id="Русский">Русский</h1>
<section><h4 id="Значение">Значение</h4>
<ol>
<li><a><span class="label">зоол.</span></a><link rel="x"/> самец домашней кошки
  <span class="example-fullblock"><span>◆</span><span class="example-block">много <b>котов</b><br/></span></span>
  <ul><li>домашний кот (лат. Felis catus)</li></ul>
</li>
<li>то же, что <a>бабник</a> <span class="example-fullblock">◆ Отсутствует пример</span></li>
<li><span class="example-fullblock">◆ только пример</span></li>
</ol></section>
<section><h4 id="Синонимы">Синонимы</h4><ol><li>котик</li></ol></section>
<section><h4 id="Значение_2">Значение</h4><ol><li>второе значение омонима</li></ol></section>
</section>
<section><h1 id="Татарский">Татарский</h1>
<section><h4 id="Значение_3">Значение</h4><ol><li>чужой язык</li></ol></section>
</section>
"""


def test_definitions_are_cleaned_from_examples_and_nested_lists():
    assert parse_definitions(SAMPLE) == [
        "зоол. самец домашней кошки",
        "то же, что бабник",
        "второе значение омонима",
    ]


def test_page_without_russian_section_gives_nothing():
    assert parse_definitions('<h1 id="Татарский">x</h1><h4 id="Значение"></h4><ol><li>y</li></ol>') == []


def test_at_most_five_definitions():
    items = "".join(f"<li>значение {i}</li>" for i in range(9))
    html = f'<h1 id="Русский"></h1><h4 id="Значение"></h4><ol>{items}</ol>'
    assert len(parse_definitions(html)) == 5


@pytest.fixture
def downloads():
    return []


@pytest.fixture
def client(tileset, dictionary, tmp_path, downloads):
    def fake_download(word):
        downloads.append(word)
        if word == "СЛОМАНО":
            raise WiktionaryError("нет связи")
        if word == "НЕТСТАТЬИ":
            return None
        return SAMPLE

    registry = GameRegistry(tileset, dictionary, games_dir=tmp_path)
    return TestClient(create_app(registry, wiktionary=Wiktionary(fake_download)))


def test_word_route_returns_definitions_and_link(client):
    data = client.get("/words/кот").json()
    assert data["word"] == "КОТ"
    assert data["definitions"][0] == "зоол. самец домашней кошки"
    assert data["url"].startswith("https://ru.wiktionary.org/wiki/")


def test_word_route_caches(client, downloads):
    client.get("/words/кот")
    client.get("/words/КОТ")
    assert downloads == ["КОТ"]


def test_missing_article_is_an_empty_list(client):
    assert client.get("/words/нетстатьи").json()["definitions"] == []


def test_wiktionary_failure_is_502(client):
    response = client.get("/words/сломано")
    assert response.status_code == 502
    assert "Викисловарь" in response.json()["detail"]


@pytest.mark.parametrize("word", ["cat", "к", "кот1", "а" * 31])
def test_only_russian_words_are_looked_up(client, downloads, word):
    assert client.get(f"/words/{word}").status_code == 400
    assert downloads == []
