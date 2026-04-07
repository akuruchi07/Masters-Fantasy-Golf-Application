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

from draft import ALL_SLOTS, BACKUP_SLOTS, DraftConfig, DraftState, SLOT_LABELS, STARTER_SLOTS
from leaderboard import LivePlayerScorecard, build_team_scoreboard, fetch_live_scorecards, get_leaderboard

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PLAYERS_CSV = os.path.join(APP_ROOT, "players.csv")

app = FastAPI(title="Masters Draft Room API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        .replace("ø", "o")
        .replace(" ", "-")
    )


PAST_CHAMPIONS = {
    "angel-cabrera",
    "fred-couples",
    "sergio-garcia",
    "dustin-johnson",
    "zach-johnson",
    "hideki-matsuyama",
    "rory-mcilroy",
    "jose-maria-olazabal",
    "jon-rahm",
    "patrick-reed",
    "scottie-scheffler",
    "charl-schwartzel",
    "adam-scott",
    "vijay-singh",
    "jordan-spieth",
    "bubba-watson",
    "mike-weir",
    "danny-willett",
}

AMERICANS = {
    "daniel-berger",
    "akshay-bhatia",
    "keegan-bradley",
    "michael-brennan",
    "jacob-bridgeman",
    "sam-burns",
    "brian-campbell",
    "patrick-cantlay",
    "wyndham-clark",
    "fred-couples",
    "bryson-dechambeau",
    "harris-english",
    "ethan-fang",
    "ryan-gerard",
    "chris-gotterup",
    "max-greyserman",
    "ben-griffin",
    "brian-harman",
    "russell-henley",
    "jackson-herrington",
    "brandon-holtz",
    "max-homa",
    "mason-howell",
    "dustin-johnson",
    "zach-johnson",
    "john-keefer",
    "michael-kim",
    "kurt-kitayama",
    "jake-knapp",
    "brooks-koepka",
    "matt-mccarty",
    "maverick-mcnealy",
    "collin-morikawa",
    "andrew-novak",
    "patrick-reed",
    "davis-riley",
    "xander-schauffele",
    "scottie-scheffler",
    "jj-spaun",
    "jordan-spieth",
    "samuel-stevens",
    "justin-thomas",
    "bubba-watson",
    "gary-woodland",
    "cameron-young",
}

NON_PGA_TOUR = {
    "bryson-dechambeau",
    "sergio-garcia",
    "tyrrell-hatton",
    "dustin-johnson",
    "tom-mckibbin",
    "carlos-ortiz",
    "jon-rahm",
    "charl-schwartzel",
    "cameron-smith",
    "bubba-watson",
    "angel-cabrera",
    "fred-couples",
    "jose-maria-olazabal",
    "vijay-singh",
    "mike-weir",
    "danny-willett",
}

ODDS_LABELS = {
    "scottie-scheffler": "+500",
    "bryson-dechambeau": "10/1",
    "jon-rahm": "11/1",
    "rory-mcilroy": "11/1",
    "ludvig-aberg": "15/1",
    "xander-schauffele": "17/1",
    "cameron-young": "22/1",
    "justin-rose": "30/1",
    "brooks-koepka": "40/1",
    "jordan-spieth": "40/1",
    "viktor-hovland": "45/1",
    "patrick-reed": "45/1",
    "robert-macintyre": "35/1",
    "tommy-fleetwood": "35/1",
    "justin-thomas": "80/1",
    "akshay-bhatia": "70/1",
    "shane-lowry": "80/1",
    "patrick-cantlay": "66/1",
    "dustin-johnson": "225/1",
}

AUTO_DRAFT_PRIORITY = [
    "scottie-scheffler",
    "bryson-dechambeau",
    "jon-rahm",
    "rory-mcilroy",
    "ludvig-aberg",
    "xander-schauffele",
    "cameron-young",
    "justin-rose",
    "brooks-koepka",
    "jordan-spieth",
    "viktor-hovland",
    "patrick-reed",
    "robert-macintyre",
    "tommy-fleetwood",
    "matt-fitzpatrick",
    "collin-morikawa",
    "hideki-matsuyama",
    "corey-conners",
    "justin-thomas",
    "patrick-cantlay",
    "tyrrell-hatton",
    "shane-lowry",
    "russell-henley",
    "sam-burns",
    "daniel-berger",
    "akshay-bhatia",
    "wyndham-clark",
    "sungjae-im",
    "harris-english",
    "cameron-smith",
    "brian-harman",
    "sepp-straka",
    "nick-taylor",
    "min-woo-lee",
    "vijay-singh",
    "keegan-bradley",
    "ryan-fox",
    "samuel-stevens",
    "max-homa",
    "maverick-mcnealy",
    "jake-knapp",
    "ben-griffin",
    "chris-gotterup",
    "max-greyserman",
    "jason-day",
    "nicolai-hojgaard",
    "rasmus-hojgaard",
    "si-woo-kim",
    "michael-kim",
    "aaron-rai",
    "carlos-ortiz",
    "adam-scott",
    "alex-noren",
    "gary-woodland",
    "dustin-johnson",
    "sergio-garcia",
    "zach-johnson",
    "angel-cabrera",
    "fred-couples",
    "bubba-watson",
    "danny-willett",
    "mike-weir",
    "jose-maria-olazabal",
    "charl-schwartzel",
    "haotong-li",
    "sami-valimaki",
    "harry-hall",
    "nicolas-echavarria",
    "ryan-gerard",
    "brian-campbell",
    "matt-mccarty",
    "andrew-novak",
    "davis-riley",
    "jacob-bridgeman",
    "kurt-kitayama",
    "john-keefer",
    "michael-brennan",
    "ethan-fang",
    "jackson-herrington",
    "brandon-holtz",
    "mason-howell",
    "naoyuki-kataoka",
    "casey-jarvis",
    "fifa-laopakdee",
    "mateo-pulcini",
    "marco-penge",
    "rasmus-neergaard-petersen",
    "kristoffer-reitan",
    "aldrich-potgieter",
    "tom-mckibbin",
]
AUTO_DRAFT_RANK = {name: idx + 1 for idx, name in enumerate(AUTO_DRAFT_PRIORITY)}


def player_meta_from_name(name: str) -> Dict[str, Any]:
    athlete_id = slugify(name)
    is_american = athlete_id in AMERICANS
    odds_rank = AUTO_DRAFT_RANK.get(athlete_id, 10_000)
    initials = " ".join(part[0] for part in name.replace(".", "").split()[:2]).upper()
    avatar_url = f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&size=128&background=145233&color=F5E7B1&bold=true"
    return {
        "athleteId": athlete_id,
        "name": name,
        "isPastChampion": athlete_id in PAST_CHAMPIONS,
        "isAmerican": is_american,
        "isInternational": not is_american,
        "isNonPga": athlete_id in NON_PGA_TOUR,
        "oddsRank": odds_rank,
        "oddsLabel": ODDS_LABELS.get(athlete_id),
        "avatarUrl": avatar_url,
        "initials": initials,
    }


def load_players() -> List[Dict[str, Any]]:
    if not os.path.exists(PLAYERS_CSV):
        raise HTTPException(status_code=500, detail="players.csv not found in backend folder.")
    players: List[Dict[str, Any]] = []
    with open(PLAYERS_CSV, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if "name" not in (r.fieldnames or []):
            raise HTTPException(status_code=500, detail="players.csv must have a 'name' column.")
        for row in r:
            name = (row.get("name") or "").strip()
            if name:
                players.append(player_meta_from_name(name))
    return players


def player_priority_score(player: Dict[str, Any]) -> int:
    return int(player.get("oddsRank") or AUTO_DRAFT_RANK.get(player["athleteId"], 10_000))


DRAFT_POOL = load_players()
PLAYER_MAP = {p["athleteId"]: p for p in DRAFT_POOL}
scorecards: Dict[str, LivePlayerScorecard] = {}


@dataclass
class User:
    user_id: str
    name: str
    is_host: bool = False


class Room:
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.sockets: Dict[str, WebSocket] = {}
        self.draft = DraftState(DraftConfig(roster_size=7, seconds_per_pick=60, snake=True, auto_pick=True))
        self.draft.reset_for_teams([])

    def host_id(self) -> Optional[str]:
        for uid, u in self.users.items():
            if u.is_host:
                return uid
        return None


ROOM = Room()


async def broadcast(msg: Dict[str, Any]):
    dead: List[str] = []
    for uid, ws in list(ROOM.sockets.items()):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(uid)
    for uid in dead:
        ROOM.sockets.pop(uid, None)


def serialize_room_state() -> Dict[str, Any]:
    users = [{"userId": u.user_id, "name": u.name, "isHost": u.is_host} for u in ROOM.users.values()]
    users.sort(key=lambda x: (not x["isHost"], x["name"].lower()))

    d = ROOM.draft
    rosters_out: Dict[str, Dict[str, Any]] = {}
    for team in d.teams:
        roster = d.rosters.get(team, {})
        rosters_out[team] = {
            "slots": {slot: roster.get(slot) for slot in ALL_SLOTS},
            "filledCount": sum(1 for slot in ALL_SLOTS if roster.get(slot) is not None),
            "requiredFilled": all(roster.get(slot) is not None for slot in STARTER_SLOTS),
        }

    return {
        "users": users,
        "slotLabels": SLOT_LABELS,
        "draft": {
            "started": d.started,
            "completed": d.completed,
            "teams": d.teams,
            "pickNo": d.pick_no,
            "totalPicks": d.total_picks,
            "currentTeam": d.current_team(),
            "secondsLeft": d.remaining_seconds(),
            "deadlineTs": d.deadline_ts,
            "rosterSize": d.config.roster_size,
            "secondsPerPick": d.config.seconds_per_pick,
            "snake": d.config.snake,
            "autoPick": d.config.auto_pick,
            "starterSlots": STARTER_SLOTS,
            "backupSlots": BACKUP_SLOTS,
            "picks": [
                {
                    "pickNo": p.pick_no,
                    "team": p.team,
                    "athleteId": p.athlete_id,
                    "name": p.name,
                    "slot": p.slot,
                    "slotLabel": p.slot_label,
                    "ts": p.ts,
                }
                for p in d.picks
            ],
            "rosters": rosters_out,
            "picked": list(d.picked_ids),
        },
    }


def serialize_scoreboard() -> Dict[str, Any]:
    teams_out = build_team_scoreboard(ROOM.draft.rosters, scorecards)
    return {"teams": teams_out, "updatedTs": time.time()}


def next_open_slot_for_team(team_name: str) -> Optional[str]:
    roster = ROOM.draft.rosters.get(team_name, {})
    slot_order = [
        "past_champion",
        "international",
        "american",
        "non_pga",
        "wildcard",
        "backup_1",
        "backup_2",
    ]
    for slot in slot_order:
        if roster.get(slot) is None:
            return slot
    return None


def best_available_for_slot(team_name: str, slot: str) -> Optional[Dict[str, Any]]:
    d = ROOM.draft
    candidates = []

    for player in DRAFT_POOL:
        if player["athleteId"] in d.picked_ids:
            continue
        eligible = d.eligible_slots(team_name, player)
        if slot in eligible:
            candidates.append(player)

    if not candidates:
        return None

    candidates.sort(key=player_priority_score)
    return candidates[0]


def do_auto_pick_for_team(team_name: str) -> bool:
    d = ROOM.draft
    next_slot = next_open_slot_for_team(team_name)
    if not next_slot:
        return False

    player = best_available_for_slot(team_name, next_slot)
    if not player:
        return False

    d.make_pick(player["athleteId"], player["name"], next_slot, player)
    return True


async def draft_clock_loop():
    while True:
        await asyncio.sleep(1)
        d = ROOM.draft
        if not d.started or d.completed:
            continue
        if d.remaining_seconds() != 0:
            continue

        if not d.config.auto_pick:
            d.advance_turn()
            await broadcast({"type": "room_state", "data": serialize_room_state()})
            continue

        team = d.current_team()
        if not team:
            continue

        try:
            picked = do_auto_pick_for_team(team)
            if not picked:
                d.advance_turn()
        except Exception:
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
    slot: Optional[str] = None


class UpdateTimerReq(BaseModel):
    userId: str
    seconds_per_pick: int


class AutoPickReq(BaseModel):
    userId: str


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/field")
def field(limit: int = 0):
    if limit and limit > 0:
        return {"players": DRAFT_POOL[:limit], "slotLabels": SLOT_LABELS}
    return {"players": DRAFT_POOL, "slotLabels": SLOT_LABELS}


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
    ROOM.draft.config.roster_size = 7
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
    scorecards.clear()
    await broadcast({"type": "room_state", "data": serialize_room_state()})
    await broadcast({"type": "scoreboard", "data": serialize_scoreboard()})
    return serialize_room_state()


@app.post("/api/draft/timer")
async def update_timer(req: UpdateTimerReq):
    u = ROOM.users.get(req.userId)
    if not u or not u.is_host:
        raise HTTPException(status_code=403, detail="Only host can change the timer.")

    new_seconds = int(req.seconds_per_pick)
    if new_seconds < 5 or new_seconds > 300:
        raise HTTPException(status_code=400, detail="Timer must be between 5 and 300 seconds.")

    ROOM.draft.config.seconds_per_pick = new_seconds

    if ROOM.draft.started and not ROOM.draft.completed:
        ROOM.draft.deadline_ts = time.time() + new_seconds

    state_out = serialize_room_state()
    await broadcast({"type": "room_state", "data": state_out})
    return state_out


@app.post("/api/draft/auto-pick")
async def auto_pick(req: AutoPickReq):
    u = ROOM.users.get(req.userId)
    if not u:
        raise HTTPException(status_code=401, detail="Join first.")

    d = ROOM.draft
    if not d.started or d.completed:
        raise HTTPException(status_code=400, detail="Draft not active.")
    if d.current_team() != u.name:
        raise HTTPException(status_code=403, detail=f"Not your turn. On the clock: {d.current_team()}")

    picked = do_auto_pick_for_team(u.name)
    if not picked:
        raise HTTPException(status_code=400, detail="No valid auto-pick available.")

    state_out = serialize_room_state()
    await broadcast({"type": "room_state", "data": state_out})
    await broadcast({"type": "scoreboard", "data": serialize_scoreboard()})
    return state_out


@app.get("/api/draft/eligible-slots/{athlete_id}")
def eligible_slots(athlete_id: str, userId: str):
    u = ROOM.users.get(userId)
    if not u:
        raise HTTPException(status_code=401, detail="Join first.")
    d = ROOM.draft
    if not d.started or d.completed:
        raise HTTPException(status_code=400, detail="Draft not active.")
    player = PLAYER_MAP.get(athlete_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found.")
    return {"slots": d.eligible_slots(u.name, player)}


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

    player = PLAYER_MAP.get(req.athlete_id)
    if not player:
        raise HTTPException(status_code=400, detail="Player not in draft pool.")
    if req.athlete_id in d.picked_ids:
        raise HTTPException(status_code=409, detail="Already drafted.")

    valid_slots = d.eligible_slots(u.name, player)
    if not valid_slots:
        raise HTTPException(status_code=400, detail="Player does not fit any available slot.")

    slot = req.slot
    if slot is None:
        if len(valid_slots) != 1:
            return {
                "needsSlotSelection": True,
                "slots": valid_slots,
                "slotLabels": {s: SLOT_LABELS[s] for s in valid_slots},
                "player": player,
            }
        slot = valid_slots[0]

    try:
        d.make_pick(req.athlete_id, req.name, slot, player)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    state_out = serialize_room_state()
    await broadcast({"type": "room_state", "data": state_out})
    await broadcast({"type": "scoreboard", "data": serialize_scoreboard()})
    return state_out


@app.get("/api/scoreboard")
def scoreboard():
    return serialize_scoreboard()


@app.get("/api/tournament-leaderboard")
def tournament_leaderboard():
    return {"leaderboard": get_leaderboard()}


@app.get("/api/player/{athlete_id}/holes")
def player_holes(athlete_id: str):
    sc = scorecards.get(athlete_id)
    if not sc:
        return {
            "athleteId": athlete_id,
            "name": athlete_id.replace("-", " ").title(),
            "holes": [],
            "fantasyPoints": 0,
            "basePoints": 0,
            "bonusPoints": 0,
            "placementBonus": 0,
            "scoringHighlights": [],
            "baseBreakdown": {},
            "bonusBreakdown": {},
            "placementBreakdown": {},
            "roundPoints": {},
            "madeCut": None,
        }

    return {
        "athleteId": sc.athlete_id,
        "name": sc.name,
        "fantasyPoints": sc.fantasy_points,
        "basePoints": sc.hole_points,
        "bonusPoints": sc.bonus_points,
        "placementBonus": sc.placement_bonus,
        "madeCut": sc.made_cut,
        "scoringHighlights": sc.scoring_highlights,
        "baseBreakdown": sc.round_base_breakdown,
        "bonusBreakdown": sc.round_bonus_breakdown,
        "placementBreakdown": sc.placement_breakdown,
        "roundPoints": sc.round_points,
        "holes": [
            {
                "round": h.round,
                "hole": h.hole,
                "par": h.par,
                "strokes": h.strokes,
                "result": h.result,
                "points": h.points,
                "bonusPoints": h.bonus_points,
                "totalPoints": round(h.points + h.bonus_points, 2),
            }
            for h in sc.holes
        ],
        "updatedTs": sc.updated_ts,
    }


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