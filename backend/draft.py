from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

@dataclass
class DraftConfig:
    roster_size: int = 6
    seconds_per_pick: int = 60
    snake: bool = True
    auto_pick: bool = True

@dataclass
class Pick:
    pick_no: int
    team: str
    athlete_id: str
    name: str
    ts: float

@dataclass
class DraftState:
    config: DraftConfig
    teams: List[str] = field(default_factory=list)  # ordered draft order
    started: bool = False
    completed: bool = False

    total_picks: int = 0
    pick_no: int = 1
    direction: int = 1
    team_index: int = 0
    deadline_ts: Optional[float] = None

    picks: List[Pick] = field(default_factory=list)
    rosters: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)
    picked_ids: set[str] = field(default_factory=set)

    def reset_for_teams(self, teams_in_order: List[str]):
        self.teams = list(teams_in_order)
        self.started = False
        self.completed = False
        self.total_picks = len(self.teams) * self.config.roster_size
        self.pick_no = 1
        self.direction = 1
        self.team_index = 0
        self.deadline_ts = None
        self.picks = []
        self.rosters = {t: [] for t in self.teams}
        self.picked_ids = set()

    def start(self):
        if not self.teams:
            raise ValueError("No users in draft.")
        self.started = True
        self.completed = False
        self.deadline_ts = time.time() + self.config.seconds_per_pick

    def current_team(self) -> Optional[str]:
        if not self.started or self.completed or not self.teams:
            return None
        return self.teams[self.team_index]

    def is_team_full(self, team: str) -> bool:
        return len(self.rosters.get(team, [])) >= self.config.roster_size

    def advance_turn(self):
        self.pick_no += 1
        if self.pick_no > self.total_picks:
            self.completed = True
            self.deadline_ts = None
            return

        if not self.config.snake:
            self.team_index = (self.team_index + 1) % len(self.teams)
        else:
            nxt = self.team_index + self.direction
            if nxt < 0 or nxt >= len(self.teams):
                self.direction *= -1
                nxt = self.team_index + self.direction
            self.team_index = nxt

        self.deadline_ts = time.time() + self.config.seconds_per_pick

    def make_pick(self, athlete_id: str, name: str) -> Pick:
        if not self.started or self.completed:
            raise ValueError("Draft not active.")
        team = self.current_team()
        if team is None:
            raise ValueError("No team on the clock.")
        if self.is_team_full(team):
            raise ValueError("Team roster full.")
        if athlete_id in self.picked_ids:
            raise ValueError("Already drafted.")

        p = Pick(
            pick_no=self.pick_no,
            team=team,
            athlete_id=athlete_id,
            name=name,
            ts=time.time(),
        )
        self.picks.append(p)
        self.rosters[team].append((athlete_id, name))
        self.picked_ids.add(athlete_id)
        self.advance_turn()
        return p

    def remaining_seconds(self) -> Optional[int]:
        if not self.started or self.completed or self.deadline_ts is None:
            return None
        return max(0, int(self.deadline_ts - time.time()))