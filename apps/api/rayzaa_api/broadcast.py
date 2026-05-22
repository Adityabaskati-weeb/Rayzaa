from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class BroadcastHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self.latest_payload: dict[str, Any] = {"booting": True}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
        await websocket.send_json({"type": "state", "payload": self.latest_payload})

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def publish(self, payload: dict[str, Any]) -> None:
        self.latest_payload = payload
        stale: list[WebSocket] = []
        async with self._lock:
            for client in self._clients:
                try:
                    await client.send_json({"type": "state", "payload": payload})
                except Exception:
                    stale.append(client)
            for client in stale:
                self._clients.discard(client)
