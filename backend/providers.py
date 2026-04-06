from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import time

from scoring import classify_result, points_for_hole

@dataclass
class Hole:
    round: int
    hole: int
    par: Optional[int]
    strokes: Optional[int]

    @property
    def result(self) -> str:
        return classify_result(self.strokes, self.par)

    @property
    def points(self) -> int:
        return points_for_hole(self.strokes, self.par)

@dataclass
class PlayerScorecard:
    athlete_id: str
    name: str
    holes: List[Hole]
    updated_ts: float

    @property
    def fantasy_points(self) -> int:
        return sum(h.points for h in self.holes)

class ScoreProvider:
    def fetch_many(self, athlete_ids: List[str]) -> Dict[str, PlayerScorecard]:
        raise NotImplementedError

class StubProvider(ScoreProvider):
    """
    Fake scoring that changes over time so you can test live updates.
    Replace with a real Masters provider later.
    """
    def __init__(self):
        self._tick = 0

    def fetch_many(self, athlete_ids: List[str]) -> Dict[str, PlayerScorecard]:
        self._tick += 1
        out: Dict[str, PlayerScorecard] = {}
        for i, aid in enumerate(athlete_ids):
            holes: List[Hole] = []
            played = min(18, max(0, (self._tick + i) % 19))
            for h in range(1, played + 1):
                par = 4 if h % 3 else 3
                strokes = par + (h % 3) - 1  # -1,0,+1
                holes.append(Hole(round=1, hole=h, par=par, strokes=strokes))
            out[aid] = PlayerScorecard(
                athlete_id=aid,
                name=aid.replace("-", " ").title(),
                holes=holes,
                updated_ts=time.time(),
            )
        return out