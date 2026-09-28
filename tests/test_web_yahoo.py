import time

import httpx
import pytest
from fastapi.testclient import TestClient
from yahoo_fakes import FakeClient

from fantasy import config, jobs
from fantasy.web import routes_yahoo
from fantasy.web.app import app
from fantasy.yahoo import auth, draftsync

client = TestClient(app)


@pytest.fixture
def yahoo_ready(monkeypatch):
    monkeypatch.setenv("YAHOO_CLIENT_ID", "cid")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "secret")
    config.get_settings.cache_clear()
    monkeypatch.setattr(
        auth.httpx,
        "post",
        lambda *a, **k: httpx.Response(
            200, json={"access_token": "A", "refresh_token": "R", "expires_in": 3600}
        ),
    )
    fake = FakeClient()
    monkeypatch.setattr(routes_yahoo, "get_client", lambda: fake)
    monkeypatch.setattr(draftsync, "get_client", lambda: fake)
    return fake


def wait_for_job(name):
    for _ in range(100):
        if not jobs.status(name).running:
            return jobs.status(name)
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_yahoo_page_without_credentials():
    page = client.get("/yahoo").text
    assert "YAHOO_CLIENT_ID" in page and "Bei Yahoo anmelden" not in page
    assert "Fantasy data provided by Yahoo Fantasy" in page


def test_connect_sync_and_live_draft(yahoo_ready):
    assert "Bei Yahoo anmelden" in client.get("/yahoo").text
    login = client.get("/yahoo/login", follow_redirects=False)
    assert login.headers["location"].startswith("https://api.login.yahoo.com/oauth2/request_auth")
    state = login.headers["location"].split("state=")[1].split("&")[0]
    connected = client.post(
        "/yahoo/connect", data={"pasted": f"https://localhost:8000/auth/callback?code=C&state={state}"}
    )
    assert "Verbunden" in connected.text

    client.post("/yahoo/sync")
    job = wait_for_job("league-sync")
    assert job.ok, job.message
    assert "Jonas' Team" in job.message and "Position 7" in job.message
    page = client.get("/yahoo").text
    assert "Freunde Liga" in page and "4 pro Woche" in page and "Mo 19.10., 21:00" in page

    draft_page = client.get("/draft").text
    assert "Live-Sync starten" in draft_page
    assert "Jonas&#39; Team" in draft_page or "Du" in draft_page

    # Run one poll directly (the background thread would do the same every few seconds).
    sync = draftsync.get_sync()
    sync.poll_once()
    board = client.get("/draft/live/refresh", params={"v": "old"})
    assert board.status_code == 200 and "Nikola Jokic" in board.text
    version = board.text.split('id="board-version" name="v" value="')[1].split('"')[0]
    assert client.get("/draft/live/refresh", params={"v": version}).status_code == 204


def test_sync_start_and_stop_buttons(yahoo_ready):
    client.post("/yahoo/connect", data={"pasted": "CODE"})
    started = client.post("/draft/live/sync/start")
    assert "Yahoo-Live-Sync aktiv" in started.text
    stopped = client.post("/draft/live/sync/stop")
    assert "Live-Sync starten" in stopped.text


def test_team_list_without_draft_order(yahoo_ready):
    from fantasy.db import session_scope, set_json
    from fantasy.yahoo import league

    with session_scope() as session:
        set_json(
            session,
            league.KV_SETTINGS,
            {"name": "Liga", "season": "2026", "categories": [], "roster": [], "unsupported_categories": []},
        )
        set_json(
            session,
            league.KV_TEAMS,
            [
                {"team_key": "a", "name": "A", "draft_position": None, "is_mine": True},
                {"team_key": "b", "name": "B", "draft_position": 2, "is_mine": False},
            ],
        )
    page = client.get("/yahoo")
    assert page.status_code == 200 and "A (du)" in page.text


def test_finished_job_does_not_reload_page_forever(yahoo_ready):
    client.post("/yahoo/sync")
    wait_for_job("league-sync")
    assert "location.reload" not in client.get("/yahoo").text
    assert "location.reload" in client.get("/yahoo/job").text
