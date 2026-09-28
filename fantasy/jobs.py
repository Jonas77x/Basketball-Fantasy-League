"""Minimal background jobs for long-running user actions (e.g. the ~20 s Yahoo league sync).

Scheduled jobs (daily lineup, news, ...) will use APScheduler in a later phase.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from fantasy.timeutil import utcnow

log = logging.getLogger(__name__)


@dataclass
class JobStatus:
    name: str
    running: bool = False
    ok: bool | None = None
    message: str = ""
    started: datetime | None = None
    finished: datetime | None = None


_jobs: dict[str, JobStatus] = {}
_lock = threading.Lock()


def status(name: str) -> JobStatus:
    with _lock:
        return _jobs.get(name) or JobStatus(name)


def run_background(name: str, fn: Callable[[], str]) -> bool:
    """Start fn in a thread unless a job with this name is running. fn returns a result message."""
    with _lock:
        current = _jobs.get(name)
        if current and current.running:
            return False
        job = JobStatus(name, running=True, started=utcnow(), message="läuft …")
        _jobs[name] = job

    def runner():
        try:
            message = fn()
            job.ok, job.message = True, message
        except Exception as exc:  # shown to Jonas as text
            log.exception("job %s failed", name)
            job.ok, job.message = False, str(exc)
        finally:
            job.running = False
            job.finished = utcnow()

    threading.Thread(target=runner, name=f"job-{name}", daemon=True).start()
    return True


def reset() -> None:
    with _lock:
        _jobs.clear()
