from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect  
from websocketManager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    manager.bind_event_loop(asyncio.get_running_loop())
    print("BGMI Live Scoreboard backend started")
    try:
        yield
    finally:
        print("BGMI Live Scoreboard backend stopped")


app = FastAPI(
    title="BGMI Live Scoreboard",
    lifespan=lifespan,
)


@app.get("/")
async def home():
    return {"message": "BGMI Live Scoreboard Backend"}


@app.get("/scoreboard")
async def get_scoreboard():
    return await manager.get_scoreboard()


async def publish_scoreboard_dataframe(dataframe: object) -> dict:
    return await manager.update_dataframe(dataframe)


@app.websocket("/scoreboard")
async def scoreboard_websocket(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    finally:
        await manager.disconnect(websocket)
