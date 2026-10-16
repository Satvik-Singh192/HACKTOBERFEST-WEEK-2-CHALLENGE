import io
import csv
import json
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

try:
    from backend.state import store, ROI_CONFIG_FILE, _save_json
    from backend.websocketManager import manager
except ImportError:
    from state import store, ROI_CONFIG_FILE, _save_json
    from websocketManager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    import webbrowser
    import threading

    manager.bind_event_loop(asyncio.get_running_loop())
    print("BGMI Live Scoreboard backend started with persistent storage")
    print("Opening browser → http://127.0.0.1:8000/frontend/setup.html")

    # Open the browser after a short delay so the server is ready
    def _open_browser():
        import time
        time.sleep(1.2)
        webbrowser.open("http://127.0.0.1:8000/frontend/setup.html")

    threading.Thread(target=_open_browser, daemon=True).start()

    try:
        yield
    finally:
        print("BGMI Live Scoreboard backend stopped")


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="BGMI Live Scoreboard & Tournament Manager",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = root_dir / "frontend"
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

output_dir = root_dir / "output"
output_dir.mkdir(parents=True, exist_ok=True)
app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")


# ------------------ Request Models ------------------
class KillRequest(BaseModel):
    team: str
    player: Optional[str] = None
    delta: int = 1


class KnockRequest(BaseModel):
    team: str
    player: Optional[str] = None
    delta: int = 1


class EliminateRequest(BaseModel):
    team: str


class MatchStatusRequest(BaseModel):
    status: str  # LIVE, PAUSED, FINISHED


class NewMatchRequest(BaseModel):
    map: Optional[str] = None


class TeamPayload(BaseModel):
    team: str
    color: Optional[str] = "#94A3B8"
    players: Optional[List[Dict[str, Any]]] = []


class CalibrateRequest(BaseModel):
    xmin: float
    xmax: float
    ymin: float
    ymax: float


# ------------------ System Endpoints ------------------
@app.get("/")
async def home():
    return {
        "title": "BGMI Live Scoreboard & Tournament Engine",
        "status": store.get_status(),
        "match": store.current_match.get("match_number", 1),
        "map": store.current_match.get("map", "Erangel"),
        "teams_count": len(store.current_match.get("teams", [])),
    }


@app.get("/scoreboard")
async def get_scoreboard():
    return store.get_match_snapshot()


@app.get("/api/teams")
async def get_teams():
    return store.current_match.get("teams", [])


@app.get("/api/mvp")
async def get_mvp():
    return store.get_match_snapshot().get("mvp")


@app.get("/api/fraggers")
async def get_fraggers():
    return store.get_top_fraggers(limit=5)


# ------------------ Match Lifecycle ------------------
@app.get("/api/match")
async def get_match_info():
    return store.get_match_snapshot()


@app.post("/api/match/status")
async def update_match_status(req: MatchStatusRequest):
    snapshot = store.set_status(req.status)
    await manager.broadcast_snapshot(snapshot)
    return {"status": "ok", "match_status": store.get_status(), "snapshot": snapshot}


@app.post("/api/match/end")
async def end_match():
    snapshot = store.end_match()
    await manager.broadcast_snapshot(snapshot)
    return {"status": "ok", "message": "Match ended, placement points assigned and saved to history", "snapshot": snapshot}


@app.post("/api/match/new")
async def start_new_match(req: Optional[NewMatchRequest] = None):
    map_name = req.map if req else None
    snapshot = store.start_new_match(map_name=map_name)
    await manager.broadcast_snapshot(snapshot)
    return {"status": "ok", "message": "New match started", "snapshot": snapshot}


@app.get("/api/match/settings")
async def get_settings():
    return store.settings


@app.post("/api/match/settings")
async def update_settings(settings: Dict[str, Any]):
    updated = store.update_settings(settings)
    snapshot = store.get_match_snapshot()
    await manager.broadcast_snapshot(snapshot)
    return {"status": "ok", "settings": updated}


# ------------------ Scoring & Kills ------------------
@app.post("/api/kill")
async def modify_kill(req: KillRequest):
    if store.get_status() in ["PAUSED", "FINISHED"]:
        return {
            "status": "blocked",
            "message": f"Match is currently {store.get_status()}. Kill was not registered.",
            "current_status": store.get_status(),
        }

    snapshot = store.add_kill(team_name=req.team, player_name=req.player, delta=req.delta)
    if snapshot is None:
        return {"error": "Failed to add kill"}

    await manager.broadcast_snapshot(snapshot)
    return {"status": "ok", "snapshot": snapshot}


@app.post("/api/knock")
async def modify_knock(req: KnockRequest):
    if store.get_status() in ["PAUSED", "FINISHED"]:
        return {
            "status": "blocked",
            "message": f"Match is currently {store.get_status()}. Knock was not registered.",
        }

    snapshot = store.add_knock(team_name=req.team, player_name=req.player, delta=req.delta)
    if snapshot:
        await manager.broadcast_snapshot(snapshot)
    return {"status": "ok", "snapshot": snapshot}


@app.post("/api/eliminate")
async def eliminate_team(req: EliminateRequest):
    snapshot = store.eliminate_team(team_name=req.team)
    await manager.broadcast_snapshot(snapshot)
    return {"status": "ok", "snapshot": snapshot}


@app.post("/api/undo")
async def undo_action():
    snapshot = store.undo_last_action()
    if snapshot:
        await manager.broadcast_snapshot(snapshot)
        return {"status": "ok", "snapshot": snapshot}
    return {"status": "none", "message": "No recent kill action to undo"}


@app.post("/api/reset")
async def reset_current_match():
    # Reset current match scores to 0
    cur_num = store.current_match.get("match_number", 1)
    cur_map = store.current_match.get("map", "Erangel")
    store.current_match = store._create_initial_match(cur_num, cur_map)
    store._save_match()
    snapshot = store.get_match_snapshot()
    await manager.broadcast_snapshot(snapshot)
    return {"status": "reset", "snapshot": snapshot}


# ------------------ Roster Management ------------------
@app.get("/api/roster")
async def get_roster():
    return store.roster


@app.post("/api/roster")
async def add_or_update_team(team: TeamPayload):
    updated = store.update_team(team.model_dump())
    snapshot = store.get_match_snapshot()
    await manager.broadcast_snapshot(snapshot)
    return {"status": "ok", "roster": updated}


@app.delete("/api/roster/{team_name}")
async def delete_team(team_name: str):
    updated = store.delete_team(team_name)
    snapshot = store.get_match_snapshot()
    await manager.broadcast_snapshot(snapshot)
    return {"status": "ok", "roster": updated}


@app.post("/api/roster/reset-default")
async def reset_roster_defaults():
    updated = store.reset_roster_defaults()
    snapshot = store.get_match_snapshot()
    await manager.broadcast_snapshot(snapshot)
    return {"status": "ok", "roster": updated}


@app.get("/api/roster/ocr-lookup")
async def get_ocr_lookup():
    return store.get_ocr_roster_lookup()


# ------------------ History & CSV Export ------------------
@app.get("/api/history")
async def get_history():
    return store.get_accumulated_history()


@app.post("/api/history/clear")
async def clear_history():
    store.history = []
    store._save_history()
    return {"status": "ok", "message": "History cleared"}


@app.get("/api/history/export-csv")
async def export_history_csv():
    history_data = store.get_accumulated_history()
    standings = history_data.get("overall_standings", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Rank", "Team", "Matches Played", "WWCD", "Kill Points", "Placement Points", "Total Points"])

    for s in standings:
        writer.writerow([
            s.get("rank", 0),
            s.get("team", ""),
            s.get("matches_played", 0),
            s.get("wwcd", 0),
            s.get("kills", 0),
            s.get("place", 0),
            s.get("total", 0),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tournament_standings.csv"},
    )


# ------------------ ROI Calibration ------------------
@app.post("/api/calibrate")
async def save_calibration(req: CalibrateRequest):
    _save_json(ROI_CONFIG_FILE, req.model_dump())
    return {"status": "ok", "message": "Calibration saved successfully", "config": req.model_dump()}


@app.get("/api/calibrate")
async def get_calibration():
    if ROI_CONFIG_FILE.is_file():
        try:
            with open(ROI_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"xmin": 0.62, "xmax": 0.97, "ymin": 0.05, "ymax": 0.35}


# ------------------ WebSockets ------------------
@app.websocket("/scoreboard")
async def scoreboard_websocket(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
