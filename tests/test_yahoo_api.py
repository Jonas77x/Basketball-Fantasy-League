from conftest import fixture_text

from fantasy.engine.draft import DraftSettings
from fantasy.yahoo import api, league
from fantasy.yahoo.xmlutil import parse


def load(name):
    return parse(fixture_text(name))


def test_user_leagues():
    leagues = api.parse_leagues(load("yahoo_user_leagues.xml"))
    assert [lg.league_key for lg in leagues] == ["470.l.60530", "470.l.99999"]
    assert leagues[0].num_teams == 12 and leagues[0].draft_status == "predraft"


def test_nba_settings_and_category_mapping():
    settings = api.parse_settings(load("yahoo_nba_settings.xml"))
    assert settings.draft_type == "live" and not settings.is_auction
    assert settings.max_weekly_adds == 4 and settings.playoff_start_week == 19
    assert settings.draft_time.isoformat() == "2026-10-19T19:00:00+00:00"  # 21:00 in Berlin
    keys, unsupported = league.map_categories(settings.stat_categories)
    assert keys == ["fg", "ft", "tpm", "pts", "reb", "ast", "stl", "blk", "to"]
    assert unsupported == []
    slots = league.roster_slots(settings.roster_positions)
    assert len(slots) == 13 and slots.count("UTIL") == 2 and slots.count("C") == 2 and "IL" not in slots


def test_official_docs_samples_parse():
    nfl = api.parse_settings(load("yahoo_docs_settings_nfl.xml"))
    keys, unsupported = league.map_categories(nfl.stat_categories)
    assert unsupported  # football categories are not basketball categories
    team = api.parse_teams(load("yahoo_docs_team.xml"))[0]
    assert team.draft_position == 8 and team.name == "marky's Bold Team"
    roster = api.parse_players(load("yahoo_docs_roster.xml"))
    assert len(roster) == 15 and roster[0].name == "Kyler Murray" and roster[0].selected_position
    player = api.parse_players(load("yahoo_docs_player.xml"))[0]
    assert player.name == "Christian McCaffrey"


def test_teams_mine_and_draft_order():
    teams = api.parse_teams(load("yahoo_teams.xml"))
    mine = [t for t in teams if t.is_mine]
    assert len(teams) == 12 and len(mine) == 1
    assert mine[0].name == "Jonas' Team" and mine[0].draft_position == 7


def test_draft_results_during_live_draft():
    status, results = api.parse_draft_results(load("yahoo_draftresults_live.xml"))
    assert status == "drafting"
    assert len(results) == 156
    made = [r for r in results if r.player_key]
    assert [r.pick for r in made] == list(range(1, 8))


def test_players_with_draft_analysis():
    players = api.parse_players(load("yahoo_players_ranked.xml"), start_rank=1)
    jokic = players[0]
    assert jokic.name == "Nikola Jokić" and jokic.positions == ["C"] and jokic.rank == 1
    assert jokic.average_pick == 1.9
    hali = next(p for p in players if p.name == "Tyrese Haliburton")
    assert hali.status == "INJ" and hali.positions == ["PG", "SG"]
    newcomer = players[-1]
    assert newcomer.average_pick is None  # "-" in Yahoo's XML


def test_draft_settings_from_yahoo_keeps_punts():
    settings = api.parse_settings(load("yahoo_nba_settings.xml"))
    teams = api.parse_teams(load("yahoo_teams.xml"))
    old = DraftSettings(teams=10, my_slot=1, rounds=12, punts=["ft"], risk=False)
    new = league.draft_settings_from_yahoo(settings, teams, old)
    assert (new.teams, new.my_slot, new.rounds) == (12, 7, 13)
    assert new.punts == ["ft"] and new.risk is False
    assert new.team_names[0] == "Brick City" and new.team_names[6] == "Jonas' Team"
