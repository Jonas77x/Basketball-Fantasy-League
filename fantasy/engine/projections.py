"""Projections for the 2026-27 season.

Model (kept deliberately simple and transparent):
1. Per-minute rates from the last three seasons, weighted towards the most recent one
   (weights 5/3/2, multiplied by minutes played), regressed towards league average.
2. Age curve on the per-minute rates (young players improve, decline from about 29,
   steals/blocks/rebounds decline earlier than scoring).
3. Minutes per game from the recent seasons plus small age adjustments.
4. Expected games from the three-year availability history, regressed towards ~70 games.
5. Manual adjustments (injuries, roles, rookies) from data/manual/adjustments_2026_27.toml.
Rookies without NBA stats get a baseline by draft slot and position (clearly flagged).
"""

from dataclasses import dataclass, field

TARGET_SEASON = 2027  # season end year of 2026-27
SEASON_WEIGHTS = {2026: 5.0, 2025: 3.0, 2024: 2.0}
MINUTE_WEIGHTS = {2026: 6.0, 2025: 3.0, 2024: 1.0}

RATE_KEYS = ["pts", "reb", "ast", "stl", "blk", "tpm", "tov", "fga", "fta"]
BREF_KEYS = {
    "pts": "pts", "reb": "trb", "ast": "ast", "stl": "stl", "blk": "blk", "tpm": "fg3",
    "tov": "tov", "fga": "fga", "fta": "fta", "fgm": "fg", "ftm": "ft",
}  # fmt: skip
SCORING_KEYS = {"pts", "ast", "tpm", "tov", "fga", "fta"}

PRIOR_MINUTES = 250.0  # regression strength for per-minute rates
PRIOR_FGA = 150.0
PRIOR_FTA = 80.0
HEALTHY_GAMES = 78.0


@dataclass
class Baseline:
    """League-average per-minute rates and shooting percentages."""

    rates: dict[str, float]
    fg_pct: float
    ft_pct: float


@dataclass
class Projection:
    games: float
    minutes: float
    stats: dict[str, float]  # per game: pts reb ast stl blk tpm tov fga fta fgm ftm
    fg_pct: float
    ft_pct: float
    notes: list[str] = field(default_factory=list)


def _f(record: dict, key: str) -> float:
    value = record.get(key, 0) or 0
    return float(value)


def league_baseline(season_rows: list[dict], min_minutes: float = 500.0) -> Baseline:
    rows = [r for r in season_rows if _f(r, "mp") >= min_minutes]
    minutes = sum(_f(r, "mp") for r in rows)
    rates = {k: sum(_f(r, BREF_KEYS[k]) for r in rows) / minutes for k in RATE_KEYS}
    fg = sum(_f(r, "fg") for r in rows) / sum(_f(r, "fga") for r in rows)
    ft = sum(_f(r, "ft") for r in rows) / sum(_f(r, "fta") for r in rows)
    return Baseline(rates=rates, fg_pct=fg, ft_pct=ft)


def age_factor(age_next: int, key: str) -> float:
    """Multiplier on per-minute rates for next season, depending on age."""
    scoring = [(20, 0.08), (21, 0.06), (22, 0.05), (23, 0.04), (24, 0.03), (25, 0.02), (26, 0.01),
               (28, 0.0), (29, -0.01), (30, -0.015), (31, -0.02), (32, -0.03), (33, -0.04),
               (34, -0.05), (35, -0.06), (99, -0.08)]  # fmt: skip
    athletic = [(20, 0.04), (21, 0.03), (22, 0.02), (23, 0.015), (24, 0.01), (25, 0.005), (26, 0.0),
                (27, -0.005), (28, -0.01), (29, -0.02), (30, -0.025), (31, -0.03), (32, -0.04),
                (33, -0.05), (34, -0.06), (35, -0.07), (99, -0.09)]  # fmt: skip
    table = scoring if key in SCORING_KEYS else athletic
    for max_age, delta in table:
        if age_next <= max_age:
            return 1.0 + delta
    return 1.0


def availability(seasons: dict[int, dict]) -> float:
    """Share of games played over the recent seasons (missing seasons after the debut count as 0)."""
    present = sorted(seasons)
    if not present:
        return 0.86
    first = present[0]
    num = den = 0.0
    for season, weight in SEASON_WEIGHTS.items():
        if season < first:
            continue
        games = _f(seasons[season], "games") if season in seasons else 0.0
        num += weight * min(games, 82.0)
        den += weight * 82.0
    return num / den if den else 0.86


def project_games(seasons: dict[int, dict], age_next: int) -> float:
    rate = availability(seasons)
    games = 82.0 * (0.55 * rate + 0.45 * 0.86)
    if age_next >= 36:
        games -= 4
    elif age_next >= 33:
        games -= 2
    return max(10.0, min(HEALTHY_GAMES, games))


def project_minutes(seasons: dict[int, dict], age_next: int) -> float:
    num = den = 0.0
    for season, weight in MINUTE_WEIGHTS.items():
        if season in seasons and _f(seasons[season], "games") > 0:
            num += weight * _f(seasons[season], "mp")
            den += weight * _f(seasons[season], "games")
    if not den:
        return 0.0
    mpg = num / den
    if mpg >= 15:
        if age_next <= 22:
            mpg += 1.5
        elif age_next <= 24:
            mpg += 0.8
    if age_next >= 36:
        mpg -= 2.5
    elif age_next >= 34:
        mpg -= 1.5
    return max(0.0, min(37.5, mpg))


def project_veteran(seasons: dict[int, dict], age_next: int, baseline: Baseline) -> Projection:
    weighted_minutes = sum(SEASON_WEIGHTS[s] * _f(seasons[s], "mp") for s in seasons if s in SEASON_WEIGHTS)
    rates = {}
    for key in RATE_KEYS:
        total = sum(
            SEASON_WEIGHTS[s] * _f(seasons[s], BREF_KEYS[key]) for s in seasons if s in SEASON_WEIGHTS
        )
        rate = (total + PRIOR_MINUTES * baseline.rates[key]) / (weighted_minutes + PRIOR_MINUTES)
        rates[key] = rate * age_factor(age_next, key)

    def pct(makes: str, attempts: str, prior_att: float, prior_pct: float) -> float:
        m = sum(SEASON_WEIGHTS[s] * _f(seasons[s], makes) for s in seasons if s in SEASON_WEIGHTS)
        a = sum(SEASON_WEIGHTS[s] * _f(seasons[s], attempts) for s in seasons if s in SEASON_WEIGHTS)
        return (m + prior_att * prior_pct) / (a + prior_att)

    fg_pct = pct("fg", "fga", PRIOR_FGA, baseline.fg_pct)
    ft_pct = pct("ft", "fta", PRIOR_FTA, baseline.ft_pct)
    if age_next >= 33:
        fg_pct -= 0.003

    minutes = project_minutes(seasons, age_next)
    games = project_games(seasons, age_next)
    return _finish(rates, minutes, games, fg_pct, ft_pct)


# Rookie baseline per 36 minutes by draft slot: (last pick of tier, minutes per game, per-36 rates)
ROOKIE_TIERS = [
    (3, 27.0, {"pts": 18.5, "reb": 6.8, "ast": 3.4, "stl": 1.2, "blk": 0.8, "tpm": 1.6, "tov": 2.9, "fga": 15.5, "fta": 4.8}),
    (10, 22.0, {"pts": 16.0, "reb": 6.2, "ast": 3.0, "stl": 1.1, "blk": 0.7, "tpm": 1.6, "tov": 2.4, "fga": 13.8, "fta": 3.8}),
    (20, 16.0, {"pts": 14.5, "reb": 6.0, "ast": 2.8, "stl": 1.1, "blk": 0.6, "tpm": 1.6, "tov": 2.2, "fga": 12.8, "fta": 3.2}),
    (30, 12.0, {"pts": 13.5, "reb": 5.8, "ast": 2.6, "stl": 1.0, "blk": 0.6, "tpm": 1.5, "tov": 2.0, "fga": 12.0, "fta": 2.8}),
    (99, 7.0, {"pts": 12.5, "reb": 5.6, "ast": 2.4, "stl": 1.0, "blk": 0.5, "tpm": 1.4, "tov": 1.9, "fga": 11.5, "fta": 2.5}),
]  # fmt: skip
ROOKIE_FG, ROOKIE_FT = 0.445, 0.74
POSITION_MODS = {
    "C": ({"reb": 1.45, "blk": 2.0, "ast": 0.6, "tpm": 0.35, "stl": 0.85}, 0.07, -0.08),
    "PF": ({"reb": 1.2, "blk": 1.35, "ast": 0.8, "tpm": 0.8}, 0.025, -0.03),
    "SF": ({}, 0.0, 0.0),
    "SG": ({"reb": 0.8, "blk": 0.6, "ast": 1.15, "tpm": 1.15}, -0.01, 0.03),
    "PG": ({"reb": 0.7, "blk": 0.5, "ast": 1.7, "tpm": 1.1, "tov": 1.2}, -0.02, 0.04),
}


def project_rookie(pick: int, primary_position: str) -> Projection:
    minutes, per36 = next((m, r) for last, m, r in ROOKIE_TIERS if pick <= last)
    mods, fg_delta, ft_delta = POSITION_MODS.get(primary_position, POSITION_MODS["SF"])
    rates = {k: per36[k] * mods.get(k, 1.0) / 36.0 for k in RATE_KEYS}
    proj = _finish(rates, minutes, 70.0, ROOKIE_FG + fg_delta, ROOKIE_FT + ft_delta)
    proj.notes.append(f"Rookie (Pick {pick}): grobe Schätzung")
    return proj


def _finish(
    rates: dict[str, float], minutes: float, games: float, fg_pct: float, ft_pct: float
) -> Projection:
    stats = {k: rates[k] * minutes for k in RATE_KEYS}
    stats["fgm"] = stats["fga"] * fg_pct
    stats["ftm"] = stats["fta"] * ft_pct
    return Projection(games=games, minutes=minutes, stats=stats, fg_pct=fg_pct, ft_pct=ft_pct)


def apply_adjustments(proj: Projection, adj: dict) -> Projection:
    """Apply one entry of the manual adjustments file."""
    if not adj:
        return proj
    minutes = proj.minutes
    rates = {k: (proj.stats[k] / minutes if minutes else 0.0) for k in RATE_KEYS}
    if "minutes" in adj:
        minutes = float(adj["minutes"])
    minutes = max(0.0, minutes + float(adj.get("minutes_delta", 0.0)))

    production = float(adj.get("production", 1.0))
    factors = {k: production for k in RATE_KEYS}
    stat_factors = adj.get("stats", {})
    for key, value in stat_factors.items():
        factors[key] *= float(value)
    if "pts" in stat_factors:  # more scoring means more shots, keep efficiency constant
        for key in ("fga", "fta"):
            if key not in stat_factors:
                factors[key] *= float(stat_factors["pts"])
    rates = {k: rates[k] * factors[k] for k in RATE_KEYS}

    games = float(adj.get("games", proj.games))
    fg_pct = float(adj.get("fg_pct", proj.fg_pct))
    ft_pct = float(adj.get("ft_pct", proj.ft_pct))
    result = _finish(rates, minutes, games, fg_pct, ft_pct)
    result.notes = list(proj.notes)
    if adj.get("note"):
        result.notes.insert(0, adj["note"])
    return result
