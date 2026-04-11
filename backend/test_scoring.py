from scoring import score_golfer, SCORING_RULES
from scraper import fetch_espn_leaderboard, map_espn_field, map_espn_golfer
from leaderboard import get_leaderboard, fetch_live_scorecards

data = fetch_espn_leaderboard()
competitors = data["events"][0]["competitions"][0]["competitors"]

for raw in competitors:
    golfer = map_espn_golfer(raw)
    if golfer["name"] in ["Nicolai Højgaard", "Jason Day"]:
        rounds = golfer.get("rounds", [])
        played_rounds = sum(
            1 for rnd in rounds
            if any(h.get("strokes") is not None for h in rnd)
        )

        round3_started = (
            len(rounds) >= 3 and
            any(h.get("strokes") is not None for h in rounds[2])
        )

        print("\n=== DEBUG ===")
        print("Name:", golfer["name"])
        print("Played rounds:", played_rounds)
        print("Round 3 started:", round3_started)
        print("Rounds:", rounds)

'''
data = fetch_espn_leaderboard()
golfers = map_espn_field(data)

print("Number of golfers:", len(golfers))
print(type(golfers))
print(golfers)
assert isinstance(golfers, list)
assert len(golfers) > 0

first = golfers[0]

print("First mapped golfer:")
print(first)

assert "name" in first
assert "rounds" in first
assert "finishing_position" in first
assert "score_to_par" in first

assert isinstance(first["name"], str)
assert isinstance(first["rounds"], list)
assert isinstance(first["score_to_par"], int)

if first["rounds"]:
    assert isinstance(first["rounds"][0], list)
    if first["rounds"][0]:
        hole = first["rounds"][0][0]
        assert "hole" in hole
        assert "strokes" in hole
        assert "par" in hole
        assert "hole_in_one" in hole

result = score_golfer(first, SCORING_RULES)

print("Scored result:")
print(result)

assert "golfer_name" in result
assert "fantasy_points" in result
assert "stats" in result

print("All tests passed.")

# Simple test golfer
golfer_data = {
    "name": "Drake Maye",
    "rounds": [
        [
            {"hole": 1, "par": 4, "strokes": 3},  # birdie
            {"hole": 2, "par": 5, "strokes": 4},  # birdie
            {"hole": 3, "par": 3, "strokes": 2},  # birdie → streak
            {"hole": 4, "par": 4, "strokes": 4},  # par
            {"hole": 5, "par": 4, "strokes": 5},  # bogey
        ]
    ],
    "finishing_position": 12
}


normalized_golfer = {
    "name": "Mikel Arteta",
    "rounds": [
        [
            {"hole": 1, "par": 4, "strokes": 3, "hole_in_one": False},
            {"hole": 2, "par": 5, "strokes": 4, "hole_in_one": False},
        ]
    ],
    "finishing_position": None,
}
'''

'''
result_golf = score_golfer(golfer_data, SCORING_RULES)
result_norm = score_golfer(normalized_golfer, SCORING_RULES)

print("FINAL RESULT:")
print(result_golf)
print(result_norm)
'''

#result_norm = score_golfer(normalized_golfer, SCORING_RULES)
#print(result_norm)

#print(get_leaderboard()[:5])

#cards = fetch_live_scorecards()
#print(list(cards.items())[:2])