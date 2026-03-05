from __future__ import annotations

import csv
import os
import time
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PLAYERS_CSV = os.path.join(APP_ROOT, "players.csv")

app = FastAPI(title="Masters Draft Tracker API")

# Allow local dev frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Draft state (in-memory)
# ----------------------------
TEAMS = ["Team A", "Team B", "Team C", "Team D"]
draft_state: Dict[str, List[Dict[str, Any]]] = {t: [] for t in TEAMS}
picked_ids: set[str] = set()

# ----------------------------
# Fantasy scoring rules
# ----------------------------
SCORETYPE_POINTS = {
    "ALBATROSS": 5,
    "DOUBLE_EAGLE": 5,
    "EAGLE": 2,
    "BIRDIE": 1,
    "PAR": 0,
    "BOGEY": -1,
    "DOUBLE_BOGEY": -2,
    "TRIPLE_BOGEY": -3,
}

# ----------------------------
# Utility
# ----------------------------
SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "masters-draft-tracker/1.0",
        "Accept": "application/json",
    }
)

def read_top_players_csv() -> List[Dict[str, str]]:
    if not os.path.exists(PLAYERS_CSV):
        raise HTTPException(status_code=500, detail="players.csv not found in backend folder.")

    out = []
    with open(PLAYERS_CSV, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if "name" not in (r.fieldnames or []):
            raise HTTPException(status_code=500, detail="players.csv must have a 'name' column.")
        for row in r:
            name = (row.get("name") or "").strip()
            if name:
                # For now athleteId is a stable slug derived from name (until you wire ESPN IDs)
                athlete_id = slugify(name)
                out.append({"athleteId": athlete_id, "name": name})
    return out

def slugify(s: str) -> str:
    # crude but stable for ids; you can swap this to real ESPN athlete ids later
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

def http_get_json(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    r = SESSION.get(url, params=params, timeout=25)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Upstream error {r.status_code} for {url}")
    return r.json()

# ----------------------------
# ESPN adapter (pluggable)
# ----------------------------
# Start with "stubbed" scoring so your draft room works today.
# Then you can fill these functions with actual Masters hole-by-hole pulling.
class ESPNAdapter:
    """
    Replace implementation when you have confirmed a reliable Masters hole-by-hole source.
    Keep the response shape the same so the UI doesn't change.
    """

    def get_player_holes(self, athlete_id: str) -> Dict[str, Any]:
        # STUB: return no holes, 0 points.
        # Later: map your athlete_id (slug) -> ESPN athleteId, pull scorecard, parse holes.
        return {
            "athleteId": athlete_id,
            "name": athlete_id.replace("-", " ").title(),
            "holes": [],
            "fantasyPoints": 0,
        }

ESPN = ESPNAdapter()

# ----------------------------
# API Models
# ----------------------------
class DraftPick(BaseModel):
    team: str
    athlete_id: str
    player_name: str

# ----------------------------
# API Endpoints
# ----------------------------
@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/field")
def api_field(limit: int = 50):
    players = read_top_players_csv()
    return {"players": players[:limit]}

@app.get("/api/teams")
def api_teams():
    return {"teams": TEAMS, "draft": draft_state, "picked": list(picked_ids)}

@app.post("/api/draft")
def api_draft(pick: DraftPick):
    if pick.team not in draft_state:
        raise HTTPException(status_code=400, detail="Unknown team.")
    if pick.athlete_id in picked_ids:
        raise HTTPException(status_code=409, detail="Player already drafted.")

    draft_state[pick.team].append({"athleteId": pick.athlete_id, "name": pick.player_name})
    picked_ids.add(pick.athlete_id)
    return {"ok": True, "draft": draft_state}

@app.get("/api/player/{athlete_id}/holes")
def api_player_holes(athlete_id: str):
    # In stub mode this returns empty holes; later it will return real per-hole results
    return ESPN.get_player_holes(athlete_id)

@app.get("/api/draft/scoreboard")
def api_draft_scoreboard():
    """
    Returns fantasy points for all drafted players.
    Cached for 10-15s to support polling.
    """
    now = time.time()
    if not hasattr(api_draft_scoreboard, "_cache"):
        api_draft_scoreboard._cache = {"ts": 0.0, "value": None}
    cache = api_draft_scoreboard._cache
    if cache["value"] is not None and (now - cache["ts"]) < 10:
        return cache["value"]

    out = {"teams": {}}
    for team, roster in draft_state.items():
        team_total = 0
        players = []
        for p in roster:
            aid = p["athleteId"]
            data = ESPN.get_player_holes(aid)
            pts = int(data.get("fantasyPoints") or 0)
            team_total += pts
            players.append({"athleteId": aid, "name": p["name"], "fantasyPoints": pts})

        out["teams"][team] = {"total": team_total, "players": players}

    cache["ts"] = now
    cache["value"] = out
    return out