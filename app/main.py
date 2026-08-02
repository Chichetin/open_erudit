"""HTTP-маршруты и игровой WebSocket. Тонкая обёртка над движком."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.hub import Hub
from app.protocol import (
    MAX_MESSAGE_BYTES,
    parse_placements,
    parse_tile_ids,
    parse_word,
)
from app.sessions import GameRegistry, is_valid_game_id
from erudit.game import Game, Player
from erudit.rules import MoveError

APP_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(APP_DIR / "templates"))

# Коды закрытия сокета: 4400 — протокол нарушен, 4401 — токен не подошёл.
CLOSE_BAD_PROTOCOL = 4400
CLOSE_UNAUTHORIZED = 4401
CLOSE_NOT_FOUND = 4404


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # партии переживают перезапуск сервера: снапшоты лежат на диске
    app.state.registry.restore()
    yield


def create_app(registry: GameRegistry | None = None) -> FastAPI:
    app = FastAPI(title="open_erudit", lifespan=_lifespan)
    app.state.registry = registry if registry is not None else GameRegistry()
    app.state.hub = Hub()
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

    @app.websocket("/g/{game_id}/ws")
    async def game_socket(socket: WebSocket, game_id: str):
        await socket.accept()
        registry: GameRegistry = socket.app.state.registry
        hub: Hub = socket.app.state.hub

        authenticated = await _authenticate(socket, registry, game_id)
        if authenticated is None:
            return
        game, player = authenticated

        hub.join(game.id, player.id, socket)
        player.connected = True
        try:
            await hub.send_state(game, player.id, socket)
            await _announce_presence(hub, game)
            await _serve(socket, hub, registry, game, player)
        except WebSocketDisconnect:
            pass
        finally:
            hub.leave(game.id, player.id, socket)
            player.connected = player.id in hub.online(game.id)
            await _announce_presence(hub, game)

    return app


async def _authenticate(
    socket: WebSocket, registry: GameRegistry, game_id: str
) -> tuple[Game, Player] | None:
    """Первое сообщение обязано быть `hello` с токеном. Иначе — закрываем."""
    try:
        message = await _receive(socket)
    except (WebSocketDisconnect, MoveError):
        await socket.close(code=CLOSE_BAD_PROTOCOL)
        return None

    if not isinstance(message, dict) or message.get("type") != "hello":
        await socket.close(code=CLOSE_BAD_PROTOCOL)
        return None
    if not is_valid_game_id(game_id):
        await socket.close(code=CLOSE_NOT_FOUND)
        return None

    found = registry.authenticate(game_id, message.get("token") or "")
    if found is None:
        await socket.close(code=CLOSE_UNAUTHORIZED)
        return None
    return found


async def _serve(
    socket: WebSocket, hub: Hub, registry: GameRegistry, game: Game, player: Player
) -> None:
    while True:
        try:
            message = await _receive(socket)
        except MoveError as exc:
            await socket.send_json({"type": "error", "message": exc.message})
            continue
        if not isinstance(message, dict):
            await socket.send_json({"type": "error", "message": "Испорченное сообщение"})
            continue

        async with hub.lock(game.id):
            await _handle(socket, hub, registry, game, player, message)


async def _handle(
    socket: WebSocket,
    hub: Hub,
    registry: GameRegistry,
    game: Game,
    player: Player,
    message: dict,
) -> None:
    kind = message.get("type")

    try:
        if kind == "draft":
            preview = game.preview(player.id, parse_placements(message.get("placements")))
            await socket.send_json(
                {
                    "type": "preview",
                    "valid": preview.valid,
                    "words": [list(item) for item in preview.words],
                    "total": preview.total,
                    "error": preview.error,
                    "unknown_words": list(preview.unknown_words),
                }
            )
            return
        elif kind == "commit":
            game.play(player.id, parse_placements(message.get("placements")))
        elif kind == "exchange":
            game.exchange(player.id, parse_tile_ids(message.get("tile_ids")))
        elif kind == "pass":
            game.do_pass(player.id)
        elif kind == "allow_word":
            game.allow_word(parse_word(message.get("word")), player.id)
        elif kind == "hello":
            await hub.send_state(game, player.id, socket)
            return
        else:
            await socket.send_json({"type": "error", "message": "Неизвестное сообщение"})
            return
    except MoveError as exc:
        await socket.send_json(
            {
                "type": "error",
                "message": exc.message,
                "unknown_words": list(exc.unknown_words),
            }
        )
        return

    registry.save(game)
    await hub.broadcast_state(game)


async def _announce_presence(hub: Hub, game: Game) -> None:
    online = hub.online(game.id)
    for participant in game.players:
        participant.connected = participant.id in online
    await hub.broadcast(
        game.id,
        {
            "type": "presence",
            "players": [
                {"id": p.id, "name": p.name, "connected": p.connected}
                for p in game.players
            ],
            "current": game.players[game.current].id if game.status == "active" else None,
        },
    )


async def _receive(socket: WebSocket) -> object:
    raw = await socket.receive_text()
    if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise MoveError("Сообщение слишком длинное")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MoveError("Испорченное сообщение") from exc


app = create_app()
