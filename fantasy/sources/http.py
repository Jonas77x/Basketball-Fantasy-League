"""Polite HTTP fetching: per-host minimum interval plus a simple disk cache."""

import hashlib
import logging
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from fantasy.config import get_settings

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

# Minimum seconds between two requests to the same host (see CLAUDE.md).
HOST_INTERVALS = {
    "www.basketball-reference.com": 4.0,
    "hashtagbasketball.com": 5.0,
}
DEFAULT_INTERVAL = 2.0

_last_request: dict[str, float] = {}
_lock = threading.Lock()


class FetchError(RuntimeError):
    pass


def _wait_for_host(host: str) -> None:
    interval = HOST_INTERVALS.get(host, DEFAULT_INTERVAL)
    with _lock:
        last = _last_request.get(host, 0.0)
        wait = last + interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request[host] = time.monotonic()


def _cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode()).hexdigest()[:24]
    return get_settings().cache_dir / f"{digest}.html"


def fetch_text(url: str, max_age_hours: float = 12.0, timeout: float = 30.0) -> str:
    """Fetch a URL as text, served from the disk cache when fresh enough."""
    path = _cache_path(url)
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age_hours * 3600:
        return path.read_text(encoding="utf-8")

    host = urlparse(url).netloc
    _wait_for_host(host)
    log.info("GET %s", url)
    try:
        response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise FetchError(f"{url}: {exc}") from exc
    if response.status_code == 429:
        raise FetchError(f"{url}: rate limited (429) – später erneut versuchen")
    if response.status_code != 200:
        raise FetchError(f"{url}: HTTP {response.status_code}")
    path.write_text(response.text, encoding="utf-8")
    return response.text
