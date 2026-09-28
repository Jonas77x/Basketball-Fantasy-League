"""Name normalization and team abbreviations, so players from different sources can be matched."""

import re
import unicodedata

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# Different spellings of the same player across sources (normalized form -> canonical normalized form).
ALIASES = {
    "nicolas claxton": "nic claxton",
    "cameron thomas": "cam thomas",
    "herb jones": "herbert jones",
    "moe wagner": "moritz wagner",
    "alex sarr": "alexandre sarr",
    "carlton carrington": "bub carrington",
    "ron holland": "ronald holland",
    "gg jackson": "gregory jackson",
}

TEAM_CODES = {
    "ATL": "ATL", "BOS": "BOS", "BKN": "BKN", "BRK": "BKN", "BK": "BKN", "CHA": "CHA", "CHO": "CHA",
    "CHI": "CHI", "CLE": "CLE", "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GS": "GSW", "GSW": "GSW",
    "HOU": "HOU", "IND": "IND", "LAC": "LAC", "LAL": "LAL", "MEM": "MEM", "MIA": "MIA", "MIL": "MIL",
    "MIN": "MIN", "NO": "NOP", "NOP": "NOP", "NOR": "NOP", "NY": "NYK", "NYK": "NYK", "OKC": "OKC",
    "ORL": "ORL", "PHI": "PHI", "PHO": "PHX", "PHX": "PHX", "POR": "POR", "SAC": "SAC", "SA": "SAS",
    "SAS": "SAS", "TOR": "TOR", "UTA": "UTA", "UTAH": "UTA", "WAS": "WAS", "WSH": "WAS",
}  # fmt: skip


def normalize_name(name: str) -> str:
    """'Luka Dončić' -> 'luka doncic', 'Jaren Jackson Jr.' -> 'jaren jackson'."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("’", "'")
    text = re.sub(r"[.'`]", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    parts = [p for p in text.split() if p not in SUFFIXES]
    key = " ".join(parts)
    return ALIASES.get(key, key)


def normalize_team(code: str) -> str:
    code = (code or "").strip().upper()
    return TEAM_CODES.get(code, code)
