from __future__ import annotations

import asyncio
import csv
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from draft import DraftConfig, DraftState
#from providers import StubProvider, PlayerScorecard


from leaderboard import get_leaderboard, fetch_live_scorecards, LivePlayerScorecard

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PLAYERS_CSV = os.path.join(APP_ROOT, "players.csv")

app = FastAPI(title="Masters Draft Room API (Known Good)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- Draft pool --------
def slugify(s: str) -> str:
    return (
        s.strip()
        .lower()
        .replace("’", "")
        .replace("'", "")
        .replace(".", "")
        .replace(",", "")
        .replace("å", "a")
        .replace("ö", "o")
        .replace("ä", "a")
        .replace("ü", "u")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("á", "a")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
        .replace(" ", "-")
    )

def load_top_players(limit: int = 50) -> List[Dict[str, str]]:
    if not os.path.exists(PLAYERS_CSV):
        raise HTTPException(status_code=500, detail="players.csv not found in backend folder.")
    with open(PLAYERS_CSV, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if "name" not in (r.fieldnames or []):
            raise HTTPException(status_code=500, detail="players.csv must have a 'name' column.")
        players = []
        for row in r:
            name = (row.get("name") or "").strip()
            if name:
                players.append({"athleteId": slugify(name), "name": name})
        return players[:limit]

DRAFT_POOL = load_top_players(50)

# -------- Live scoring (stub now) --------

#provider = StubProvider()
scorecards: Dict[str, LivePlayerScorecard] = {}


# -------- room state --------
@dataclass
class User:
    user_id: str
    name: str
    is_host: bool = False

class Room:
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.sockets: Dict[str, WebSocket] = {}
        self.draft = DraftState(DraftConfig(roster_size=6, seconds_per_pick=60, snake=True, auto_pick=True))
        self.draft.reset_for_teams([])

    def host_id(self) -> Optional[str]:
        for uid, u in self.users.items():
            if u.is_host:
                return uid
        return None

ROOM = Room()

# -------- broadcast --------
async def broadcast(msg: Dict[str, Any]):
    dead: List[str] = []
    for uid, ws in list(ROOM.sockets.items()):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(uid)
    for uid in dead:
        ROOM.sockets.pop(uid, None)
        ROOM.users.pop(uid, None)

def serialize_room_state() -> Dict[str, Any]:
    users = [{"userId": u.user_id, "name": u.name, "isHost": u.is_host} for u in ROOM.users.values()]
    users.sort(key=lambda x: (not x["isHost"], x["name"].lower()))

    d = ROOM.draft
    return {
        "users": users,
        "draft": {
            "started": d.started,
            "completed": d.completed,
            "teams": d.teams,
            "pickNo": d.pick_no,
            "totalPicks": d.total_picks,
            "currentTeam": d.current_team(),
            "secondsLeft": d.remaining_seconds(),
            "rosterSize": d.config.roster_size,
            "secondsPerPick": d.config.seconds_per_pick,
            "snake": d.config.snake,
            "autoPick": d.config.auto_pick,
            "picks": [
                {"pickNo": p.pick_no, "team": p.team, "athleteId": p.athlete_id, "name": p.name, "ts": p.ts}
                for p in d.picks
            ],
            "rosters": {t: [{"athleteId": aid, "name": nm} for (aid, nm) in d.rosters.get(t, [])] for t in d.teams},
            "picked": list(d.picked_ids),
        },
    }

def serialize_scoreboard() -> Dict[str, Any]:
    teams_out: Dict[str, Any] = {}
    for team, roster in ROOM.draft.rosters.items():
        total = 0
        players = []
        for aid, name in roster:
            sc = scorecards.get(aid)
            pts = sc.fantasy_points if sc else 0
            total += pts
            players.append({"athleteId": aid, "name": name, "fantasyPoints": pts})
        teams_out[team] = {"total": total, "players": players}
    return {"teams": teams_out, "updatedTs": time.time()}

# -------- loops --------
async def draft_clock_loop():
    while True:
        await asyncio.sleep(1)
        d = ROOM.draft
        if not d.started or d.completed:
            continue
        if d.remaining_seconds() == 0:
            if not d.config.auto_pick:
                d.advance_turn()
                await broadcast({"type": "room_state", "data": serialize_room_state()})
                continue

            available = [p for p in DRAFT_POOL if p["athleteId"] not in d.picked_ids]
            if available:
                p = available[0]
                try:
                    d.make_pick(p["athleteId"], p["name"])
                except Exception:
                    d.advance_turn()
            else:
                d.advance_turn()

            await broadcast({"type": "room_state", "data": serialize_room_state()})

async def scoring_loop():
    while True:
        await asyncio.sleep(15)
        drafted_ids = list(ROOM.draft.picked_ids)
        if not drafted_ids:
            continue
        try:
            fetched = fetch_live_scorecards()

            filtered = {aid: sc for aid, sc in fetched.items() if aid in drafted_ids}
            scorecards.clear()
            scorecards.update(filtered)
            await broadcast({"type": "scoreboard", "data": serialize_scoreboard()})
        except Exception as e:
            await broadcast({"type": "error", "data": {"message": f"scoring_loop: {e}"}})

@app.on_event("startup")
async def _startup():
    asyncio.create_task(draft_clock_loop())
    asyncio.create_task(scoring_loop())

# -------- REST models --------
class JoinReq(BaseModel):
    userId: str
    name: str

class StartDraftReq(BaseModel):
    userId: str
    seconds_per_pick: Optional[int] = None
    roster_size: Optional[int] = None
    snake: Optional[bool] = None
    auto_pick: Optional[bool] = None

class MakePickReq(BaseModel):
    userId: str
    athlete_id: str
    name: str

# -------- REST endpoints --------
@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/field")
def field(limit: int = 50):
    return {"players": DRAFT_POOL[:limit]}

@app.get("/api/state")
def state():
    return serialize_room_state()

@app.post("/api/join")
async def join(req: JoinReq):
    nm = (req.name or "").strip()[:30] or "Player"
    if req.userId in ROOM.users:
        ROOM.users[req.userId].name = nm
    else:
        ROOM.users[req.userId] = User(user_id=req.userId, name=nm)

    if ROOM.host_id() is None:
        ROOM.users[req.userId].is_host = True

    await broadcast({"type": "room_state", "data": serialize_room_state()})
    return serialize_room_state()

@app.post("/api/draft/start")
async def start_draft(req: StartDraftReq):
    u = ROOM.users.get(req.userId)
    if not u:
        raise HTTPException(status_code=401, detail="Join first.")
    if not u.is_host:
        raise HTTPException(status_code=403, detail="Only host can start the draft.")
    if len(ROOM.users) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 players to start.")

    if req.seconds_per_pick is not None:
        ROOM.draft.config.seconds_per_pick = int(req.seconds_per_pick)
    if req.roster_size is not None:
        ROOM.draft.config.roster_size = int(req.roster_size)
    if req.snake is not None:
        ROOM.draft.config.snake = bool(req.snake)
    if req.auto_pick is not None:
        ROOM.draft.config.auto_pick = bool(req.auto_pick)

    names = [usr.name for usr in ROOM.users.values()]
    random.shuffle(names)

    ROOM.draft.reset_for_teams(names)
    ROOM.draft.start()

    await broadcast({"type": "room_state", "data": serialize_room_state()})
    return serialize_room_state()

@app.post("/api/draft/reset")
async def reset_draft(req: StartDraftReq):
    u = ROOM.users.get(req.userId)
    if not u or not u.is_host:
        raise HTTPException(status_code=403, detail="Only host can reset.")
    ROOM.draft.reset_for_teams([])
    await broadcast({"type": "room_state", "data": serialize_room_state()})
    return serialize_room_state()

@app.post("/api/draft/pick")
async def make_pick(req: MakePickReq):
    u = ROOM.users.get(req.userId)
    if not u:
        raise HTTPException(status_code=401, detail="Join first.")

    d = ROOM.draft
    if not d.started or d.completed:
        raise HTTPException(status_code=400, detail="Draft not active.")

    if d.current_team() != u.name:
        raise HTTPException(status_code=403, detail=f"Not your turn. On the clock: {d.current_team()}")

    pool_ids = {p["athleteId"] for p in DRAFT_POOL}
    if req.athlete_id not in pool_ids:
        raise HTTPException(status_code=400, detail="Player not in draft pool.")
    if req.athlete_id in d.picked_ids:
        raise HTTPException(status_code=409, detail="Already drafted.")

    try:
        d.make_pick(req.athlete_id, req.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await broadcast({"type": "room_state", "data": serialize_room_state()})
    return serialize_room_state()

@app.get("/api/scoreboard")
def scoreboard():
    return serialize_scoreboard()

@app.get('/api/tournament-leaderboard')
def tournament_leaderboard():
    return {'leaderboard': get_leaderboard()}

@app.get("/api/player/{athlete_id}/holes")
def player_holes(athlete_id: str):
    sc = scorecards.get(athlete_id)
    if not sc:
        return {"athleteId": athlete_id, "name": athlete_id.replace("-", " ").title(), "holes": [], "fantasyPoints": 0}
    return {
        "athleteId": sc.athlete_id,
        "name": sc.name,
        "fantasyPoints": sc.fantasy_points,
        "holes": [
            {"round": h.round, "hole": h.hole, "par": h.par, "strokes": h.strokes, "result": h.result, "points": h.points}
            for h in sc.holes
        ],
        "updatedTs": sc.updated_ts,
    }

# -------- WebSocket --------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    user_id = ws.query_params.get("userId")
    if not user_id:
        await ws.close(code=1008)
        return

    await ws.accept()
    ROOM.sockets[user_id] = ws

    await ws.send_json({"type": "room_state", "data": serialize_room_state()})
    await ws.send_json({"type": "scoreboard", "data": serialize_scoreboard()})

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ROOM.sockets.pop(user_id, None)
    except Exception:
        ROOM.sockets.pop(user_id, None)
        
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)        