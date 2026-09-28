"""Live draft sync: polls Yahoo's draftresults and mirrors them into the live draft.

Polling interval adapts to the situation (see CLAUDE.md: 3-10 s during the draft):
  - draft not started yet:      20 s
  - my pick within 2 picks:      3 s
  - my pick within 6 picks:      5 s
  - otherwise:                   8 s
  - after errors: doubling up to 60 s, 90 s when Yahoo throttles.
Every poll is written to the sync log, so after a rehearsal we can see whether Yahoo
really updates draftresults during a live draft. If the sync fails, manual entry keeps working.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

from fantasy import draftroom
from fantasy.db import SyncLog, session_scope
from fantasy.engine.draft import slot_for_pick
from fantasy.players.catalog import get_catalog
from fantasy.timeutil import utcnow
from fantasy.yahoo import api, league
from fantasy.yahoo.client import YahooClient, get_client
from fantasy.yahoo.errors import YahooError, YahooNotAuthorized, YahooRateLimited

log = logging.getLogger(__name__)


@dataclass
class SyncStatus:
    running: bool = False
    league_key: str = ""
    draft_status: str = ""
    picks_made: int = 0
    polls: int = 0
    last_poll: datetime | None = None
    last_change: datetime | None = None
    interval: float = 0.0
    error: str = ""
    errors_in_row: int = 0
    unmatched: list[str] = field(default_factory=list)


class DraftSync:
    def __init__(self, client_factory=None, sleep=None):
        self._client_factory = client_factory  # None: the shared client (looked up at call time)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sleep = sleep or self._stop.wait
        self.status = SyncStatus()

    # ---------- control ----------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.status = SyncStatus(running=True, league_key=league.active_league_key())
        self._thread = threading.Thread(target=self._run, name="draft-sync", daemon=True)
        self._thread.start()
        self._log("Live-Sync gestartet", ok=True)

    def stop(self, reason: str = "Live-Sync gestoppt") -> None:
        self._stop.set()
        if self.status.running:
            self.status.running = False
            self._log(reason, ok=True)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    def _run(self) -> None:
        while not self._stop.is_set():
            interval = self.poll_once()
            if not self.status.running:
                break
            self._sleep(interval)

    # ---------- one poll ----------

    def poll_once(self, client: YahooClient | None = None) -> float:
        """Poll Yahoo once, apply the picks, return seconds until the next poll."""
        client = client or (self._client_factory or get_client)()
        status = self.status
        status.polls += 1
        status.last_poll = utcnow()
        try:
            league_key = status.league_key or league.active_league_key()
            draft_status, results = api.draft_results(client, league_key)
            made = [r for r in results if r.player_key]
            changed = self._apply(client, league_key, made)
            status.draft_status = draft_status
            status.picks_made = len(made)
            status.error = ""
            status.errors_in_row = 0
            if changed:
                status.last_change = utcnow()
            self._log(
                f"Abfrage: Status {draft_status or '?'}, {len(made)} Picks"
                + (" (neu übernommen)" if changed else ""),
                picks=len(made),
                ok=True,
            )
            if draft_status == "postdraft" or len(made) >= self._total_picks():
                self.stop("Draft beendet – Live-Sync automatisch gestoppt")
                return 0.0
            return self._interval(draft_status)
        except YahooNotAuthorized as exc:
            return self._fail(str(exc), stop=True)
        except YahooRateLimited as exc:
            return self._fail(str(exc), wait=90.0)
        except (YahooError, ValueError) as exc:
            return self._fail(str(exc))
        except Exception as exc:  # never let the thread die silently
            log.exception("draft sync crashed")
            return self._fail(f"Unerwarteter Fehler: {exc}")

    def _apply(self, client: YahooClient, league_key: str, made: list[api.DraftResult]) -> bool:
        known = league.known_player_keys()
        missing = [r.player_key for r in made if r.player_key not in known]
        if missing:
            infos = api.players_by_keys(client, league_key, missing)
            league.store_players(infos, list(get_catalog()))
            known = league.known_player_keys()
        my_team = league.my_team_key()
        slots = league.team_slots()
        names = {p.id: p.name for p in get_catalog()}
        with session_scope() as session:
            draft = draftroom.get_draft(session, "live")
            settings = draftroom.settings_of(draft)
            picks = []
            unmatched = []
            for r in made:
                catalog_id, name = known.get(r.player_key, (None, r.player_key))
                if catalog_id is None:
                    unmatched.append(name)
                else:
                    name = names.get(catalog_id, name)
                slot = slots.get(r.team_key) or slot_for_pick(r.pick, settings.teams)
                mine = r.team_key == my_team if my_team else slot == settings.my_slot
                picks.append(draftroom.ExternalPick(r.pick, slot, catalog_id, name, mine))
            self.status.unmatched = unmatched
            return draftroom.apply_external_picks(session, draft, picks)

    def _total_picks(self) -> int:
        with session_scope() as session:
            return draftroom.settings_of(draftroom.get_draft(session, "live")).total_picks

    def _interval(self, draft_status: str) -> float:
        if draft_status != "drafting":
            return 20.0
        with session_scope() as session:
            state = draftroom.state_of(draftroom.get_draft(session, "live"))
        until = state.picks_until_my_turn()
        if state.is_my_turn or until <= 2:
            interval = 3.0
        elif until <= 6:
            interval = 5.0
        else:
            interval = 8.0
        self.status.interval = interval
        return interval

    def _fail(self, message: str, wait: float | None = None, stop: bool = False) -> float:
        status = self.status
        status.errors_in_row += 1
        status.error = message
        self._log(f"Fehler: {message}", ok=False)
        if stop:
            self.stop("Live-Sync gestoppt – bitte Picks von Hand eintragen")
            return 0.0
        interval = wait or min(60.0, 5.0 * 2 ** (status.errors_in_row - 1))
        status.interval = interval
        return interval

    def _log(self, message: str, picks: int | None = None, ok: bool = True) -> None:
        try:
            with session_scope() as session:
                session.add(SyncLog(kind="draft", message=message, picks_made=picks, ok=ok))
        except Exception:  # logging must never break the sync
            log.exception("could not write sync log")


_sync: DraftSync | None = None
_lock = threading.Lock()


def get_sync() -> DraftSync:
    global _sync
    with _lock:
        if _sync is None:
            _sync = DraftSync()
        return _sync


def reset_sync() -> None:
    global _sync
    with _lock:
        if _sync is not None:
            _sync.stop()
        _sync = None


def seconds_since(moment: datetime | None) -> int | None:
    return None if moment is None else int(time.time() - moment.timestamp())
