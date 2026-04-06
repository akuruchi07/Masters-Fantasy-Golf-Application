from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

STARTER_SLOTS = [
    "past_champion",
    "international",
    "american",
    "non_pga",
    "wildcard",
]
BACKUP_SLOTS = ["backup_1", "backup_2"]
ALL_SLOTS = STARTER_SLOTS + BACKUP_SLOTS

SLOT_LABELS = {
    "past_champion": "Past Masters Champion",
    "international": "International",
    "american": "American",
    "non_pga": "Non-PGA Tour",
    "wildcard": "Wildcard",
    "backup_1": "Backup 1",
    "backup_2": "Backup 2",
}


@dataclass
class DraftConfig:
    roster_size: int = 7
    seconds_per_pick: int = 60
    snake: bool = True
    auto_pick: bool = True


@dataclass
class Pick:
    pick_no: int
    team: str
    athlete_id: str
    name: str
    slot: str
    slot_label: str
    ts: float


@dataclass
class DraftState:
    config: DraftConfig
    teams: List[str] = field(default_factory=list)
    started: bool = False
    completed: bool = False

    total_picks: int = 0
    pick_no: int = 1
    direction: int = 1
    team_index: int = 0
    deadline_ts: Optional[float] = None

    picks: List[Pick] = field(default_factory=list)
    rosters: Dict[str, Dict[str, Optional[Dict[str, Any]]]] = field(default_factory=dict)
    picked_ids: set[str] = field(default_factory=set)

    def empty_roster(self) -> Dict[str, Optional[Dict[str, Any]]]:
        return {slot: None for slot in ALL_SLOTS}

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
        self.rosters = {t: self.empty_roster() for t in self.teams}
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

    def roster_for(self, team: str) -> Dict[str, Optional[Dict[str, Any]]]:
        return self.rosters.setdefault(team, self.empty_roster())

    def roster_count(self, team: str) -> int:
        return sum(1 for player in self.roster_for(team).values() if player is not None)

    def is_team_full(self, team: str) -> bool:
        return self.roster_count(team) >= self.config.roster_size

    def required_slots_filled(self, team: str) -> bool:
        roster = self.roster_for(team)
        return all(roster.get(slot) is not None for slot in STARTER_SLOTS)

    def roster_has_player(self, team: str, athlete_id: str) -> bool:
        roster = self.roster_for(team)
        return any(player and player.get("athleteId") == athlete_id for player in roster.values())

    def eligible_slots(self, team: str, player_meta: Dict[str, Any]) -> List[str]:
        roster = self.roster_for(team)
        valid: List[str] = []
        starters_done = self.required_slots_filled(team)

        for slot in ALL_SLOTS:
            if roster.get(slot) is not None:
                continue

            if slot == "past_champion" and player_meta.get("isPastChampion"):
                valid.append(slot)
            elif slot == "international" and player_meta.get("isInternational"):
                valid.append(slot)
            elif slot == "american" and player_meta.get("isAmerican"):
                valid.append(slot)
            elif slot == "non_pga" and player_meta.get("isNonPga"):
                valid.append(slot)
            elif slot == "wildcard":
                valid.append(slot)
            elif slot in BACKUP_SLOTS and starters_done:
                valid.append(slot)

        return valid

    def next_auto_slot(self, team: str, player_meta: Dict[str, Any]) -> Optional[str]:
        valid = self.eligible_slots(team, player_meta)
        return valid[0] if len(valid) == 1 else None

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

    def make_pick(self, athlete_id: str, name: str, slot: str, player_meta: Dict[str, Any]) -> Pick:
        if not self.started or self.completed:
            raise ValueError("Draft not active.")
        team = self.current_team()
        if team is None:
            raise ValueError("No team on the clock.")
        if self.is_team_full(team):
            raise ValueError("Team roster full.")
        if athlete_id in self.picked_ids:
            raise ValueError("Already drafted.")
        if self.roster_has_player(team, athlete_id):
            raise ValueError("Player already on your roster.")

        valid_slots = self.eligible_slots(team, player_meta)
        if not valid_slots:
            raise ValueError("Player does not fit any available slot.")
        if slot not in valid_slots:
            raise ValueError("Invalid slot for this player.")

        pick = Pick(
            pick_no=self.pick_no,
            team=team,
            athlete_id=athlete_id,
            name=name,
            slot=slot,
            slot_label=SLOT_LABELS[slot],
            ts=time.time(),
        )
        roster = self.roster_for(team)
        roster[slot] = {
            "athleteId": athlete_id,
            "name": name,
            "slot": slot,
            "slotLabel": SLOT_LABELS[slot],
        }
        self.picks.append(pick)
        self.picked_ids.add(athlete_id)
        self.advance_turn()
        return pick

    def remaining_seconds(self) -> Optional[int]:
        if not self.started or self.completed or self.deadline_ts is None:
            return None
        return max(0, int(self.deadline_ts - time.time()))