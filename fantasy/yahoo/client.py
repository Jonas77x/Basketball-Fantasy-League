"""Central, read-only Yahoo Fantasy API client.

Every Yahoo request goes through here (see CLAUDE.md): rate limit, cache, backoff on 429/999,
automatic token refresh on 401, German errors on 403. Writing to Yahoo is NOT possible through
this client – that is reserved for fantasy/actions/executor.py.

Base URL (docs: https://sports.yahoo.com/developer/docs/ → "API Endpoints"):
  https://fantasysports.yahooapis.com/fantasy/v2
"""

import logging
import threading
import time
import xml.etree.ElementTree as ET

import httpx

from fantasy.yahoo import auth
from fantasy.yahoo.errors import YahooError, YahooNotAuthorized, YahooRateLimited
from fantasy.yahoo.xmlutil import parse

log = logging.getLogger(__name__)

BASE_URL = "https://fantasysports.yahooapis.com/fantasy/v2"
MIN_INTERVAL = 1.0  # seconds between two requests
RATE_LIMIT_STATUS = {429, 999}  # Yahoo answers 999 "Request denied" when throttling
BACKOFF_SECONDS = (5.0, 15.0)


class YahooClient:
    def __init__(
        self,
        http: httpx.Client | None = None,
        token_provider=auth.access_token,
        min_interval: float = MIN_INTERVAL,
        sleep=time.sleep,
    ):
        self._http = http or httpx.Client(timeout=20.0)
        self._token = token_provider
        self._min_interval = min_interval
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last = 0.0
        self._cache: dict[str, tuple[float, ET.Element]] = {}
        self.request_count = 0

    def clear_cache(self) -> None:
        self._cache.clear()

    def get(self, path: str, ttl: float = 60.0) -> ET.Element:
        """GET /fantasy/v2/{path}, parsed XML root (<fantasy_content>). ttl=0 skips the cache."""
        path = path.lstrip("/")
        now = time.monotonic()
        cached = self._cache.get(path)
        if ttl > 0 and cached and now - cached[0] < ttl:
            return cached[1]

        root = self._request(path)
        self._cache[path] = (time.monotonic(), root)
        return root

    def _wait_turn(self) -> None:
        with self._lock:
            wait = self._last + self._min_interval - time.monotonic()
            if wait > 0:
                self._sleep(wait)
            self._last = time.monotonic()

    def _request(self, path: str) -> ET.Element:
        url = f"{BASE_URL}/{path}"
        refreshed = False
        for attempt in range(len(BACKOFF_SECONDS) + 1):
            self._wait_turn()
            token = self._token(force_refresh=refreshed)
            started = time.monotonic()
            try:
                response = self._http.get(url, headers={"Authorization": f"Bearer {token}"})
            except httpx.HTTPError as exc:
                raise YahooError(f"Keine Verbindung zu Yahoo: {exc}") from exc
            self.request_count += 1
            log.info(
                "Yahoo GET %s -> %s (%.0f ms)",
                path,
                response.status_code,
                (time.monotonic() - started) * 1000,
            )

            if response.status_code == 200:
                return parse(response.text)
            if response.status_code == 401 and not refreshed:
                refreshed = True  # expired token: refresh once and retry
                continue
            if response.status_code == 403:
                raise YahooNotAuthorized(_description(response.text))
            if response.status_code in RATE_LIMIT_STATUS:
                if attempt < len(BACKOFF_SECONDS):
                    log.warning(
                        "Yahoo throttling (HTTP %s), waiting %.0f s",
                        response.status_code,
                        BACKOFF_SECONDS[attempt],
                    )
                    self._sleep(BACKOFF_SECONDS[attempt])
                    continue
                raise YahooRateLimited()
            if response.status_code >= 500 and attempt < len(BACKOFF_SECONDS):
                self._sleep(BACKOFF_SECONDS[attempt])
                continue
            raise YahooError(f"Yahoo-Fehler HTTP {response.status_code}: {_description(response.text)}")
        raise YahooError("Yahoo antwortet nicht wie erwartet.")


def _description(body: str) -> str:
    try:
        root = parse(body)
        desc = root.find(".//description")
        if desc is not None and desc.text:
            return desc.text.strip()[:200]
    except ET.ParseError:
        pass
    return body.strip()[:200]


_client: YahooClient | None = None


def get_client() -> YahooClient:
    global _client
    if _client is None:
        _client = YahooClient()
    return _client


def reset_client() -> None:
    global _client
    _client = None
