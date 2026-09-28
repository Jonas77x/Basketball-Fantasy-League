"""Hashtag Basketball: average draft position (ADP) per platform, incl. Yahoo positions.

Page: https://hashtagbasketball.com/fantasy-basketball-adp  (fetched at most once a day)
"""

from bs4 import BeautifulSoup

from fantasy.sources.http import fetch_text

URL = "https://hashtagbasketball.com/fantasy-basketball-adp"


def _float_or_none(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _positions(cell) -> str:
    return " ".join(seg.get_text(strip=True) for seg in cell.select(".pos-pill__seg"))


def parse_adp(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="rawDataTable")
    if table is None:
        raise ValueError("rawDataTable not found")
    players = []
    for row in table.find_all("tr"):
        if not row.get("data-madp") and not row.get("data-yadp"):
            continue
        cells = row.find_all("td")
        link = cells[0].find("a")
        if link is None:
            continue
        pos_cells = row.select("td.adp-pos-col")
        yahoo_pos = _positions(pos_cells[0]) if pos_cells else ""
        espn_pos = _positions(pos_cells[1]) if len(pos_cells) > 1 else ""
        players.append(
            {
                "hashtag_id": link.get("href", "").strip("/").split("/")[0],
                "name": link.get_text(strip=True),
                "team": cells[1].get_text(strip=True),
                "yahoo_pos": yahoo_pos or espn_pos,
                "yahoo_adp": _float_or_none(row.get("data-yadp")),
                "espn_adp": _float_or_none(row.get("data-eadp")),
                "fantrax_adp": _float_or_none(row.get("data-fadp")),
                "blend_adp": _float_or_none(row.get("data-madp")),
            }
        )
    return players


def fetch_adp(max_age_hours: float = 24.0) -> list[dict]:
    return parse_adp(fetch_text(URL, max_age_hours=max_age_hours))
