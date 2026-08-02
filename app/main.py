"""HTTP-маршруты и игровой WebSocket. Тонкая обёртка над движком."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.sessions import GameRegistry, is_valid_game_id

APP_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(APP_DIR / "templates"))


def create_app(registry: GameRegistry | None = None) -> FastAPI:
    app = FastAPI(title="open_erudit")
    app.state.registry = registry if registry is not None else GameRegistry()
    app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def lobby(request: Request):
        return TEMPLATES.TemplateResponse(request, "lobby.html", {})

    @app.post("/games")
    async def create_game(request: Request):
        registry: GameRegistry = request.app.state.registry
        try:
            game = registry.create()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {
            "game_id": game.id,
            "links": registry.links(str(request.base_url), game),
        }

    @app.get("/g/{game_id}", response_class=HTMLResponse)
    async def game_page(request: Request, game_id: str):
        if not is_valid_game_id(game_id):
            raise HTTPException(status_code=404, detail="Партия не найдена")
        registry: GameRegistry = request.app.state.registry
        if registry.get(game_id) is None:
            raise HTTPException(status_code=404, detail="Партия не найдена")
        return TEMPLATES.TemplateResponse(request, "game.html", {"game_id": game_id})

    return app


app = create_app()
