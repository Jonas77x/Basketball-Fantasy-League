from conftest import fixture_text

from fantasy.players.names import normalize_name, normalize_team
from fantasy.sources import bref, hashtag


def test_parse_totals_keeps_combined_row_and_last_team():
    rows = bref.parse_totals(fixture_text("bref_totals_sample.html"), 2026)
    by_name = {r["name"]: r for r in rows}
    assert set(by_name) == {"Luka Dončić", "James Harden"}  # no "League Average"
    harden = by_name["James Harden"]
    assert harden["team"] == "CLE"
    assert harden["teams"] == "LAC/CLE"
    assert harden["games"] == 70
    luka = by_name["Luka Dončić"]
    assert luka["pts"] == 2143 and luka["mp"] == 2289 and luka["bref_id"] == "doncilu01"


def test_parse_draft_skips_header_rows():
    picks = bref.parse_draft(fixture_text("bref_draft_sample.html"), 2026)
    assert [p["pick"] for p in picks] == [1, 2, 3]
    assert picks[0]["name"] == "AJ Dybantsa" and picks[0]["team"] == "WAS"


def test_parse_adp_reads_yahoo_columns():
    players = hashtag.parse_adp(fixture_text("hashtag_adp_sample.html"))
    by_name = {p["name"]: p for p in players}
    assert by_name["Nikola Jokic"]["yahoo_adp"] == 1.9
    assert by_name["Nikola Jokic"]["yahoo_pos"] == "C"
    shead = by_name["Jamal Shead"]
    assert shead["yahoo_adp"] is None and shead["blend_adp"] == 244.1 and shead["yahoo_pos"] == "PG"


def test_name_normalization_matches_sources():
    assert normalize_name("Luka Dončić") == normalize_name("Luka Doncic")
    assert normalize_name("Alperen Şengün") == normalize_name("Alperen Sengün")
    assert normalize_name("Jimmy Butler III") == normalize_name("Jimmy Butler")
    assert normalize_name("Jaren Jackson Jr.") == "jaren jackson"
    assert normalize_name("De'Aaron Fox") == "deaaron fox"


def test_team_codes():
    assert normalize_team("BRK") == "BKN"
    assert normalize_team("SA") == "SAS"
    assert normalize_team("pho") == "PHX"
