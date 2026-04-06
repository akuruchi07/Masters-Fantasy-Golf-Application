from dataclasses import dataclass
import time
from typing import Dict, List, Optional

from draft import BACKUP_SLOTS, SLOT_LABELS, STARTER_SLOTS
from scraper import fetch_espn_leaderboard, map_espn_field
from scoring import SCORING_RULES, classify_result, score_field


@dataclass
class HoleScore:
    round: int
    hole: int
    par: int
    strokes: int
    result: str
    points: float


@dataclass
class LivePlayerScorecard:
    athlete_id: str
    name: str
    fantasy_points: float
    holes: List[HoleScore]
    updated_ts: float
    made_cut: bool
    round_points: Dict[int, float]


def get_leaderboard():
    data = fetch_espn_leaderboard()
    golfers = map_espn_field(data)
    scored_field = score_field(golfers, SCORING_RULES)
    leaderboard = sorted(scored_field, key=lambda x: x["fantasy_points"], reverse=True)
    return leaderboard


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


def points_for_result(result: str) -> float:
    return SCORING_RULES["hole_points"].get(result, 0)


def build_hole_list(rounds: List[List[dict]]) -> List[HoleScore]:
    holes_out: List[HoleScore] = []
    for index, data in enumerate(rounds, start=1):
        for hole in data:
            strokes = hole.get("strokes")
            par = hole.get("par")
            if strokes is None or par is None:
                continue
            result = classify_result(strokes, par)
            holes_out.append(
                HoleScore(
                    round=index,
                    hole=hole.get("hole"),
                    par=par,
                    strokes=strokes,
                    result=result,
                    points=points_for_result(result),
                )
            )
    return holes_out


def round_points_from_holes(holes: List[HoleScore]) -> Dict[int, float]:
    out: Dict[int, float] = {}
    for hole in holes:
        out[hole.round] = round(out.get(hole.round, 0.0) + hole.points, 2)
    return out


def infer_made_cut(raw_golfer: dict) -> bool:
    status = (raw_golfer.get("status") or {}).get("type", {}) if isinstance(raw_golfer.get("status"), dict) else {}
    status_name = str(status.get("name") or "").lower()
    status_state = str(status.get("state") or "").lower()
    detail = str(status.get("detail") or "").lower()

    if "cut" in detail and "made" not in detail:
        return False
    if status_name in {"cut", "missed_cut"}:
        return False
    if status_state in {"post", "complete"}:
        return True

    rounds = raw_golfer.get("rounds") or []
    rounds_completed = sum(1 for rnd in rounds if any(h.get("strokes") is not None for h in rnd))
    if rounds_completed >= 3:
        return True

    if rounds_completed < 2:
        return False

    return True


def fetch_live_scorecards() -> Dict[str, LivePlayerScorecard]:
    data = fetch_espn_leaderboard()
    golfers = map_espn_field(data)
    scored = score_field(golfers, SCORING_RULES)

    out: Dict[str, LivePlayerScorecard] = {}
    for raw_golfer, scored_golfer in zip(golfers, scored):
        athlete_id = slugify(raw_golfer["name"])
        holes = build_hole_list(raw_golfer["rounds"])
        out[athlete_id] = LivePlayerScorecard(
            athlete_id=athlete_id,
            name=raw_golfer["name"],
            fantasy_points=scored_golfer["fantasy_points"],
            holes=holes,
            updated_ts=time.time(),
            made_cut=infer_made_cut(raw_golfer),
            round_points=round_points_from_holes(holes),
        )
    return out


def build_team_scoreboard(rosters: Dict[str, Dict[str, Optional[dict]]], scorecards: Dict[str, LivePlayerScorecard]) -> Dict[str, dict]:
    teams_out: Dict[str, dict] = {}

    for team, roster in rosters.items():
        missed_starters: List[str] = []
        for slot in STARTER_SLOTS:
            player = roster.get(slot)
            if not player:
                continue
            sc = scorecards.get(player["athleteId"])
            if sc and not sc.made_cut:
                missed_starters.append(slot)

        active_backups = set(BACKUP_SLOTS[: min(len(missed_starters), len(BACKUP_SLOTS))])
        total = 0.0
        players_out: List[dict] = []

        for slot_name, slot_label in SLOT_LABELS.items():
            player = roster.get(slot_name)
            if not player:
                players_out.append(
                    {
                        "slot": slot_name,
                        "slotLabel": slot_label,
                        "athleteId": None,
                        "name": None,
                        "fantasyPoints": 0,
                        "roundPoints": {},
                        "madeCut": None,
                        "isBackup": slot_name in BACKUP_SLOTS,
                        "isActive": False,
                        "status": "empty",
                    }
                )
                continue

            sc = scorecards.get(player["athleteId"])
            round_points = sc.round_points if sc else {}
            made_cut = sc.made_cut if sc else None
            is_backup = slot_name in BACKUP_SLOTS
            is_active_backup = slot_name in active_backups and bool(sc and sc.made_cut)

            if is_backup:
                fantasy_points = round((round_points.get(3, 0.0) + round_points.get(4, 0.0)) if is_active_backup else 0.0, 2)
                status = "active_backup" if is_active_backup else "bench"
            else:
                fantasy_points = round(
                    round_points.get(1, 0.0)
                    + round_points.get(2, 0.0)
                    + (round_points.get(3, 0.0) + round_points.get(4, 0.0) if sc and sc.made_cut else 0.0),
                    2,
                )
                status = "missed_cut" if sc and not sc.made_cut else "starter"

            total += fantasy_points
            players_out.append(
                {
                    "slot": slot_name,
                    "slotLabel": slot_label,
                    "athleteId": player["athleteId"],
                    "name": player["name"],
                    "fantasyPoints": fantasy_points,
                    "roundPoints": round_points,
                    "madeCut": made_cut,
                    "isBackup": is_backup,
                    "isActive": is_active_backup or not is_backup,
                    "status": status,
                }
            )

        teams_out[team] = {
            "total": round(total, 2),
            "players": players_out,
            "missedStarterSlots": missed_starters,
        }

    return teams_out