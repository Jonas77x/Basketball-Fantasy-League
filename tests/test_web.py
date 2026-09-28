import re

from fastapi.testclient import TestClient

from fantasy.web.app import app

client = TestClient(app)


def board_pick(kind: str, **data):
    return client.post(f"/draft/{kind}/pick", data=data)


def test_draft_page_renders():
    response = client.get("/draft")
    assert response.status_code == 200
    assert "Pick eintragen" in response.text
    assert "Du bist dran!" in response.text  # default: position 1, first pick


def test_quick_search_finds_player_with_accent_free_input():
    response = client.get("/draft/live/search", params={"q": "donc"})
    assert response.status_code == 200
    assert "Luka Doncic" in response.text


def test_pick_flow_mine_and_others():
    client.post("/draft/live/settings", data={"teams": 10, "my_slot": 2, "rounds": 13, "risk": "1"})
    first = client.get("/draft/live/search", params={"q": "jokic"})
    player_id = re.search(r'"player_id": "([^"]+)"', first.text).group(1)
    response = board_pick("live", player_id=player_id)
    assert response.status_code == 200
    assert 'id="clock" hx-swap-oob="true"' in response.text
    assert "Du bist dran!" in response.text  # pick 2 belongs to slot 2
    # Same player twice is rejected with a message.
    again = board_pick("live", player_id=player_id)
    assert "schon gedraftet" in again.text
    # My pick shows up in the team panel.
    wemby = re.search(r'"player_id": "([^"]+)"', client.get("/draft/live/search", params={"q": "wemb"}).text)
    mine = board_pick("live", player_id=wemby.group(1))
    assert "Dein Team (1/13)" in mine.text
    # Undo removes it again.
    undone = client.post("/draft/live/undo")
    assert "Dein Team (0/13)" in undone.text


def test_custom_player_not_in_list():
    response = board_pick("live", name="Unbekannter Rookie")
    assert "Unbekannter Rookie" in response.text


def test_practice_mode_simulates_opponents_until_my_turn():
    client.post(
        "/draft/practice/settings", data={"teams": 12, "my_slot": 5, "rounds": 13, "auto_opponents": "1"}
    )
    response = client.post("/draft/practice/simulate")
    assert "Du bist dran!" in response.text
    assert response.text.count('class="no">#') == 4
    # After my pick the opponents pick automatically up to my next pick (20).
    player_id = re.search(r'"player_id": "([^"]+)"', response.text).group(1)
    after = board_pick("practice", player_id=player_id)
    assert after.text.count('class="no">#') == 19
    # The live draft is untouched.
    assert "Dein Team (0/13)" in client.get("/draft").text


def test_punt_toggle():
    response = client.post("/draft/live/punts", data={"toggle": "ft"})
    assert "chip punt" in response.text
    response = client.post("/draft/live/punts", data={"punts": ""})
    assert "chip punt" not in response.text


def test_pool_filter_by_position():
    response = client.get("/draft/live/pool", params={"pool_pos": "C", "pool_limit": 20})
    assert response.status_code == 200
    positions = re.findall(r"<span>[A-Z]{2,3}, ([A-Z,]+),", response.text)
    assert positions and all("C" in p.split(",") for p in positions)


def test_ai_without_key_explains_setup():
    response = client.post("/draft/live/ai")
    assert "ANTHROPIC_API_KEY" in response.text
