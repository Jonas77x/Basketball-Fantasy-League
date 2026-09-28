"""Snake draft state: whose turn it is, which picks are mine, who is gone."""

import math
from dataclasses import asdict, dataclass, field

from fantasy.engine.categories import DEFAULT_CATEGORIES

# Yahoo default for NBA: 10 starters + 3 bench (IL slots are not drafted).
DEFAULT_ROSTER = ["PG", "SG", "G", "SF", "PF", "F", "C", "C", "UTIL", "UTIL", "BN", "BN", "BN"]


@dataclass
class DraftSettings:
    teams: int = 12
    my_slot: int = 1
    rounds: int = 13
    categories: list[str] = field(default_factory=lambda: list(DEFAULT_CATEGORIES))
    punts: list[str] = field(default_factory=list)
    roster: list[str] = field(default_factory=lambda: list(DEFAULT_ROSTER))
    risk: bool = True
    team_names: list[str] = field(default_factory=list)

    @property
    def active_categories(self) -> list[str]:
        return [c for c in self.categories if c not in self.punts]

    @property
    def total_picks(self) -> int:
        return self.teams * self.rounds

    @property
    def pool_size(self) -> int:
        return self.teams * self.rounds

    @property
    def starting_slots(self) -> list[str]:
        return [s for s in self.roster if s not in ("BN", "IL", "IL+")]

    def team_name(self, slot: int) -> str:
        if slot == self.my_slot:
            return "Du"
        if 0 < slot <= len(self.team_names) and self.team_names[slot - 1]:
            return self.team_names[slot - 1]
        return f"Team {slot}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DraftSettings":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        settings = cls(**known)
        settings.my_slot = max(1, min(settings.my_slot, settings.teams))
        return settings


@dataclass
class DraftPick:
    overall: int
    slot: int
    player_id: str | None
    name: str
    mine: bool


def slot_for_pick(overall: int, teams: int) -> int:
    """Team slot (1..teams) on the clock at an overall pick number in a snake draft."""
    rnd = math.ceil(overall / teams)
    pos = overall - (rnd - 1) * teams
    return pos if rnd % 2 == 1 else teams + 1 - pos


def round_of(overall: int, teams: int) -> int:
    return math.ceil(overall / teams)


class DraftState:
    def __init__(self, settings: DraftSettings, picks: list[DraftPick]):
        self.settings = settings
        self.picks = sorted(picks, key=lambda p: p.overall)

    @property
    def current_pick(self) -> int:
        return len(self.picks) + 1

    @property
    def is_done(self) -> bool:
        return self.current_pick > self.settings.total_picks

    @property
    def on_the_clock(self) -> int | None:
        return None if self.is_done else slot_for_pick(self.current_pick, self.settings.teams)

    @property
    def is_my_turn(self) -> bool:
        return not self.is_done and self.on_the_clock == self.settings.my_slot

    @property
    def current_round(self) -> int:
        return min(round_of(self.current_pick, self.settings.teams), self.settings.rounds)

    def my_pick_numbers(self) -> list[int]:
        s = self.settings
        return [n for n in range(1, s.total_picks + 1) if slot_for_pick(n, s.teams) == s.my_slot]

    def next_my_pick(self, after: int | None = None) -> int | None:
        start = self.current_pick if after is None else after + 1
        return next((n for n in self.my_pick_numbers() if n >= start), None)

    def future_my_picks(self) -> list[int]:
        return [n for n in self.my_pick_numbers() if n >= self.current_pick]

    def drafted_ids(self) -> set[str]:
        return {p.player_id for p in self.picks if p.player_id}

    def my_player_ids(self) -> list[str]:
        return [p.player_id for p in self.picks if p.mine and p.player_id]

    def my_picks(self) -> list[DraftPick]:
        return [p for p in self.picks if p.mine]

    def picks_until_my_turn(self) -> int:
        """Number of other teams' picks before my next pick (0 if it's my turn)."""
        nxt = self.next_my_pick()
        return 0 if nxt is None else nxt - self.current_pick

    def picks_between_my_next_two(self) -> int | None:
        """When it's my turn: how many picks the others make before my following pick."""
        nxt = self.next_my_pick()
        if nxt is None:
            return None
        after = self.next_my_pick(after=nxt)
        return None if after is None else after - nxt - 1
