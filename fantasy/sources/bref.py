"""Basketball-Reference: season totals and the NBA draft.

Pages (public, no API):
  https://www.basketball-reference.com/leagues/NBA_{year}_totals.html   (year = season end, 2026 = 2025-26)
  https://www.basketball-reference.com/draft/NBA_{year}.html
Rate limit: max. 1 request per 4 s (enforced in sources/http.py), results are stored as snapshots.
"""

from bs4 import BeautifulSoup

from fantasy.sources.http import fetch_text

BASE = "https://www.basketball-reference.com"

TOTAL_FIELDS = [
    "games", "games_started", "mp", "fg", "fga", "fg3", "fg3a", "ft", "fta",
    "orb", "drb", "trb", "ast", "stl", "blk", "tov", "pts",
]  # fmt: skip
MULTI_TEAM = {"2TM", "3TM", "4TM", "5TM", "TOT"}


def _num(text: str) -> float:
    text = text.strip()
    return float(text) if text else 0.0


def parse_totals(html: str, season: int) -> list[dict]:
    """Parse a season totals page. Traded players keep only their combined row, with the last team."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="totals_stats")
    if table is None:
        raise ValueError("totals_stats table not found")

    players: dict[str, dict] = {}
    for row in table.find("tbody").find_all("tr"):
        if "thead" in (row.get("class") or []):
            continue
        cells = {c.get("data-stat"): c for c in row.find_all(["th", "td"])}
        name_cell = cells.get("name_display")
        if name_cell is None or not name_cell.get("data-append-csv"):
            continue  # "League Average" and separator rows
        bref_id = name_cell["data-append-csv"]
        team = cells["team_name_abbr"].get_text(strip=True)

        if bref_id in players:
            # Individual team rows after a combined row: remember the most recent team.
            players[bref_id]["team"] = team
            players[bref_id]["teams"].append(team)
            continue

        record = {
            "bref_id": bref_id,
            "name": name_cell.get_text(strip=True),
            "season": season,
            "age": int(_num(cells["age"].get_text())),
            "pos": cells["pos"].get_text(strip=True),
            "team": team,
            "teams": [] if team in MULTI_TEAM else [team],
        }
        for field in TOTAL_FIELDS:
            record[field] = _num(cells[field].get_text()) if field in cells else 0.0
        players[bref_id] = record

    result = []
    for record in players.values():
        record["teams"] = "/".join(record["teams"])
        result.append(record)
    return result


def parse_draft(html: str, year: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="stats")
    if table is None:
        raise ValueError("draft table not found")
    picks = []
    for row in table.find("tbody").find_all("tr"):
        cells = {c.get("data-stat"): c for c in row.find_all(["th", "td"])}
        pick = cells.get("pick_overall")
        if pick is None or not pick.get_text(strip=True).isdigit():
            continue
        picks.append(
            {
                "draft_year": year,
                "pick": int(pick.get_text(strip=True)),
                "team": cells["team_id"].get_text(strip=True),
                "name": cells["player"].get_text(strip=True),
                "college": cells["college_name"].get_text(strip=True) if "college_name" in cells else "",
            }
        )
    return picks


def fetch_totals(season: int, max_age_hours: float = 12.0) -> list[dict]:
    html = fetch_text(f"{BASE}/leagues/NBA_{season}_totals.html", max_age_hours=max_age_hours)
    return parse_totals(html, season)


def fetch_draft(year: int, max_age_hours: float = 12.0) -> list[dict]:
    html = fetch_text(f"{BASE}/draft/NBA_{year}.html", max_age_hours=max_age_hours)
    return parse_draft(html, year)
