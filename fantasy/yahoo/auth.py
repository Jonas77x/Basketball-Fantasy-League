"""Yahoo OAuth 2.0 (authorization code flow).

Source: https://developer.yahoo.com/oauth2/guide/flows_authcode/
  Step 2  GET  https://api.login.yahoo.com/oauth2/request_auth  (client_id, redirect_uri, response_type=code, state)
  Step 4  POST https://api.login.yahoo.com/oauth2/get_token     (grant_type=authorization_code)
  Step 5  POST https://api.login.yahoo.com/oauth2/get_token     (grant_type=refresh_token)
Access tokens live one hour; the refresh token is stored in the local database.

Locally the app runs on plain http, so Yahoo's redirect to https://localhost:8000/auth/callback shows an
error page. Jonas copies the address from the browser bar and pastes it into the app – `extract_code`
accepts that URL, a bare code (redirect "oob") or a proper callback when running behind https.
"""

import base64
import logging
import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from fantasy.config import get_settings
from fantasy.db import OAuthToken, as_utc, get_json, session_scope, set_json
from fantasy.timeutil import utcnow
from fantasy.yahoo.errors import YahooAuthFailed, YahooNotConfigured, YahooNotConnected

log = logging.getLogger(__name__)

AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
PROVIDER = "yahoo"
REFRESH_MARGIN = timedelta(minutes=5)


def authorization_url() -> str:
    settings = get_settings()
    if not settings.yahoo_configured:
        raise YahooNotConfigured()
    state = secrets.token_urlsafe(16)
    with session_scope() as session:
        set_json(session, "yahoo_oauth_state", {"state": state})
    params = {
        "client_id": settings.yahoo_client_id,
        "redirect_uri": settings.yahoo_redirect_uri,
        "response_type": "code",
        "state": state,
        "language": "de-de",
    }
    if settings.yahoo_scope:
        params["scope"] = settings.yahoo_scope
    return f"{AUTH_URL}?{urlencode(params)}"


def extract_code(pasted: str) -> tuple[str, str | None]:
    """Get (code, state) from a pasted callback URL or a bare code."""
    text = pasted.strip()
    if not text:
        raise YahooAuthFailed("Bitte die Adresse aus der Adresszeile (oder den Code von Yahoo) einfügen.")
    if "code=" in text:
        query = parse_qs(urlparse(text).query) if "://" in text else parse_qs(text.lstrip("?"))
        if "error" in query:
            raise YahooAuthFailed(f"Yahoo meldet: {query.get('error_description', query['error'])[0]}")
        codes = query.get("code")
        if not codes:
            raise YahooAuthFailed("In der Adresse steht kein Code. Bitte die komplette Adresse kopieren.")
        return codes[0], (query.get("state") or [None])[0]
    if " " in text or "/" in text:
        raise YahooAuthFailed("Das sieht nicht nach einer Yahoo-Adresse oder einem Code aus.")
    return text, None


def _token_request(data: dict) -> dict:
    settings = get_settings()
    basic = base64.b64encode(f"{settings.yahoo_client_id}:{settings.yahoo_client_secret}".encode()).decode()
    body = {
        "client_id": settings.yahoo_client_id,
        "client_secret": settings.yahoo_client_secret,
        "redirect_uri": settings.yahoo_redirect_uri,
        **data,
    }
    try:
        response = httpx.post(
            TOKEN_URL,
            data=body,
            headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        raise YahooAuthFailed(f"Keine Verbindung zu Yahoo: {exc}") from exc
    if response.status_code != 200:
        try:
            detail = response.json().get("error_description") or response.json().get("error")
        except ValueError:
            detail = response.text[:200]
        log.warning("Yahoo token request failed: HTTP %s %s", response.status_code, detail)
        raise YahooAuthFailed(f"Yahoo hat die Anmeldung abgelehnt (HTTP {response.status_code}): {detail}")
    return response.json()


def _store(payload: dict, previous_refresh: str = "") -> OAuthToken:
    expires = utcnow() + timedelta(seconds=int(payload.get("expires_in", 3600)))
    with session_scope() as session:
        token = session.get(OAuthToken, PROVIDER) or OAuthToken(provider=PROVIDER)
        token.access_token = payload["access_token"]
        token.refresh_token = payload.get("refresh_token") or previous_refresh or token.refresh_token
        token.expires_at = expires
        token.user_guid = payload.get("xoauth_yahoo_guid", token.user_guid or "")
        token.updated_at = utcnow()
        session.merge(token)
    return token


def connect(pasted: str) -> None:
    """Exchange the authorization code for tokens."""
    if not get_settings().yahoo_configured:
        raise YahooNotConfigured()
    code, state = extract_code(pasted)
    with session_scope() as session:
        expected = (get_json(session, "yahoo_oauth_state", {}) or {}).get("state")
    if state and expected and state != expected:
        raise YahooAuthFailed(
            "Der Link passt nicht zur letzten Anmeldung. Bitte „Bei Yahoo anmelden“ neu starten."
        )
    payload = _token_request({"grant_type": "authorization_code", "code": code})
    _store(payload)
    log.info("Yahoo connected")


def disconnect() -> None:
    with session_scope() as session:
        token = session.get(OAuthToken, PROVIDER)
        if token is not None:
            session.delete(token)


def is_connected() -> bool:
    with session_scope() as session:
        return session.get(OAuthToken, PROVIDER) is not None


def access_token(force_refresh: bool = False) -> str:
    """A valid access token, refreshed automatically shortly before it expires."""
    settings = get_settings()
    if not settings.yahoo_configured:
        raise YahooNotConfigured()
    with session_scope() as session:
        token = session.get(OAuthToken, PROVIDER)
        if token is None:
            raise YahooNotConnected()
        current, refresh, expires = token.access_token, token.refresh_token, as_utc(token.expires_at)
    if not force_refresh and expires - REFRESH_MARGIN > utcnow():
        return current
    payload = _token_request({"grant_type": "refresh_token", "refresh_token": refresh})
    return _store(payload, previous_refresh=refresh).access_token
