import pytest

from fantasy.engine import projections as pj
from fantasy.players.catalog import build_catalog


def season(games, mp, **totals):
    base = {"games": games, "mp": mp, "pts": 0, "trb": 0, "ast": 0, "stl": 0, "blk": 0, "fg3": 0, "tov": 0,
            "fga": 0, "fta": 0, "fg": 0, "ft": 0}  # fmt: skip
    base.update(totals)
    return base


BASELINE = pj.Baseline(rates={k: 0.4 for k in pj.RATE_KEYS}, fg_pct=0.47, ft_pct=0.78)


def test_availability_counts_missed_season_after_debut_as_zero():
    seasons = {2024: season(80, 2800), 2025: season(80, 2800)}  # missed all of 2025-26
    assert pj.availability(seasons) == pytest.approx((2 * 80 + 3 * 80) / (10 * 82))


def test_age_curve_direction():
    assert pj.age_factor(21, "pts") > 1.0
    assert pj.age_factor(27, "pts") == 1.0
    assert pj.age_factor(35, "blk") < pj.age_factor(35, "pts") < 1.0


def test_veteran_projection_recent_season_weighs_most():
    old = season(80, 2400, pts=1200, fga=1000, fg=470, fta=200, ft=160)
    new = season(80, 2400, pts=2400, fga=1600, fg=760, fta=400, ft=320)
    proj = pj.project_veteran({2025: old, 2026: new}, age_next=27, baseline=BASELINE)
    assert 20 < proj.stats["pts"] < 30  # closer to the recent 30 ppg than to 15
    assert proj.minutes == pytest.approx(30.0)
    assert 0.46 < proj.fg_pct < 0.48


def test_adjustments_override_games_and_scale_shots_with_points():
    proj = pj.project_rookie(1, "SF")
    adjusted = pj.apply_adjustments(proj, {"games": 50, "stats": {"pts": 1.2}, "note": "Test"})
    assert adjusted.games == 50
    assert adjusted.stats["pts"] == pytest.approx(proj.stats["pts"] * 1.2)
    assert adjusted.stats["fga"] == pytest.approx(proj.stats["fga"] * 1.2)
    assert adjusted.fg_pct == proj.fg_pct
    assert adjusted.notes[0] == "Test"


def test_rookie_centers_rebound_more_than_guards():
    center, guard = pj.project_rookie(5, "C"), pj.project_rookie(5, "PG")
    assert center.stats["reb"] > guard.stats["reb"]
    assert guard.stats["ast"] > center.stats["ast"]
    assert "Rookie" in center.notes[0]


def test_catalog_from_snapshots():
    players = build_catalog()
    by_name = {p.name: p for p in players}
    assert len(players) > 350
    jokic = by_name["Nikola Jokic"]
    assert jokic.stats["reb"] > 10 and jokic.positions == ["C"]
    assert by_name["Shaedon Sharpe"].games == 22  # manual adjustment: out until March
    assert by_name["Cameron Boozer"].is_rookie
    assert any("Neu bei" in n for n in by_name["Jaylen Brown"].notes)
