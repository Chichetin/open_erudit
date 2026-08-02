# open_erudit

Веб-«Эрудит» на двоих: сервер поднимается на локальной машине, игроки заходят из
браузеров — по локальной сети или снаружи через быстрый туннель Cloudflare.

Архитектурные решения — в [`PLAN.md`](PLAN.md), пошаговый план реализации —
в [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md).

## Разработка

```bash
uv sync          # окружение (Python 3.13)
uv run pytest    # тесты
```
