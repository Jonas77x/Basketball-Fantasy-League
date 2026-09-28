"""Test doubles for Yahoo: a client serving fixture XML files by URL path."""

from conftest import fixture_text

from fantasy.yahoo.xmlutil import parse

ROUTES = [
    ("users;use_login=1/games;game_keys=nba/leagues", "yahoo_user_leagues.xml"),
    ("/settings", "yahoo_nba_settings.xml"),
    ("/teams", "yahoo_teams.xml"),
    ("/draftresults", "yahoo_draftresults_live.xml"),
    ("/players;sort=OR;start=0;", "yahoo_players_ranked.xml"),
    ("/players;player_keys=", "yahoo_players_ranked.xml"),
]


class FakeClient:
    def __init__(self, overrides: dict[str, str] | None = None):
        self.calls: list[str] = []
        self.overrides = overrides or {}

    def get(self, path: str, ttl: float = 60.0):
        self.calls.append(path)
        for needle, text in self.overrides.items():
            if needle in path:
                return parse(text)
        for needle, name in ROUTES:
            if needle in path:
                return parse(fixture_text(name))
        if "/players;sort=OR;start=" in path:  # later pages: empty
            return parse('<fantasy_content><league><players count="0"/></league></fantasy_content>')
        raise AssertionError(f"unexpected Yahoo path {path}")
