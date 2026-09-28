"""League sync: settings, teams and players from Yahoo into our database and draft settings."""

import logging
from dataclasses import asdict, dataclass, replace

from sqlalchemy import select

from fantasy.config import get_settings
from fantasy.db import SyncLog, YahooPlayer, get_json, session_scope, set_json
from fantasy.engine.draft import DraftSettings
from fantasy.players.catalog import Player
from fantasy.players.names import normalize_name, normalize_team
from fantasy.timeutil import format_display, utcnow
from fantasy.yahoo import api
from fantasy.yahoo.client import YahooClient

log = logging.getLogger(__name__)

KV_LEAGUE = "yahoo_league"  # active league key + league info
KV_SETTINGS = "yahoo_settings"  # readable summary of the league settings
KV_TEAMS = "yahoo_teams"

PLAYER_PAGES = 16  # 16 x 25 = 400 players by Yahoo overall rank (about 16 s at 1 request/s)

# Yahoo stat display names / NBA stat ids -> our category keys.
CATEGORY_BY_DISPLAY = {
    "PTS": "pts", "REB": "reb", "AST": "ast", "ST": "stl", "STL": "stl", "BLK": "blk",
    "3PTM": "tpm", "3PM": "tpm", "FG%": "fg", "FT%": "ft", "TO": "to",
}  # fmt: skip
CATEGORY_BY_ID = {
    12: "pts",
    15: "reb",
    16: "ast",
    17: "stl",
    18: "blk",
    10: "tpm",
    5: "fg",
    8: "ft",
    19: "to",
}
NOT_DRAFTED_SLOTS = {"IL", "IL+", "NA"}


def map_categories(stats: list[api.StatCategory]) -> tuple[list[str], list[str]]:
    """(our category keys in Yahoo order, names of scoring categories we cannot handle yet)."""
    keys, unsupported = [], []
    for stat in stats:
        if stat.display_only or not stat.enabled:
            continue
        key = CATEGORY_BY_DISPLAY.get(stat.display_name.upper()) or CATEGORY_BY_ID.get(stat.stat_id)
        if key and key not in keys:
            keys.append(key)
        elif not key:
            unsupported.append(stat.display_name or stat.name)
    return keys, unsupported


def roster_slots(positions: list[api.RosterPosition]) -> list[str]:
    slots = []
    for pos in positions:
        if pos.position in NOT_DRAFTED_SLOTS:
            continue
        name = "UTIL" if pos.position.upper() == "UTIL" else pos.position.upper()
        slots.extend([name] * pos.count)
    return slots


def draft_settings_from_yahoo(
    settings: api.LeagueSettings, teams: list[api.YahooTeam], old: DraftSettings
) -> DraftSettings:
    categories, _ = map_categories(settings.stat_categories)
    slots = roster_slots(settings.roster_positions)
    ordered = sorted(teams, key=lambda t: (t.draft_position or 99, int(t.team_id or 0)))
    mine = next((t for t in teams if t.is_mine), None)
    has_order = all(t.draft_position for t in teams) and len(teams) == settings.league.num_teams
    return DraftSettings(
        teams=settings.league.num_teams or old.teams,
        my_slot=(mine.draft_position if mine and mine.draft_position else old.my_slot),
        rounds=len(slots) or old.rounds,
        categories=categories or old.categories,
        punts=[c for c in old.punts if c in (categories or old.categories)],
        roster=slots or old.roster,
        risk=old.risk,
        team_names=[t.name for t in ordered] if has_order else old.team_names,
    )


def active_league_key() -> str:
    with session_scope() as session:
        info = get_json(session, KV_LEAGUE, {}) or {}
    if info.get("league_key"):
        return info["league_key"]
    league_id = get_settings().yahoo_league_id.strip()
    return api.league_key_for(league_id) if league_id else ""


def set_active_league(league_key: str) -> None:
    with session_scope() as session:
        set_json(session, KV_LEAGUE, {"league_key": league_key})


def league_info() -> dict:
    with session_scope() as session:
        return {
            "league": get_json(session, KV_LEAGUE, {}) or {},
            "settings": get_json(session, KV_SETTINGS, {}) or {},
            "teams": get_json(session, KV_TEAMS, []) or [],
        }


def my_team_key() -> str:
    teams = league_info()["teams"]
    return next((t["team_key"] for t in teams if t.get("is_mine")), "")


def team_slots() -> dict[str, int]:
    """team_key -> draft position (slot)."""
    return {t["team_key"]: t["draft_position"] for t in league_info()["teams"] if t.get("draft_position")}


def settings_summary(settings: api.LeagueSettings) -> dict:
    categories, unsupported = map_categories(settings.stat_categories)
    waiver_types = {"R": "Rolling (Reihenfolge rotiert)", "FR": "Nach Tabellenplatz", "F": "FAAB (Bieten)"}
    return {
        "name": settings.league.name,
        "season": settings.league.season,
        "num_teams": settings.league.num_teams,
        "draft_status": settings.league.draft_status,
        "draft_type": settings.draft_type,
        "is_auction": settings.is_auction,
        "draft_time": settings.draft_time.isoformat() if settings.draft_time else None,
        "draft_time_display": format_display(settings.draft_time) if settings.draft_time else None,
        "draft_pick_time": settings.draft_pick_time,
        "categories": categories,
        "unsupported_categories": unsupported,
        "roster": [
            f"{p.position} ×{p.count}" if p.count > 1 else p.position for p in settings.roster_positions
        ],
        "max_weekly_adds": settings.max_weekly_adds,
        "max_adds": settings.max_adds,
        "waiver_type": waiver_types.get(settings.waiver_type, settings.waiver_type),
        "waiver_rule": settings.waiver_rule,
        "waiver_time": settings.waiver_time,
        "uses_faab": settings.uses_faab,
        "uses_playoff": settings.uses_playoff,
        "playoff_start_week": settings.playoff_start_week,
        "num_playoff_teams": settings.num_playoff_teams,
        "trade_end_date": settings.trade_end_date,
        "trade_ratify_type": settings.trade_ratify_type,
        "start_date": settings.league.start_date,
        "end_date": settings.league.end_date,
        "url": settings.league.url,
    }


# ---------- players ----------


def _catalog_index(catalog: list[Player]) -> dict[str, list[Player]]:
    index: dict[str, list[Player]] = {}
    for player in catalog:
        index.setdefault(normalize_name(player.name), []).append(player)
    return index


def match_catalog(info: api.YahooPlayerInfo, index: dict[str, list[Player]]) -> str | None:
    candidates = index.get(normalize_name(info.name), [])
    if len(candidates) == 1:
        return candidates[0].id
    team = normalize_team(info.team_abbr)
    same_team = [p for p in candidates if p.team == team]
    return same_team[0].id if len(same_team) == 1 else None


def store_players(infos: list[api.YahooPlayerInfo], catalog: list[Player]) -> int:
    """Upsert Yahoo players with their catalog mapping. Returns the number of unmatched players."""
    index = _catalog_index(catalog)
    unmatched = 0
    with session_scope() as session:
        for info in infos:
            row = session.get(YahooPlayer, info.player_key) or YahooPlayer(player_key=info.player_key)
            row.catalog_id = match_catalog(info, index)
            unmatched += row.catalog_id is None
            row.name = info.name
            row.team = normalize_team(info.team_abbr)
            row.positions = " ".join(info.positions)
            row.status = info.status
            row.injury_note = info.injury_note
            if info.rank is not None:
                row.rank = info.rank
            if info.average_pick is not None:
                row.average_pick = info.average_pick
                row.percent_drafted = info.percent_drafted
            row.updated_at = utcnow()
            session.merge(row)
    return unmatched


def known_player_keys() -> dict[str, tuple[str | None, str]]:
    """player_key -> (catalog id, name)."""
    with session_scope() as session:
        rows = session.scalars(select(YahooPlayer)).all()
        return {r.player_key: (r.catalog_id, r.name) for r in rows}


def overlay(players: list[Player]) -> list[Player]:
    """Our catalog enriched with the league's Yahoo data: Yahoo ADP, positions and injury status."""
    with session_scope() as session:
        rows = session.scalars(select(YahooPlayer).where(YahooPlayer.catalog_id.is_not(None))).all()
        data = {
            r.catalog_id: (r.average_pick, r.positions, r.status, r.injury_note, r.percent_drafted)
            for r in rows
        }
    if not data:
        return players
    result = []
    for p in players:
        if p.id not in data:
            result.append(p)
            continue
        adp, positions, status, note, pct = data[p.id]
        changes = {}
        if adp is not None and (pct or 0) > 0:
            changes["adp"] = adp
        if positions:
            changes["positions"] = positions.split()
        if status:
            text = f"Yahoo-Status: {status}" + (f" ({note})" if note else "")
            changes["notes"] = [text, *p.notes]
        result.append(replace(p, **changes) if changes else p)
    return result


# ---------- full sync ----------


@dataclass
class SyncSummary:
    league_key: str
    league_name: str
    teams: int
    my_team: str
    my_slot: int | None
    players: int
    unmatched: int
    unsupported_categories: list[str]


def sync_league(client: YahooClient, catalog: list[Player], player_pages: int = PLAYER_PAGES) -> SyncSummary:
    from fantasy import draftroom

    league_key = active_league_key()
    if not league_key:
        raise ValueError("Keine Liga-ID gesetzt (YAHOO_LEAGUE_ID in der .env).")
    settings = api.league_settings(client, league_key)
    teams = api.league_teams(client, league_key)
    league_key = settings.league.league_key or league_key  # numeric game id instead of "nba"
    summary = settings_summary(settings)

    with session_scope() as session:
        set_json(
            session,
            KV_LEAGUE,
            {
                "league_key": league_key,
                "league_id": settings.league.league_id,
                "name": settings.league.name,
                "synced_at": utcnow().isoformat(),
            },
        )
        set_json(session, KV_SETTINGS, summary)
        set_json(session, KV_TEAMS, [asdict(t) for t in teams])
        draft = draftroom.get_draft(session, "live")
        new_settings = draft_settings_from_yahoo(settings, teams, draftroom.settings_of(draft))
        draftroom.save_settings(draft, new_settings)

    infos: list[api.YahooPlayerInfo] = []
    for page in range(player_pages):
        batch = api.players_ranked(client, league_key, start=page * 25)
        infos.extend(batch)
        if len(batch) < 25:
            break
    unmatched = store_players(infos, catalog)

    mine = next((t for t in teams if t.is_mine), None)
    result = SyncSummary(
        league_key=league_key,
        league_name=settings.league.name,
        teams=len(teams),
        my_team=mine.name if mine else "",
        my_slot=mine.draft_position if mine else None,
        players=len(infos),
        unmatched=unmatched,
        unsupported_categories=summary["unsupported_categories"],
    )
    with session_scope() as session:
        session.add(
            SyncLog(
                kind="league",
                message=f"Liga synchronisiert: {result.league_name}, {len(infos)} Spieler, "
                f"{unmatched} ohne Zuordnung",
                ok=True,
            )
        )
    log.info("league sync done: %s", result)
    return result
