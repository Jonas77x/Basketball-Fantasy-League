"""Typed read access to the Yahoo Fantasy API.

Every endpoint used here is documented at https://sports.yahoo.com/developer/docs/ (section in comments).
Keys: league_key = {game_key}.l.{league_id}; the game code "nba" works as game_key for the current season.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from fantasy.yahoo.client import YahooClient
from fantasy.yahoo.xmlutil import integer, num, txt

# ---------- models ----------


@dataclass
class YahooLeague:
    league_key: str
    league_id: str
    name: str
    season: str
    num_teams: int
    draft_status: str  # predraft, drafting, postdraft
    url: str = ""
    current_week: int | None = None
    start_date: str = ""
    end_date: str = ""


@dataclass
class StatCategory:
    stat_id: int
    name: str
    display_name: str
    display_only: bool
    enabled: bool = True


@dataclass
class RosterPosition:
    position: str
    count: int
    position_type: str = ""


@dataclass
class LeagueSettings:
    league: YahooLeague
    draft_type: str
    is_auction: bool
    draft_time: datetime | None
    draft_pick_time: int | None
    scoring_type: str
    stat_categories: list[StatCategory]
    roster_positions: list[RosterPosition]
    uses_playoff: bool
    playoff_start_week: int | None
    num_playoff_teams: int | None
    waiver_type: str
    waiver_rule: str
    waiver_time: int | None
    uses_faab: bool
    max_weekly_adds: int | None
    max_adds: int | None
    trade_end_date: str
    trade_ratify_type: str
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class YahooTeam:
    team_key: str
    team_id: str
    name: str
    draft_position: int | None
    is_mine: bool
    manager: str = ""
    waiver_priority: int | None = None
    number_of_moves: int | None = None


@dataclass
class DraftResult:
    pick: int
    round: int
    team_key: str
    player_key: str | None


@dataclass
class YahooPlayerInfo:
    player_key: str
    name: str
    team_abbr: str
    positions: list[str]
    status: str = ""
    injury_note: str = ""
    average_pick: float | None = None
    percent_drafted: float | None = None
    rank: int | None = None
    selected_position: str = ""


# ---------- parsing ----------

GENERIC_SLOTS = {"G", "F", "Util", "UTIL", "BN", "IL", "IL+", "NA"}


def _league(el) -> YahooLeague:
    return YahooLeague(
        league_key=txt(el, "league_key"),
        league_id=txt(el, "league_id"),
        name=txt(el, "name"),
        season=txt(el, "season"),
        num_teams=integer(el, "num_teams") or 0,
        draft_status=txt(el, "draft_status"),
        url=txt(el, "url"),
        current_week=integer(el, "current_week"),
        start_date=txt(el, "start_date"),
        end_date=txt(el, "end_date"),
    )


def parse_leagues(root) -> list[YahooLeague]:
    return [_league(el) for el in root.iter("league")]


def parse_settings(root) -> LeagueSettings:
    league_el = root.find("league")
    s = league_el.find("settings")
    stats = []
    for stat in s.findall("stat_categories/stats/stat"):
        stats.append(
            StatCategory(
                stat_id=integer(stat, "stat_id") or 0,
                name=txt(stat, "name"),
                display_name=txt(stat, "display_name"),
                display_only=txt(stat, "is_only_display_stat") == "1",
                enabled=txt(stat, "enabled", "1") == "1",
            )
        )
    positions = [
        RosterPosition(txt(p, "position"), integer(p, "count") or 0, txt(p, "position_type"))
        for p in s.findall("roster_positions/roster_position")
    ]
    raw = {child.tag: (child.text or "").strip() for child in s if len(child) == 0}
    draft_ts = integer(s, "draft_time")
    return LeagueSettings(
        league=_league(league_el),
        draft_type=txt(s, "draft_type"),
        is_auction=txt(s, "is_auction_draft") == "1",
        draft_time=datetime.fromtimestamp(draft_ts, UTC) if draft_ts else None,
        draft_pick_time=integer(s, "draft_pick_time"),
        scoring_type=txt(s, "scoring_type"),
        stat_categories=stats,
        roster_positions=positions,
        uses_playoff=txt(s, "uses_playoff") == "1",
        playoff_start_week=integer(s, "playoff_start_week"),
        num_playoff_teams=integer(s, "num_playoff_teams"),
        waiver_type=txt(s, "waiver_type"),
        waiver_rule=txt(s, "waiver_rule"),
        waiver_time=integer(s, "waiver_time"),
        uses_faab=txt(s, "uses_faab") == "1",
        max_weekly_adds=integer(s, "max_weekly_adds"),
        max_adds=integer(s, "max_adds"),
        trade_end_date=txt(s, "trade_end_date"),
        trade_ratify_type=txt(s, "trade_ratify_type"),
        raw=raw,
    )


def parse_teams(root) -> list[YahooTeam]:
    teams = []
    for el in root.iter("team"):
        managers = el.findall("managers/manager")
        is_mine = txt(el, "is_owned_by_current_login") == "1" or any(
            txt(m, "is_current_login") == "1" for m in managers
        )
        teams.append(
            YahooTeam(
                team_key=txt(el, "team_key"),
                team_id=txt(el, "team_id"),
                name=txt(el, "name"),
                draft_position=integer(el, "draft_position"),
                is_mine=is_mine,
                manager=txt(managers[0], "nickname") if managers else "",
                waiver_priority=integer(el, "waiver_priority"),
                number_of_moves=integer(el, "number_of_moves"),
            )
        )
    return teams


def parse_draft_results(root) -> tuple[str, list[DraftResult]]:
    league_el = root.find("league")
    status = txt(league_el, "draft_status")
    results = []
    for el in root.iter("draft_result"):
        player = txt(el, "player_key") or None
        results.append(
            DraftResult(integer(el, "pick") or 0, integer(el, "round") or 0, txt(el, "team_key"), player)
        )
    results.sort(key=lambda r: r.pick)
    return status, results


def parse_players(root, start_rank: int | None = None) -> list[YahooPlayerInfo]:
    players = []
    for n, el in enumerate(root.iter("player")):
        name = txt(el, "name/full") or f"{txt(el, 'name/first')} {txt(el, 'name/last')}".strip()
        eligible = [p.text.strip() for p in el.findall("eligible_positions/position") if p.text]
        analysis = el.find("draft_analysis")
        players.append(
            YahooPlayerInfo(
                player_key=txt(el, "player_key"),
                name=name,
                team_abbr=txt(el, "editorial_team_abbr"),
                positions=[p for p in eligible if p not in GENERIC_SLOTS],
                status=txt(el, "status"),
                injury_note=txt(el, "injury_note"),
                average_pick=num(analysis, "average_pick"),
                percent_drafted=num(analysis, "percent_drafted"),
                rank=(start_rank + n) if start_rank is not None else None,
                selected_position=txt(el, "selected_position/position"),
            )
        )
    return players


# ---------- endpoints ----------


def league_key_for(league_id: str) -> str:
    """Docs, League Resource: 'League key format: {game_key}.l.{league_id} - Example: nfl.l.1000'."""
    return f"nba.l.{league_id}"


def user_nba_leagues(client: YahooClient) -> list[YahooLeague]:
    # Docs, User APIs -> games/leagues: /users;use_login=1/games;game_keys={game_key1}/leagues
    return parse_leagues(client.get("users;use_login=1/games;game_keys=nba/leagues", ttl=600))


def league_settings(client: YahooClient, league_key: str) -> LeagueSettings:
    # Docs, League Resource -> settings: /league/{league_key}/settings
    return parse_settings(client.get(f"league/{league_key}/settings", ttl=600))


def league_teams(client: YahooClient, league_key: str) -> list[YahooTeam]:
    # Docs, League Resource -> teams: /league/{league_key}/teams
    return parse_teams(client.get(f"league/{league_key}/teams", ttl=300))


def draft_results(client: YahooClient, league_key: str) -> tuple[str, list[DraftResult]]:
    # Docs, League Resource -> draftresults: /league/{league_key}/draftresults (never cached: live draft)
    return parse_draft_results(client.get(f"league/{league_key}/draftresults", ttl=0))


def players_ranked(
    client: YahooClient, league_key: str, start: int, count: int = 25
) -> list[YahooPlayerInfo]:
    # Docs, Players Collection filters: sort=OR (overall rank), start, count;
    # Player Resource sub-resource draft_analysis ("any sub-resource valid for a player is valid under players")
    path = f"league/{league_key}/players;sort=OR;start={start};count={count}/draft_analysis"
    return parse_players(client.get(path, ttl=3600), start_rank=start + 1)


def players_by_keys(client: YahooClient, league_key: str, keys: list[str]) -> list[YahooPlayerInfo]:
    # Docs, Players Collection: /league/{league_key}/players;player_keys={key1},{key2}
    result: list[YahooPlayerInfo] = []
    for i in range(0, len(keys), 25):
        chunk = ",".join(keys[i : i + 25])
        result.extend(parse_players(client.get(f"league/{league_key}/players;player_keys={chunk}", ttl=3600)))
    return result


def team_roster(client: YahooClient, team_key: str, day: str) -> list[YahooPlayerInfo]:
    # Docs, Roster Resource: /team/{team_key}/roster;date=YYYY-MM-DD (NBA rosters are organised by date)
    return parse_players(client.get(f"team/{team_key}/roster;date={day}", ttl=120))
