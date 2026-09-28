"""Snapshots: raw source data stored as CSV in data/snapshots/ so the app works offline.

`uv run fantasy update-data` refreshes them (polite, cached fetches).
"""

import csv
import json
import logging
from pathlib import Path

from fantasy.config import SNAPSHOT_DIR
from fantasy.timeutil import utcnow

log = logging.getLogger(__name__)

STAT_SEASONS = (2024, 2025, 2026)  # season end years: 2023-24, 2024-25, 2025-26
ROOKIE_DRAFT_YEAR = 2026


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"refusing to write empty snapshot {path.name}")
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def totals_path(season: int, base: Path = SNAPSHOT_DIR) -> Path:
    return base / f"bref_totals_{season}.csv"


def draft_path(year: int = ROOKIE_DRAFT_YEAR, base: Path = SNAPSHOT_DIR) -> Path:
    return base / f"bref_draft_{year}.csv"


def adp_path(base: Path = SNAPSHOT_DIR) -> Path:
    return base / "hashtag_adp.csv"


def meta_path(base: Path = SNAPSHOT_DIR) -> Path:
    return base / "meta.json"


def read_meta(base: Path = SNAPSHOT_DIR) -> dict:
    path = meta_path(base)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_all(base: Path = SNAPSHOT_DIR, include_stats: bool = True) -> dict:
    """Fetch all sources and rewrite the snapshots. Returns the new meta information."""
    from fantasy.sources import bref, hashtag

    meta = read_meta(base)
    now = utcnow().isoformat(timespec="seconds")

    if include_stats:
        for season in STAT_SEASONS:
            rows = bref.fetch_totals(season)
            write_csv(totals_path(season, base), rows)
            meta[totals_path(season, base).name] = {"fetched_at": now, "rows": len(rows)}
            log.info("season %s: %d players", season, len(rows))

    rows = bref.fetch_draft(ROOKIE_DRAFT_YEAR)
    write_csv(draft_path(base=base), rows)
    meta[draft_path(base=base).name] = {"fetched_at": now, "rows": len(rows)}

    rows = hashtag.fetch_adp()
    write_csv(adp_path(base), rows)
    meta[adp_path(base).name] = {"fetched_at": now, "rows": len(rows)}

    meta_path(base).write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta
