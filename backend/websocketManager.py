import asyncio
from copy import deepcopy
from concurrent.futures import Future
from fastapi import WebSocket
from scoreboard import dataframe_to_records
class WebsocketManager:
    
    def __init__(self):
        self.active_connections:set[WebSocket]=set()
        self._lock=asyncio.Lock()
        self._scoreboard={
            "version":0,
            "teams":[],
        }
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
    async def connect(self,websocket:WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
            snapshot=deepcopy(self._scoreboard)
        await websocket.send_json(snapshot)
    async def disconnect(self,websocket:WebSocket):
        async with self._lock:
            self.active_connections.discard(websocket)

    async def get_scoreboard(self) -> dict:
        async with self._lock:
            return deepcopy(self._scoreboard)

    async def update_dataframe(self, dataframe: object) -> dict:
        
        teams = dataframe_to_records(dataframe)
        return await self.update_scoreboard(teams)

    async def update_scoreboard(self, teams: list[dict]) -> dict:
        async with self._lock:
            self._scoreboard = {
                "version": self._scoreboard["version"] + 1,
                "teams": deepcopy(teams),
            }

            snapshot = deepcopy(self._scoreboard)
            connections = list(self.active_connections)
        disconnected=set()
        for websocket in connections:
            try:
                await websocket.send_json(snapshot)
            except Exception:
                disconnected.add(websocket)

        if disconnected:
            async with self._lock:
                self.active_connections.difference_update(disconnected)
        return snapshot

    def update_dataframe_from_thread(self, dataframe: object) -> Future:
        if self._loop is None or self._loop.is_closed():
            raise RuntimeError("FastAPI event loop has not started")
        if not hasattr(dataframe, "copy"):
            raise TypeError("scoreboard update must be a pandas DataFrame")
        dataframe_snapshot = dataframe.copy(deep=True)
        return asyncio.run_coroutine_threadsafe(
            self.update_dataframe(dataframe_snapshot), self._loop
        )


manager = WebsocketManager()
