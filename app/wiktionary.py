"""Значения слов из русского Викисловаря.

Сеть нужна только здесь, поэтому модуль живёт в `app/`, а не в движке.
Разбор HTML отделён от загрузки, чтобы его можно было тестировать без сети.
"""

from __future__ import annotations

import asyncio
import json
import re
import urllib.parse
import urllib.request
from collections import OrderedDict
from html.parser import HTMLParser

API_URL = "https://ru.wiktionary.org/w/api.php"
PAGE_URL = "https://ru.wiktionary.org/wiki/"
# Викимедиа просит представляться: безымянные клиенты режут чаще
USER_AGENT = "open_erudit/1.0 (https://github.com/Chichetin/open_erudit)"
TIMEOUT_SECONDS = 6
MAX_DEFINITIONS = 5
CACHE_SIZE = 256

WORD_RE = re.compile(r"^[А-ЯЁ]{2,30}$")

# у пустых элементов нет закрывающего тега — в подсчёте глубины их не учитываем
VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
)


class WiktionaryError(Exception):
    """Викисловарь не ответил или ответил чем-то непонятным."""


class _DefinitionParser(HTMLParser):
    """Собирает пункты списков из разделов «Значение» русской части статьи.

    Примеры употребления лежат внутри тех же пунктов в блоках с классом
    example-*, их пропускаем; вложенные списки (оттенки значения) тоже.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.definitions: list[str] = []
        self._in_russian = False
        self._in_meaning = False
        self._list_depth = 0
        self._skip_depth = 0  # глубина внутри пропускаемого блока
        self._current: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "h1":
            self._in_russian = attributes.get("id") == "Русский"
            self._in_meaning = False
        elif tag in {"h2", "h3", "h4"}:
            self._in_meaning = self._in_russian and (attributes.get("id") or "").startswith(
                "Значение"
            )
        if not self._in_meaning or tag in VOID_TAGS:
            return

        if self._skip_depth:
            self._skip_depth += 1
            return
        if "example" in (attributes.get("class") or ""):
            self._skip_depth = 1
            return
        if tag in {"ol", "ul"}:
            self._list_depth += 1
        elif tag == "li" and self._list_depth == 1:
            self._current = []

    def handle_endtag(self, tag: str) -> None:
        if not self._in_meaning or tag in VOID_TAGS:
            return
        if self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "li" and self._list_depth == 1 and self._current is not None:
            text = " ".join("".join(self._current).split()).strip(" ;,◆")
            if text:
                self.definitions.append(text)
            self._current = None
        elif tag in {"ol", "ul"}:
            self._list_depth -= 1
            if self._list_depth == 0:
                # раздел кончился списком; следующий начнётся новым заголовком
                self._in_meaning = False

    def handle_data(self, data: str) -> None:
        # текст вложенных списков (подвиды, оттенки) в определение не берём
        if (
            self._in_meaning
            and not self._skip_depth
            and self._list_depth == 1
            and self._current is not None
        ):
            self._current.append(data)


def parse_definitions(html: str) -> list[str]:
    parser = _DefinitionParser()
    parser.feed(html)
    return parser.definitions[:MAX_DEFINITIONS]


def page_url(word: str) -> str:
    return PAGE_URL + urllib.parse.quote(word.lower())


def _download(word: str) -> str | None:
    query = urllib.parse.urlencode(
        {
            "action": "parse",
            "page": word.lower(),
            "prop": "text",
            "format": "json",
            "formatversion": "2",
            "redirects": "1",
        }
    )
    request = urllib.request.Request(f"{API_URL}?{query}", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except (OSError, ValueError) as exc:
        raise WiktionaryError(str(exc)) from exc
    if "error" in payload:
        return None  # статьи нет
    try:
        return payload["parse"]["text"]
    except (KeyError, TypeError) as exc:
        raise WiktionaryError("неожиданный ответ") from exc


class Wiktionary:
    def __init__(self, download=_download) -> None:
        self._download = download
        self._cache: OrderedDict[str, list[str]] = OrderedDict()

    async def definitions(self, word: str) -> list[str]:
        """Пустой список — статьи нет или в ней нет русских значений."""
        if word in self._cache:
            self._cache.move_to_end(word)
            return self._cache[word]
        html = await asyncio.to_thread(self._download, word)
        found = parse_definitions(html) if html else []
        self._cache[word] = found
        if len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return found
