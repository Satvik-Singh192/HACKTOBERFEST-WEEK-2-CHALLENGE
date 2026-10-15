import asyncio
from copy import deepcopy
from concurrent.futures import Future
from fastapi import WebSocket

try:
    from backend.state import store
except ImportError:
    from state import store


class WebsocketManager:
    def __init__(self):
        self.active_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
            snapshot = store.get_match_snapshot()
        await websocket.send_json(snapshot)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections.discard(websocket)

    async def get_scoreboard(self) -> dict:
        return store.get_match_snapshot()

    async def broadcast_snapshot(self, snapshot: dict) -> dict:
        async with self._lock:
            connections = list(self.active_connections)

        disconnected = set()
        for websocket in connections:
            try:
                await websocket.send_json(snapshot)
            except Exception:
                disconnected.add(websocket)

        if disconnected:
            async with self._lock:
                self.active_connections.difference_update(disconnected)
        return snapshot

    async def update_scoreboard(self, teams: list[dict]) -> dict:
        """Legacy helper for updating teams list and broadcasting."""
        store.current_match["teams"] = deepcopy(teams)
        store._save_match()
        snapshot = store.get_match_snapshot()
        return await self.broadcast_snapshot(snapshot)

    def broadcast_from_thread(self, snapshot: dict) -> Future:
        if self._loop is None or self._loop.is_closed():
            raise RuntimeError("FastAPI event loop has not started")
        return asyncio.run_coroutine_threadsafe(
            self.broadcast_snapshot(snapshot), self._loop
        )


manager = WebsocketManager()
