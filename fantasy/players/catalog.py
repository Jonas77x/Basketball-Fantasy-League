"""Player catalog: merges snapshots (stats, ADP, rookies) and manual adjustments into projected players."""

import logging
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from fantasy.config import MANUAL_DIR, SNAPSHOT_DIR
from fantasy.engine import projections as pj
from fantasy.players.names import normalize_name, normalize_team
from fantasy.sources import snapshots as snap

log = logging.getLogger(__name__)

ADJUSTMENTS_FILE = MANUAL_DIR / "adjustments_2026_27.toml"
BREF_POSITIONS = {
    "PG": ["PG"],
    "SG": ["SG"],
    "SF": ["SF"],
    "PF": ["PF"],
    "C": ["C"],
    "G": ["PG", "SG"],
    "F": ["SF", "PF"],
}


@dataclass
class Player:
    id: str
    name: str
    team: str
    positions: list[str]
    age: int
    games: float
    minutes: float
    stats: dict[str, float]  # projected per game
    fg_pct: float
    ft_pct: float
    adp: float | None = None  # Yahoo ADP
    adp_blend: float | None = None
    is_rookie: bool = False
    notes: list[str] = field(default_factory=list)
    last_season: dict = field(default_factory=dict)  # per-game line of the last NBA season for display
    last_season_year: int | None = None

    @property
    def pos_label(self) -> str:
        return ",".join(self.positions)

    @property
    def search_key(self) -> str:
        return normalize_name(self.name) + " " + self.team.lower()


def _positions_from_text(text: str) -> list[str]:
    result: list[str] = []
    for part in text.replace("-", " ").replace(",", " ").split():
        for pos in BREF_POSITIONS.get(part.upper(), []):
            if pos not in result:
                result.append(pos)
    return result


def load_adjustments(path: Path = ADJUSTMENTS_FILE) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return {normalize_name(name): entry for name, entry in data.get("players", {}).items()}


def _last_line(record: dict) -> dict:
    games = float(record["games"]) or 1.0
    per = {k: float(record[v]) / games for k, v in pj.BREF_KEYS.items()}
    per["games"] = float(record["games"])
    per["minutes"] = float(record["mp"]) / games
    return per


def build_catalog(
    snapshot_dir: Path = SNAPSHOT_DIR, adjustments_file: Path = ADJUSTMENTS_FILE
) -> list[Player]:
    seasons_by_id: dict[str, dict[int, dict]] = {}
    latest_by_name: dict[str, str] = {}
    for season in snap.STAT_SEASONS:
        for row in snap.read_csv(snap.totals_path(season, snapshot_dir)):
            seasons_by_id.setdefault(row["bref_id"], {})[season] = row
            latest_by_name[normalize_name(row["name"])] = row["bref_id"]  # later seasons overwrite

    last_season = max(snap.STAT_SEASONS)
    baseline = pj.league_baseline(snap.read_csv(snap.totals_path(last_season, snapshot_dir)))
    rookies = {normalize_name(r["name"]): r for r in snap.read_csv(snap.draft_path(base=snapshot_dir))}
    adjustments = load_adjustments(adjustments_file)

    players: list[Player] = []
    for row in snap.read_csv(snap.adp_path(snapshot_dir)):
        key = normalize_name(row["name"])
        adj = adjustments.get(key, {})
        positions = row["yahoo_pos"].split() if row["yahoo_pos"] else []
        team = normalize_team(adj.get("team") or row["team"])
        adp = float(row["yahoo_adp"]) if row["yahoo_adp"] else None
        blend = float(row["blend_adp"]) if row["blend_adp"] else None

        bref_id = latest_by_name.get(key)
        if bref_id:
            seasons = seasons_by_id[bref_id]
            latest = max(seasons)
            record = seasons[latest]
            age_next = int(record["age"]) + (pj.TARGET_SEASON - latest)
            proj = pj.project_veteran(seasons, age_next, baseline)
            if not positions:
                positions = _positions_from_text(record["pos"])
            proj = pj.apply_adjustments(proj, adj)
            last_team = normalize_team(record["team"])
            if team and last_team and team != last_team and "Neu bei" not in adj.get("note", ""):
                proj.notes.append(f"Neu bei {team}")
            if latest == last_season and float(record["games"]) < 40 and not adj.get("note"):
                proj.notes.append(f"Nur {int(float(record['games']))} Spiele 25/26")
            if latest < last_season and not adj.get("note"):
                proj.notes.append("25/26 nicht gespielt")
            players.append(
                Player(
                    id=bref_id,
                    name=row["name"],
                    team=team,
                    positions=positions,
                    age=age_next,
                    games=proj.games,
                    minutes=proj.minutes,
                    stats=proj.stats,
                    fg_pct=proj.fg_pct,
                    ft_pct=proj.ft_pct,
                    adp=adp,
                    adp_blend=blend,
                    notes=_dedupe(proj.notes),
                    last_season=_last_line(record),
                    last_season_year=latest,
                )
            )
        elif key in rookies:
            pick = int(rookies[key]["pick"])
            primary = positions[0] if positions else "SF"
            proj = pj.project_rookie(pick, primary)
            if adj.get("note"):
                proj.notes = []  # the manual note already describes the rookie
            proj = pj.apply_adjustments(proj, adj)
            players.append(
                Player(
                    id=f"rk2026-{pick}",
                    name=row["name"],
                    team=team,
                    positions=positions or ["SF"],
                    age=20,
                    games=proj.games,
                    minutes=proj.minutes,
                    stats=proj.stats,
                    fg_pct=proj.fg_pct,
                    ft_pct=proj.ft_pct,
                    adp=adp,
                    adp_blend=blend,
                    is_rookie=True,
                    notes=_dedupe(proj.notes),
                )
            )
        else:
            log.warning("no stats for %s – skipped", row["name"])

    return players


def _dedupe(notes: list[str]) -> list[str]:
    seen, result = set(), []
    for note in notes:
        if note not in seen:
            seen.add(note)
            result.append(note)
    return result


@lru_cache
def get_catalog() -> tuple[Player, ...]:
    return tuple(build_catalog())


def by_id() -> dict[str, Player]:
    return {p.id: p for p in get_catalog()}
