"""WebSocket connection manager for /ws/dashboard realtime broadcasts."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def broadcast(
        self, data: dict[str, Any], ignore: WebSocket | None = None
    ) -> None:
        """Send a JSON payload to all connected sockets."""
        message = json.dumps(data, default=str)
        stale = []
        for ws in list(self.active_connections):
            if ws == ignore:
                continue
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


manager = ConnectionManager()
