from dataclasses import dataclass
import time
from typing import Dict, List, Optional, Tuple

from draft import BACKUP_SLOTS, SLOT_LABELS, STARTER_SLOTS
from scraper import fetch_espn_leaderboard, map_espn_field


HOLE_POINTS = {
    "albatross": 20.0,
    "eagle": 8.0,
    "birdie": 3.0,
    "par": 0.5,
    "bogey": -0.5,
    "double_bogey": -1.0,
    "worse": -1.0,
}

THREE_BIRDIES_STREAK_BONUS = 3.0
BOGEY_FREE_ROUND_BONUS = 3.0
UNDER_70_ROUND_BONUS = 5.0
HOLE_IN_ONE_BONUS = 10.0


BASE_BREAKDOWN_META = {
    "albatross": {"label": "Albatross", "pointsEach": HOLE_POINTS["albatross"]},
    "eagle": {"label": "Eagle", "pointsEach": HOLE_POINTS["eagle"]},
    "birdie": {"label": "Birdie", "pointsEach": HOLE_POINTS["birdie"]},
    "par": {"label": "Par", "pointsEach": HOLE_POINTS["par"]},
    "bogey": {"label": "Bogey", "pointsEach": HOLE_POINTS["bogey"]},
    "double_bogey_or_worse": {"label": "Double Bogey or Worse", "pointsEach": HOLE_POINTS["double_bogey"]},
}

BONUS_BREAKDOWN_META = {
    "three_birdies_streak": {"label": "3 Birdies in a Row", "pointsEach": THREE_BIRDIES_STREAK_BONUS},
    "bogey_free_round": {"label": "Bogey-Free Round", "pointsEach": BOGEY_FREE_ROUND_BONUS},
    "under_70_round": {"label": "Under 70 Round", "pointsEach": UNDER_70_ROUND_BONUS},
    "hole_in_one": {"label": "Hole-in-One", "pointsEach": HOLE_IN_ONE_BONUS},
}


@dataclass
class HoleScore:
    round: int
    hole: int
    par: int
    strokes: int
    result: str
    points: float
    bonus_points: float


@dataclass
class LivePlayerScorecard:
    athlete_id: str
    name: str
    fantasy_points: float
    holes: List[HoleScore]
    updated_ts: float
    made_cut: Optional[bool]
    round_points: Dict[int, float]
    round_hole_points: Dict[int, float]
    round_bonus_points: Dict[int, float]
    hole_points: float
    bonus_points: float
    placement_bonus: float
    scoring_highlights: List[str]
    round_base_breakdown: Dict[int, Dict[str, dict]]
    round_bonus_breakdown: Dict[int, Dict[str, dict]]
    placement_breakdown: Dict[str, dict]
    rank: Optional[int]


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


def classify_result(strokes: int, par: int) -> str:
    diff = strokes - par
    if diff <= -3:
        return "albatross"
    if diff == -2:
        return "eagle"
    if diff == -1:
        return "birdie"
    if diff == 0:
        return "par"
    if diff == 1:
        return "bogey"
    if diff == 2:
        return "double_bogey"
    return "worse"


def points_for_result(result: str) -> float:
    return HOLE_POINTS.get(result, 0.0)


def infer_made_cut(raw_golfer: dict) -> Optional[bool]:
    status = (raw_golfer.get("status") or {}).get("type", {}) if isinstance(raw_golfer.get("status"), dict) else {}
    status_name = str(status.get("name") or "").lower()
    status_state = str(status.get("state") or "").lower()
    detail = str(status.get("detail") or "").lower()

    rounds = raw_golfer.get("rounds") or []
    rounds_completed = sum(1 for rnd in rounds if any(h.get("strokes") is not None for h in rnd))

    if "made cut" in detail:
        return True
    if "missed cut" in detail or (("cut" in detail) and ("made" not in detail)):
        return False
    if status_name in {"cut", "missed_cut"}:
        return False
    if rounds_completed >= 3:
        return True

    # Before the cut is official after Friday, treat as unknown.
    if rounds_completed < 2:
        return None

    # If exactly two rounds are complete but no explicit cut result, still unknown.
    if rounds_completed == 2 and status_state not in {"post", "complete"}:
        return None

    return None


def placement_bonus(rank: int) -> float:
    if rank == 1:
        return 30.0
    if rank == 2:
        return 20.0
    if rank == 3:
        return 18.0
    if rank == 4:
        return 16.0
    if rank == 5:
        return 14.0
    if 6 <= rank <= 10:
        return 10.0
    if 11 <= rank <= 15:
        return 8.0
    if 16 <= rank <= 20:
        return 6.0
    if 21 <= rank <= 25:
        return 4.0
    return 0.0


def parse_position_value(raw_golfer: dict) -> Optional[int]:
    for key in ("position", "pos", "rank"):
        value = raw_golfer.get(key)
        if value is None:
            continue
        if isinstance(value, int):
            return value
        s = str(value).strip().upper().replace("T", "")
        if s.isdigit():
            return int(s)
    return None


def round_complete(holes: List[dict]) -> bool:
    played = [h for h in holes if h.get("strokes") is not None and h.get("par") is not None]
    return len(played) >= 18


def empty_base_breakdown():
    return {
        key: {
            "label": value["label"],
            "count": 0,
            "pointsEach": value["pointsEach"],
            "total": 0.0,
        }
        for key, value in BASE_BREAKDOWN_META.items()
    }


def empty_bonus_breakdown():
    return {
        key: {
            "label": value["label"],
            "count": 0,
            "pointsEach": value["pointsEach"],
            "total": 0.0,
        }
        for key, value in BONUS_BREAKDOWN_META.items()
    }


def add_breakdown_dicts(target: Dict[str, dict], source: Dict[str, dict]):
    for key, src in source.items():
        if key not in target:
            target[key] = {
                "label": src.get("label", key),
                "count": 0,
                "pointsEach": src.get("pointsEach", 0),
                "total": 0.0,
            }
        target[key]["count"] += src.get("count", 0)
        target[key]["total"] = round(target[key]["total"] + src.get("total", 0.0), 2)


def build_hole_scores(rounds: List[List[dict]]) -> Tuple[List[HoleScore], Dict[int, List[HoleScore]], Dict[int, Dict[str, dict]]]:
    holes_out: List[HoleScore] = []
    grouped: Dict[int, List[HoleScore]] = {}
    round_base_breakdown: Dict[int, Dict[str, dict]] = {}

    for round_index, hole_list in enumerate(rounds, start=1):
        grouped.setdefault(round_index, [])
        round_base_breakdown[round_index] = empty_base_breakdown()

        for hole in hole_list:
            strokes = hole.get("strokes")
            par = hole.get("par")
            hole_num = hole.get("hole")
            if strokes is None or par is None or hole_num is None:
                continue

            result = classify_result(strokes, par)
            base_points = points_for_result(result)
            bonus_points = 0.0

            if strokes == 1 and par >= 3:
                bonus_points += HOLE_IN_ONE_BONUS

            hs = HoleScore(
                round=round_index,
                hole=int(hole_num),
                par=int(par),
                strokes=int(strokes),
                result=result,
                points=base_points,
                bonus_points=bonus_points,
            )
            holes_out.append(hs)
            grouped[round_index].append(hs)

            key = "double_bogey_or_worse" if result in {"double_bogey", "worse"} else result
            round_base_breakdown[round_index][key]["count"] += 1
            round_base_breakdown[round_index][key]["total"] = round(
                round_base_breakdown[round_index][key]["total"] + base_points, 2
            )

    return holes_out, grouped, round_base_breakdown


def compute_round_bonuses(round_num: int, holes: List[HoleScore]) -> Tuple[float, List[str], Dict[str, dict]]:
    if not holes:
        return 0.0, [], empty_bonus_breakdown()

    bonus = 0.0
    highlights: List[str] = []
    breakdown = empty_bonus_breakdown()

    ace_count = sum(1 for h in holes if h.bonus_points > 0)
    if ace_count:
        ace_total = sum(h.bonus_points for h in holes if h.bonus_points > 0)
        bonus += ace_total
        breakdown["hole_in_one"]["count"] += ace_count
        breakdown["hole_in_one"]["total"] = round(breakdown["hole_in_one"]["total"] + ace_total, 2)
        highlights.append(f"{ace_count} Hole-in-One" if ace_count > 1 else "Hole-in-One")

    streak = 0
    streak_awarded = False
    streak_count = 0
    for h in holes:
        if h.result == "birdie":
            streak += 1
            if streak >= 3 and not streak_awarded:
                bonus += THREE_BIRDIES_STREAK_BONUS
                streak_count += 1
                streak_awarded = True
        else:
            streak = 0
            streak_awarded = False

    if streak_count:
        breakdown["three_birdies_streak"]["count"] += streak_count
        breakdown["three_birdies_streak"]["total"] = round(
            breakdown["three_birdies_streak"]["total"] + streak_count * THREE_BIRDIES_STREAK_BONUS, 2
        )
        highlights.append(f"{streak_count} Birdie Streak Bonus" if streak_count > 1 else "Birdie Streak Bonus")

    if round_complete([{"strokes": h.strokes, "par": h.par} for h in holes]):
        if all(h.result not in {"bogey", "double_bogey", "worse"} for h in holes):
            bonus += BOGEY_FREE_ROUND_BONUS
            breakdown["bogey_free_round"]["count"] += 1
            breakdown["bogey_free_round"]["total"] = round(
                breakdown["bogey_free_round"]["total"] + BOGEY_FREE_ROUND_BONUS, 2
            )
            highlights.append("Bogey-Free Round")

        total_strokes = sum(h.strokes for h in holes)
        if total_strokes < 70:
            bonus += UNDER_70_ROUND_BONUS
            breakdown["under_70_round"]["count"] += 1
            breakdown["under_70_round"]["total"] = round(
                breakdown["under_70_round"]["total"] + UNDER_70_ROUND_BONUS, 2
            )
            highlights.append("Under 70")

    return round(bonus, 2), highlights, breakdown


def score_one_golfer(raw_golfer: dict, placement_points: float = 0.0, rank: Optional[int] = None) -> LivePlayerScorecard:
    athlete_id = slugify(raw_golfer["name"])
    rounds = raw_golfer.get("rounds") or []

    holes, holes_by_round, round_base_breakdown = build_hole_scores(rounds)

    round_hole_points: Dict[int, float] = {}
    round_bonus_points: Dict[int, float] = {}
    round_points: Dict[int, float] = {}
    scoring_highlights: List[str] = []
    round_bonus_breakdown: Dict[int, Dict[str, dict]] = {}

    for round_num, round_holes in holes_by_round.items():
        hole_points = round(sum(h.points for h in round_holes), 2)
        bonus_points, round_highlights, bonus_breakdown = compute_round_bonuses(round_num, round_holes)

        round_hole_points[round_num] = hole_points
        round_bonus_points[round_num] = round(bonus_points, 2)
        round_points[round_num] = round(hole_points + bonus_points, 2)
        round_bonus_breakdown[round_num] = bonus_breakdown
        scoring_highlights.extend(round_highlights)

    total_hole_points = round(sum(round_hole_points.values()), 2)
    total_bonus_points = round(sum(round_bonus_points.values()), 2)
    total_points = round(total_hole_points + total_bonus_points + placement_points, 2)

    placement_breakdown = {
        "placement_bonus": {
            "label": "Placement Bonus",
            "count": 1 if placement_points > 0 else 0,
            "pointsEach": placement_points if placement_points > 0 else 0.0,
            "total": round(placement_points, 2),
            "rank": rank,
        }
    }

    if placement_points > 0:
        scoring_highlights.append(f"Placement Bonus (+{int(placement_points)})")

    return LivePlayerScorecard(
        athlete_id=athlete_id,
        name=raw_golfer["name"],
        fantasy_points=total_points,
        holes=holes,
        updated_ts=time.time(),
        made_cut=infer_made_cut(raw_golfer),
        round_points=round_points,
        round_hole_points=round_hole_points,
        round_bonus_points=round_bonus_points,
        hole_points=total_hole_points,
        bonus_points=total_bonus_points,
        placement_bonus=round(placement_points, 2),
        scoring_highlights=scoring_highlights,
        round_base_breakdown=round_base_breakdown,
        round_bonus_breakdown=round_bonus_breakdown,
        placement_breakdown=placement_breakdown,
        rank=rank,
    )


def all_positions_final(golfers: List[dict]) -> bool:
    if not golfers:
        return False

    finished_count = 0
    for g in golfers:
        cut_status = infer_made_cut(g)
        status = (g.get("status") or {}).get("type", {}) if isinstance(g.get("status"), dict) else {}
        state = str(status.get("state") or "").lower()
        rounds = g.get("rounds") or []
        rounds_completed = sum(1 for rnd in rounds if any(h.get("strokes") is not None for h in rnd))

        if state in {"post", "complete"} or rounds_completed >= 4 or cut_status is False:
            finished_count += 1

    return finished_count == len(golfers)


def aggregate_breakdowns_for_rounds(round_breakdowns: Dict[int, Dict[str, dict]], rounds_to_use: List[int]) -> Dict[str, dict]:
    if not round_breakdowns:
        return {}

    sample = next(iter(round_breakdowns.values()), None)
    aggregated = {}
    if sample:
        for key, value in sample.items():
            aggregated[key] = {
                "label": value["label"],
                "count": 0,
                "pointsEach": value["pointsEach"],
                "total": 0.0,
            }

    for round_num in rounds_to_use:
        breakdown = round_breakdowns.get(round_num, {})
        add_breakdown_dicts(aggregated, breakdown)

    return aggregated


def get_leaderboard():
    data = fetch_espn_leaderboard()
    golfers = map_espn_field(data)

    apply_placement = all_positions_final(golfers)

    scored_players = []
    for idx, raw_golfer in enumerate(golfers, start=1):
        pos = parse_position_value(raw_golfer) or idx
        place_bonus = placement_bonus(pos) if apply_placement else 0.0
        sc = score_one_golfer(raw_golfer, place_bonus, pos)
        scored_players.append(
            {
                "athlete_id": sc.athlete_id,
                "golfer_name": sc.name,
                "base_points": sc.hole_points,
                "bonus_points": sc.bonus_points,
                "placement_bonus": sc.placement_bonus,
                "fantasy_points": sc.fantasy_points,
                "made_cut": sc.made_cut,
                "highlights": sc.scoring_highlights,
                "base_breakdown": aggregate_breakdowns_for_rounds(sc.round_base_breakdown, [1, 2, 3, 4]),
                "bonus_breakdown": aggregate_breakdowns_for_rounds(sc.round_bonus_breakdown, [1, 2, 3, 4]),
                "placement_breakdown": sc.placement_breakdown,
                "round_points": sc.round_points,
                "rank": sc.rank,
            }
        )

    scored_players.sort(key=lambda x: x["fantasy_points"], reverse=True)
    return scored_players


def fetch_live_scorecards() -> Dict[str, LivePlayerScorecard]:
    data = fetch_espn_leaderboard()
    golfers = map_espn_field(data)

    apply_placement = all_positions_final(golfers)

    out: Dict[str, LivePlayerScorecard] = {}
    for idx, raw_golfer in enumerate(golfers, start=1):
        pos = parse_position_value(raw_golfer) or idx
        place_bonus = placement_bonus(pos) if apply_placement else 0.0
        sc = score_one_golfer(raw_golfer, place_bonus, pos)
        out[sc.athlete_id] = sc
    return out


def build_team_scoreboard(
    rosters: Dict[str, Dict[str, Optional[dict]]],
    scorecards: Dict[str, LivePlayerScorecard],
) -> Dict[str, dict]:
    teams_out: Dict[str, dict] = {}

    for team, roster in rosters.items():
        missed_starters: List[str] = []
        for slot in STARTER_SLOTS:
            player = roster.get(slot)
            if not player:
                continue
            sc = scorecards.get(player["athleteId"])
            if sc and sc.made_cut is False:
                missed_starters.append(slot)

        active_backups = set(BACKUP_SLOTS[: min(len(missed_starters), len(BACKUP_SLOTS))])

        team_total = 0.0
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
                        "fantasyPoints": 0.0,
                        "basePoints": 0.0,
                        "bonusPoints": 0.0,
                        "placementBonus": 0.0,
                        "roundPoints": {},
                        "madeCut": None,
                        "isBackup": slot_name in BACKUP_SLOTS,
                        "isActive": False,
                        "status": "empty",
                        "scoringHighlights": [],
                        "baseBreakdown": {},
                        "bonusBreakdown": {},
                        "placementBreakdown": {},
                    }
                )
                continue

            sc = scorecards.get(player["athleteId"])
            is_backup = slot_name in BACKUP_SLOTS
            is_active_backup = slot_name in active_backups and bool(sc and sc.made_cut is True)

            if not sc:
                players_out.append(
                    {
                        "slot": slot_name,
                        "slotLabel": slot_label,
                        "athleteId": player["athleteId"],
                        "name": player["name"],
                        "fantasyPoints": 0.0,
                        "basePoints": 0.0,
                        "bonusPoints": 0.0,
                        "placementBonus": 0.0,
                        "roundPoints": {},
                        "madeCut": None,
                        "isBackup": is_backup,
                        "isActive": is_active_backup or not is_backup,
                        "status": "bench" if is_backup else "starter",
                        "scoringHighlights": [],
                        "baseBreakdown": {},
                        "bonusBreakdown": {},
                        "placementBreakdown": {},
                    }
                )
                continue

            if is_backup:
                rounds_to_use = [3, 4] if is_active_backup else []
                placement_points = sc.placement_bonus if is_active_backup else 0.0
                status = "active_backup" if is_active_backup else "bench"
            else:
                rounds_to_use = [1, 2, 3, 4] if sc.made_cut is True else ([1, 2] if sc.made_cut is False else [1, 2])
                placement_points = sc.placement_bonus if sc.made_cut is True else 0.0
                status = "missed_cut" if sc.made_cut is False else "starter"

            base_breakdown = aggregate_breakdowns_for_rounds(sc.round_base_breakdown, rounds_to_use)
            bonus_breakdown = aggregate_breakdowns_for_rounds(sc.round_bonus_breakdown, rounds_to_use)

            base_points = round(sum(v["total"] for v in base_breakdown.values()), 2)
            bonus_points = round(sum(v["total"] for v in bonus_breakdown.values()), 2)
            placement_breakdown = (
                {
                    "placement_bonus": {
                        "label": "Placement Bonus",
                        "count": 1 if placement_points > 0 else 0,
                        "pointsEach": placement_points if placement_points > 0 else 0.0,
                        "total": round(placement_points, 2),
                        "rank": sc.rank,
                    }
                }
                if placement_points > 0
                else {}
            )
            fantasy_points = round(base_points + bonus_points + placement_points, 2)

            team_total += fantasy_points

            players_out.append(
                {
                    "slot": slot_name,
                    "slotLabel": slot_label,
                    "athleteId": player["athleteId"],
                    "name": player["name"],
                    "fantasyPoints": fantasy_points,
                    "basePoints": base_points,
                    "bonusPoints": bonus_points,
                    "placementBonus": round(placement_points, 2),
                    "roundPoints": {r: sc.round_points.get(r, 0.0) for r in rounds_to_use},
                    "madeCut": sc.made_cut,
                    "isBackup": is_backup,
                    "isActive": is_active_backup or not is_backup,
                    "status": status,
                    "scoringHighlights": sc.scoring_highlights,
                    "baseBreakdown": base_breakdown,
                    "bonusBreakdown": bonus_breakdown,
                    "placementBreakdown": placement_breakdown,
                }
            )

        teams_out[team] = {
            "total": round(team_total, 2),
            "players": players_out,
            "missedStarterSlots": missed_starters,
        }

    return teams_out