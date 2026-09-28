"""Fantasy stat categories (Yahoo default: 9 categories)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    kind: str  # "count" or "pct"
    negative: bool = False  # True for turnovers: fewer is better
    makes: str = ""  # pct categories: projection keys for makes/attempts
    attempts: str = ""


CATEGORIES: dict[str, Category] = {
    c.key: c
    for c in [
        Category("pts", "PTS", "count"),
        Category("reb", "REB", "count"),
        Category("ast", "AST", "count"),
        Category("stl", "STL", "count"),
        Category("blk", "BLK", "count"),
        Category("tpm", "3PM", "count"),
        Category("fg", "FG%", "pct", makes="fgm", attempts="fga"),
        Category("ft", "FT%", "pct", makes="ftm", attempts="fta"),
        Category("to", "TO", "count", negative=True),
    ]
}

DEFAULT_CATEGORIES = list(CATEGORIES)

# Projection key for each counting category.
PROJ_KEY = {"pts": "pts", "reb": "reb", "ast": "ast", "stl": "stl", "blk": "blk", "tpm": "tpm", "to": "tov"}


def label(key: str) -> str:
    return CATEGORIES[key].label


def labels(keys) -> list[str]:
    return [CATEGORIES[k].label for k in keys]
