from pathlib import Path

import pytest

from fantasy.players.catalog import Player

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Every test gets its own data directory (SQLite, cache) and no .env secrets."""
    from fantasy import config, db

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "var"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    config.get_settings.cache_clear()
    db.reset_engine()
    yield
    db.reset_engine()
    config.get_settings.cache_clear()


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def make_player(pid: str, **stats) -> Player:
    """Synthetic player with sensible defaults; override any per-game stat via keywords."""
    base = {"pts": 12.0, "reb": 5.0, "ast": 3.0, "stl": 1.0, "blk": 0.5, "tpm": 1.2, "tov": 1.5,
            "fga": 10.0, "fta": 3.0}  # fmt: skip
    games = stats.pop("games", 70.0)
    positions = stats.pop("positions", ["SF"])
    adp = stats.pop("adp", None)
    fg_pct = stats.pop("fg_pct", 0.47)
    ft_pct = stats.pop("ft_pct", 0.78)
    base.update(stats)
    base["fgm"] = base["fga"] * fg_pct
    base["ftm"] = base["fta"] * ft_pct
    return Player(
        id=pid,
        name=f"Player {pid}",
        team="BOS",
        positions=positions,
        age=26,
        games=games,
        minutes=30.0,
        stats=base,
        fg_pct=fg_pct,
        ft_pct=ft_pct,
        adp=adp,
        adp_blend=adp,
    )
