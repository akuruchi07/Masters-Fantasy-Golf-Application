from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


# Fantasy scoring per HOLE outcome.
# Edit as needed.
SCORING_RULES = {
    "hole_points": {
        "PAR": 0.5,
        "BIRDIE": 3.0,   
        "EAGLE": 8.0,    
        "ALBATROSS": 5.0,  
        "BOGEY": -0.5,    
        "DOUBLE_BOGEY": -1.0,  
        "TRIPLE_BOGEY_OR_WORSE": -1.0,  
    },
    "hole_in_one_bonus": 5.0,          
    "bogey_free_round_bonus": 3.0,     
    "consecutive_birdies_bonus": 1.0,  
    "consecutive_bogeys_bonus": -1.0,   
    "finishing_points": [
        {"min": 1, "max": 1, "points": 20.0},
        {"min": 2, "max": 2, "points": 18.0},
        {"min": 3, "max": 3, "points": 16.0},
        {"min": 4, "max": 4, "points": 14.0},
        {"min": 5, "max": 5, "points": 12.0},
        {"min": 6, "max": 6, "points": 10.0},
        {"min": 7, "max": 7, "points": 8.0},
        {"min": 8, "max": 8, "points": 7.0},
        {"min": 9, "max": 9, "points": 6.0},
        {"min": 10, "max": 10, "points": 5.0},
        {"min": 11, "max": 15, "points": 4.0},
        {"min": 16, "max": 20, "points": 3.0},
        {"min": 21, "max": 25, "points": 2.0},
    ]
}

def classify_result(strokes: Optional[int], par: Optional[int]) -> str:
    if strokes is None or par is None:
        return "OTHER"

    diff = strokes - par

    if diff <= -3:
        return "ALBATROSS"
    if diff == -2:
        return "EAGLE"
    if diff == -1:
        return "BIRDIE"
    if diff == 0:
        return "PAR"
    if diff == 1:
        return "BOGEY"
    if diff == 2:
        return "DOUBLE_BOGEY"
    return "TRIPLE_BOGEY_OR_WORSE"

def points_for_hole(strokes: Optional[int], par: Optional[int]) -> int: 
    result = classify_result(strokes, par) 
    return SCORING_RULES.get(
        result, SCORING_RULES["OTHER"])
    


def score_round(holes):
    total = 0
    '''
    holes = list of dict:
    [{"strokes": 4, "par": 5}, ...]
    '''
    for hole in holes:
        total += points_for_hole(
            hole.get("strokes"),
            hole.get('par')
        )
    return total

def score_golfer_tournament(rounds):
    '''
    rounds = list of rounds
    each round = list of holes
    '''
    total = 0

    for data in rounds:
        total = score_round(data)
    return total

def get_finishing_bonus(position: Optional[int], finishing_rules: List[Dict[str, Any]]) -> float:
    if position is None:
        return 0.0

    for rule in finishing_rules:
        if rule["min"] <= position <= rule["max"]:
            return rule["points"]

    return 0.0

def score_golfer(golfer_data: Dict[str, Any], scoring_rules: Dict[str, Any]) -> Dict[str, Any]:
    """
    golfer_data example:
    {
        "name": "Scottie Scheffler",
        "rounds": [
            [
                {"hole": 1, "par": 4, "strokes": 4},
                {"hole": 2, "par": 5, "strokes": 4},
                {"hole": 3, "par": 3, "strokes": 2}
            ],
            [
                {"hole": 1, "par": 4, "strokes": 5}
            ]
        ],
        "finishing_position": 12
    }

    scoring_rules example:
    {
        "hole_points": {
            "PAR": 0.5,
            "BIRDIE": 3,
            "EAGLE": 8,
            "ALBATROSS": 13,
            "BOGEY": -1,
            "DOUBLE_BOGEY": -3,
            "TRIPLE_BOGEY_OR_WORSE": -4,
            "HOLE_IN_ONE": 10
        },
        "bogey_free_round_bonus": 3,
        "consecutive_birdies_bonus": 3,
        "consecutive_bogeys_bonus": -3,
        "hole_in_one_bonus": 10,
        "finishing_points": [
            {"min": 1, "max": 1, "points": 30},
            {"min": 2, "max": 2, "points": 20},
            {"min": 3, "max": 3, "points": 18},
            {"min": 4, "max": 4, "points": 16},
            {"min": 5, "max": 5, "points": 14},
            {"min": 6, "max": 6, "points": 12},
            {"min": 7, "max": 7, "points": 10},
            {"min": 8, "max": 8, "points": 9},
            {"min": 9, "max": 9, "points": 8},
            {"min": 10, "max": 10, "points": 7},
            {"min": 11, "max": 15, "points": 5},
            {"min": 16, "max": 20, "points": 3},
            {"min": 21, "max": 25, "points": 1}
        ]
    }
    """

    stats = {
        "pars": 0,
        "birdies": 0,
        "eagles": 0,
        "albatrosses": 0,
        "bogeys": 0,
        "double_bogeys": 0,
        "triple_bogeys_or_worse": 0,
        "hole_in_ones": 0,
        "bogey_free_rounds": 0,
        "consecutive_birdie_streaks": 0,
        "consecutive_bogey_streaks": 0,
        "holes_completed": 0,
        "score_to_par": 0,
        "finishing_position": golfer_data.get("finishing_position"),
    }
    # Initialize
    base_points = 0.0
    bonus_points = 0.0

    rounds = golfer_data.get("rounds", [])

    # Scoring Logic
    for round_data in rounds:
        round_has_bogey_or_worse = False
        consecutive_birdies = 0
        consecutive_bogeys = 0

        for hole in round_data:
            strokes = hole.get("strokes")
            par = hole.get("par")
            hole_in_one = hole.get("hole_in_one", False)

            if strokes is None or par is None:
                continue

            stats["holes_completed"] += 1
            stats["score_to_par"] += (strokes - par)

            result = classify_result(strokes, par)
            base_points += scoring_rules["hole_points"].get(result, 0)

            if hole_in_one:
                stats["hole_in_ones"] += 1
                bonus_points += scoring_rules.get("hole_in_one_bonus", 0)

            if result == "PAR":
                stats["pars"] += 1
                consecutive_birdies = 0
                consecutive_bogeys = 0

            elif result == "BIRDIE":
                stats["birdies"] += 1
                consecutive_birdies += 1
                consecutive_bogeys = 0

                if consecutive_birdies == 3:
                    stats["consecutive_birdie_streaks"] += 1
                    bonus_points += scoring_rules.get("consecutive_birdies_bonus", 0)
                    consecutive_birdies = 0

            elif result == "EAGLE":
                stats["eagles"] += 1
                consecutive_birdies = 0
                consecutive_bogeys = 0

            elif result == "ALBATROSS":
                stats["albatrosses"] += 1
                consecutive_birdies = 0
                consecutive_bogeys = 0

            elif result == "BOGEY":
                stats["bogeys"] += 1
                round_has_bogey_or_worse = True
                consecutive_bogeys += 1
                consecutive_birdies = 0

                if consecutive_bogeys == 3:
                    stats["consecutive_bogey_streaks"] += 1
                    bonus_points += scoring_rules.get("consecutive_bogeys_bonus", 0)
                    consecutive_bogeys = 0

            elif result == "DOUBLE_BOGEY":
                stats["double_bogeys"] += 1
                round_has_bogey_or_worse = True
                consecutive_birdies = 0
                consecutive_bogeys = 0

            elif result == "TRIPLE_BOGEY_OR_WORSE":
                stats["triple_bogeys_or_worse"] += 1
                round_has_bogey_or_worse = True
                consecutive_birdies = 0
                consecutive_bogeys = 0

        if round_data and not round_has_bogey_or_worse:
            stats["bogey_free_rounds"] += 1
            bonus_points += scoring_rules.get("bogey_free_round_bonus", 0)

    finishing_bonus = get_finishing_bonus(
        golfer_data.get("finishing_position"),
        scoring_rules.get("finishing_points", [])
    )
    bonus_points += finishing_bonus

    total_points = base_points + bonus_points

    return {
        "golfer_name": golfer_data.get("name"),
        "fantasy_points": round(total_points, 2),
        "base_points": round(base_points, 2),
        "bonus_points": round(bonus_points, 2),
        "stats": stats,
    }


