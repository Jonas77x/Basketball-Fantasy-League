from conftest import fixture_text
from yahoo_fakes import FakeClient

from fantasy import draftroom
from fantasy.db import SyncLog, session_scope
from fantasy.players.catalog import get_catalog
from fantasy.yahoo import league
from fantasy.yahoo.draftsync import DraftSync
from fantasy.yahoo.errors import YahooNotAuthorized


def setup_function():
    league.set_active_league("nba.l.60530")


def live_state():
    with session_scope() as session:
        return draftroom.state_of(draftroom.get_draft(session, "live"))


def test_league_sync_updates_draft_settings_and_players():
    client = FakeClient()
    summary = league.sync_league(client, list(get_catalog()), player_pages=2)
    assert summary.league_key == "470.l.60530"
    assert (summary.teams, summary.my_team, summary.my_slot) == (12, "Jonas' Team", 7)
    assert summary.players == 8 and summary.unmatched == 1  # "Unknown Newcomer" is not in our catalog
    settings = live_state().settings
    assert (settings.teams, settings.my_slot, settings.rounds) == (12, 7, 13)
    assert settings.categories[0] == "fg"
    info = league.league_info()
    assert info["settings"]["max_weekly_adds"] == 4
    assert info["settings"]["draft_time_display"] == "Mo 19.10., 21:00"
    assert league.active_league_key() == "470.l.60530"


def test_overlay_uses_yahoo_adp_and_status():
    league.sync_league(FakeClient(), list(get_catalog()), player_pages=1)
    players = {p.name: p for p in draftroom.players_for_draft()}
    assert players["Nikola Jokic"].adp == 1.9
    hali = players["Tyrese Haliburton"]
    assert hali.notes[0].startswith("Yahoo-Status: INJ")


def test_draft_sync_mirrors_yahoo_picks():
    client = FakeClient()
    league.sync_league(client, list(get_catalog()), player_pages=1)
    sync = DraftSync(client_factory=lambda: client)
    interval = sync.poll_once()
    state = live_state()
    assert len(state.picks) == 7
    assert state.picks[0].name == "Nikola Jokic"
    mine = [p for p in state.picks if p.mine]
    assert [p.overall for p in mine] == [7]  # Jonas has draft position 7
    assert interval == 8.0  # next own pick (18) is still far away
    assert sync.status.picks_made == 7 and sync.status.draft_status == "drafting"
    # A second poll without news changes nothing.
    sync.poll_once()
    assert sync.status.last_change is not None
    with session_scope() as session:
        logs = session.query(SyncLog).filter(SyncLog.kind == "draft").all()
    assert len(logs) == 2 and "7 Picks" in logs[-1].message


def test_manual_picks_ahead_of_yahoo_are_kept():
    client = FakeClient()
    league.sync_league(client, list(get_catalog()), player_pages=1)
    catalog = {p.name: p for p in get_catalog()}
    with session_scope() as session:
        draft = draftroom.get_draft(session, "live")
        for name in [
            "Nikola Jokic",
            "Victor Wembanyama",
            "Shai Gilgeous-Alexander",
            "Luka Doncic",
            "Tyrese Haliburton",
            "Anthony Edwards",
            "Cade Cunningham",
            "Tyrese Maxey",
            "Jalen Brunson",
        ]:
            draftroom.add_pick(session, draft, player_id=catalog[name].id)
    DraftSync(client_factory=lambda: client).poll_once()
    state = live_state()
    assert len(state.picks) == 9  # 7 from Yahoo + 2 typed in faster than the API
    assert [p.name for p in state.picks[7:]] == ["Tyrese Maxey", "Jalen Brunson"]


def test_unknown_player_is_fetched_and_kept_by_name():
    draft_xml = fixture_text("yahoo_draftresults_live.xml").replace("470.p.6021", "470.p.9001")
    client = FakeClient(overrides={"/draftresults": draft_xml})
    sync = DraftSync(client_factory=lambda: client)
    sync.poll_once()
    assert any("player_keys=" in c for c in client.calls)
    state = live_state()
    assert state.picks[6].name == "Unknown Newcomer" and state.picks[6].player_id is None
    assert sync.status.unmatched == ["Unknown Newcomer"]


def test_sync_stops_on_403():
    class Denied:
        def get(self, path, ttl=60.0):
            raise YahooNotAuthorized()

    sync = DraftSync(client_factory=Denied)
    sync.status.running = True
    assert sync.poll_once() == 0.0
    assert not sync.status.running and "403" in sync.status.error


def test_backoff_after_errors():
    class Broken:
        def get(self, path, ttl=60.0):
            raise ValueError("kaputt")

    sync = DraftSync(client_factory=Broken)
    assert [sync.poll_once() for _ in range(5)] == [5.0, 10.0, 20.0, 40.0, 60.0]
