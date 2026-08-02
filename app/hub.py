"""Открытые сокеты партии и рассылка снапшотов.

После каждого изменения каждому подключённому уходит его собственный полный
снапшот: партия весит единицы килобайт, а рассинхронизация из-за дельт стоила
бы дороже трафика.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket, WebSocketDisconnect

from erudit.game import Game
from erudit.projection import for_player


class Hub:
    def __init__(self) -> None:
        self._connections: dict[str, list[tuple[str, WebSocket]]] = defaultdict(list)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def lock(self, game_id: str) -> asyncio.Lock:
        return self._locks[game_id]

    def join(self, game_id: str, player_id: str, socket: WebSocket) -> None:
        self._connections[game_id].append((player_id, socket))

    def leave(self, game_id: str, player_id: str, socket: WebSocket) -> None:
        entries = self._connections.get(game_id)
        if not entries:
            return
        with_socket = (player_id, socket)
        if with_socket in entries:
            entries.remove(with_socket)
        if not entries:
            self._connections.pop(game_id, None)

    def online(self, game_id: str) -> set[str]:
        return {player_id for player_id, _ in self._connections.get(game_id, [])}

    async def send_state(self, game: Game, player_id: str, socket: WebSocket) -> None:
        await socket.send_json(for_player(game, player_id))

    async def broadcast_state(self, game: Game) -> None:
        for player_id, socket in list(self._connections.get(game.id, [])):
            await self._safe_send(game.id, player_id, socket, for_player(game, player_id))

    async def broadcast(self, game_id: str, payload: dict) -> None:
        for player_id, socket in list(self._connections.get(game_id, [])):
            await self._safe_send(game_id, player_id, socket, payload)

    async def _safe_send(
        self, game_id: str, player_id: str, socket: WebSocket, payload: dict
    ) -> None:
        try:
            await socket.send_json(payload)
        except (RuntimeError, WebSocketDisconnect):
            # соперник закрыл вкладку прямо во время рассылки — не повод
            # ронять ход того, кто его сделал
            self.leave(game_id, player_id, socket)
