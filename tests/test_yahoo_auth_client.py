from datetime import timedelta

import httpx
import pytest
from conftest import fixture_text

from fantasy import config
from fantasy.db import OAuthToken, session_scope
from fantasy.timeutil import utcnow
from fantasy.yahoo import auth
from fantasy.yahoo.client import YahooClient
from fantasy.yahoo.errors import YahooAuthFailed, YahooNotAuthorized, YahooNotConfigured, YahooRateLimited


@pytest.fixture
def yahoo_env(monkeypatch):
    monkeypatch.setenv("YAHOO_CLIENT_ID", "cid")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "secret")
    config.get_settings.cache_clear()


class TokenEndpoint:
    def __init__(self):
        self.requests = []

    def __call__(self, url, data=None, headers=None, timeout=None):
        self.requests.append(data)
        n = len(self.requests)
        return httpx.Response(
            200,
            json={
                "access_token": f"access-{n}",
                "refresh_token": f"refresh-{n}",
                "expires_in": 3600,
                "xoauth_yahoo_guid": "GUID",
            },
        )


def test_extract_code_variants():
    assert auth.extract_code("https://localhost:8000/auth/callback?code=abc123&state=xyz") == (
        "abc123",
        "xyz",
    )
    assert auth.extract_code("  abc123 ") == ("abc123", None)
    with pytest.raises(YahooAuthFailed):
        auth.extract_code("https://localhost:8000/auth/callback?error=access_denied&error_description=Nein")
    with pytest.raises(YahooAuthFailed):
        auth.extract_code("")


def test_not_configured():
    with pytest.raises(YahooNotConfigured):
        auth.authorization_url()


def test_connect_and_refresh(yahoo_env, monkeypatch):
    endpoint = TokenEndpoint()
    monkeypatch.setattr(auth.httpx, "post", endpoint)
    url = auth.authorization_url()
    assert "client_id=cid" in url and "response_type=code" in url
    state = url.split("state=")[1].split("&")[0]
    auth.connect(f"https://localhost:8000/auth/callback?code=CODE&state={state}")
    assert endpoint.requests[0]["grant_type"] == "authorization_code"
    assert endpoint.requests[0]["code"] == "CODE"
    assert auth.is_connected()
    assert auth.access_token() == "access-1"  # still valid, no refresh

    with session_scope() as session:
        session.get(OAuthToken, "yahoo").expires_at = utcnow() - timedelta(minutes=1)
    assert auth.access_token() == "access-2"
    assert endpoint.requests[1] == {
        "client_id": "cid",
        "client_secret": "secret",
        "redirect_uri": "https://localhost:8000/auth/callback",
        "grant_type": "refresh_token",
        "refresh_token": "refresh-1",
    }
    auth.disconnect()
    assert not auth.is_connected()


def test_connect_rejects_foreign_state(yahoo_env, monkeypatch):
    monkeypatch.setattr(auth.httpx, "post", TokenEndpoint())
    auth.authorization_url()
    with pytest.raises(YahooAuthFailed):
        auth.connect("https://localhost:8000/auth/callback?code=CODE&state=somebody-else")


def make_client(responses, sleeps=None):
    queue = list(responses)
    seen = []

    def handler(request):
        seen.append(request)
        return queue.pop(0)

    tokens = []

    def token_provider(force_refresh=False):
        tokens.append(force_refresh)
        return "T2" if force_refresh else "T1"

    client = YahooClient(
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        token_provider=token_provider,
        min_interval=0.0,
        sleep=(sleeps.append if sleeps is not None else lambda s: None),
    )
    return client, seen, tokens


def ok():
    return httpx.Response(200, text=fixture_text("yahoo_teams.xml"))


def test_client_parses_and_caches():
    client, seen, _ = make_client([ok()])
    root = client.get("league/nba.l.60530/teams")
    assert root.find("league/name").text == "Freunde Liga"
    client.get("league/nba.l.60530/teams")  # served from cache
    assert len(seen) == 1
    assert seen[0].headers["Authorization"] == "Bearer T1"
    assert str(seen[0].url) == "https://fantasysports.yahooapis.com/fantasy/v2/league/nba.l.60530/teams"


def test_client_refreshes_token_once_on_401():
    client, seen, tokens = make_client([httpx.Response(401), ok()])
    client.get("league/x/teams", ttl=0)
    assert tokens == [False, True] and seen[1].headers["Authorization"] == "Bearer T2"


def test_client_403_explains_approval():
    body = (
        "<error><description>This application is not authorized to perform this action</description></error>"
    )
    client, _, _ = make_client([httpx.Response(403, text=body)])
    with pytest.raises(YahooNotAuthorized, match="not authorized"):
        client.get("league/x/teams")


def test_client_backs_off_when_throttled():
    sleeps = []
    client, _, _ = make_client([httpx.Response(999), ok()], sleeps)
    client.get("league/x/teams")
    assert sleeps == [5.0]
    sleeps.clear()
    client, _, _ = make_client([httpx.Response(429)] * 3, sleeps)
    with pytest.raises(YahooRateLimited):
        client.get("league/x/teams")
    assert sleeps == [5.0, 15.0]


def test_client_is_read_only():
    assert not hasattr(YahooClient, "post") and not hasattr(YahooClient, "put")
