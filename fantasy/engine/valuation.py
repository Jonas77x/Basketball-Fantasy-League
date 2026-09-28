"""Z-score valuation for head-to-head category leagues.

Improvements over the original HTML assistant:
- Means and standard deviations come from the *draftable* pool (teams x rounds), found iteratively,
  not from every player in the list.
- FG% and FT% are valued by their impact (makes above pool average for the attempts taken),
  so volume matters.
- Availability: expected missed games are filled with a replacement-level player (optional).
- Head-to-head weighting ("G-score" idea, Rosenof 2024): categories with a lot of week-to-week noise
  (steals, blocks, turnovers, percentages) get a lower weight, because an extreme value there still
  wins only one category per week.
"""

from collections.abc import Sequence

import numpy as np

from fantasy.engine.categories import CATEGORIES, DEFAULT_CATEGORIES, PROJ_KEY

HEALTHY_GAMES = 78.0

# Approximate weights; volatile categories count less in weekly match-ups.
H2H_WEIGHTS = {
    "pts": 1.0,
    "reb": 1.0,
    "ast": 1.0,
    "tpm": 0.95,
    "stl": 0.8,
    "blk": 0.85,
    "fg": 0.85,
    "ft": 0.8,
    "to": 0.8,
}


class Valuation:
    def __init__(
        self,
        players: Sequence,
        pool_size: int,
        categories: Sequence[str] = DEFAULT_CATEGORIES,
        weights: dict[str, float] | None = None,
    ):
        self.players = list(players)
        self.categories = list(categories)
        weights = H2H_WEIGHTS if weights is None else weights
        self.weights = np.array([weights.get(k, 1.0) for k in self.categories])
        self.index = {p.id: i for i, p in enumerate(self.players)}
        self.pool_size = min(pool_size, len(self.players))
        self.games = np.array([p.games for p in self.players], dtype=float)
        self._stats = {
            key: np.array([p.stats.get(key, 0.0) for p in self.players], dtype=float)
            for key in ("pts", "reb", "ast", "stl", "blk", "tpm", "tov", "fgm", "fga", "ftm", "fta")
        }
        self.z = np.zeros((len(self.players), len(self.categories)))
        self.pool_pct: dict[str, float] = {}
        self._compute()

    # ---------- computation ----------

    def _raw(self, pool: np.ndarray) -> np.ndarray:
        columns = []
        for key in self.categories:
            cat = CATEGORIES[key]
            if cat.kind == "pct":
                makes, attempts = self._stats[cat.makes], self._stats[cat.attempts]
                pct = makes[pool].sum() / max(attempts[pool].sum(), 1e-9)
                self.pool_pct[key] = float(pct)
                columns.append(makes - attempts * pct)
            else:
                values = self._stats[PROJ_KEY[key]]
                columns.append(-values if cat.negative else values)
        return np.column_stack(columns)

    def _zscores(self, pool: np.ndarray) -> np.ndarray:
        raw = self._raw(pool)
        mean = raw[pool].mean(axis=0)
        sd = raw[pool].std(axis=0)
        sd[sd < 1e-9] = 1.0
        return (raw - mean) / sd * self.weights

    def _compute(self) -> None:
        minutes = np.array([p.minutes for p in self.players])
        pool = minutes >= 20.0
        if pool.sum() < 10:
            pool = np.ones(len(self.players), dtype=bool)
        for _ in range(4):
            z = self._zscores(pool)
            total = z.sum(axis=1)
            order = np.argsort(-total)
            new_pool = np.zeros(len(self.players), dtype=bool)
            new_pool[order[: self.pool_size]] = True
            if np.array_equal(new_pool, pool):
                break
            pool = new_pool
        self.z = self._zscores(pool)
        self.pool_mask = pool

    # ---------- queries ----------

    def cat_index(self, keys: Sequence[str]) -> list[int]:
        return [self.categories.index(k) for k in keys if k in self.categories]

    def totals(self, active: Sequence[str]) -> np.ndarray:
        """Sum of z-scores over the active (not punted) categories, per game."""
        return self.z[:, self.cat_index(active)].sum(axis=1)

    def replacement_level(self, values: np.ndarray, teams: int) -> float:
        """Value of the best players just outside the draftable pool (what the waiver wire offers)."""
        order = np.sort(values)[::-1]
        start = self.pool_size
        chunk = order[start : start + max(teams, 1)]
        return float(chunk.mean()) if len(chunk) else 0.0

    def with_availability(self, values: np.ndarray, replacement: float) -> np.ndarray:
        """Blend in replacement level for the games a player is expected to miss."""
        share = np.clip(self.games / HEALTHY_GAMES, 0.0, 1.0)
        return share * values + (1.0 - share) * replacement

    def values(self, active: Sequence[str], teams: int, risk: bool = True) -> np.ndarray:
        values = self.totals(active)
        if risk:
            values = self.with_availability(values, self.replacement_level(values, teams))
        return values
