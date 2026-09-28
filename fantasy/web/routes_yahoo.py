"""Yahoo page: connect (OAuth), choose and sync the league, watch the live-draft sync log."""

from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from fantasy import jobs
from fantasy.config import get_settings
from fantasy.db import SyncLog, as_utc, get_json, session_scope, set_json
from fantasy.players.catalog import get_catalog
from fantasy.timeutil import format_display
from fantasy.web.common import templates
from fantasy.web.routes_draft import sync_view
from fantasy.yahoo import api, auth, league
from fantasy.yahoo.client import get_client
from fantasy.yahoo.errors import YahooError

router = APIRouter()
KV_USER_LEAGUES = "yahoo_user_leagues"


def _redirect(message: str = "", error: bool = False) -> RedirectResponse:
    target = "/yahoo"
    if message:
        target += f"?{'error' if error else 'msg'}={quote(message)}"
    return RedirectResponse(target, status_code=303)


def _page_context(request: Request, msg: str, error: str) -> dict:
    settings = get_settings()
    info = league.league_info()
    with session_scope() as session:
        user_leagues = get_json(session, KV_USER_LEAGUES, []) or []
        logs = session.scalars(select(SyncLog).order_by(SyncLog.id.desc()).limit(25)).all()
        log_rows = [
            {"time": format_display(as_utc(r.created_at)), "kind": r.kind, "message": r.message, "ok": r.ok}
            for r in logs
        ]
    job = jobs.status("league-sync")
    return {
        "request": request,
        "msg": msg,
        "error": error,
        "configured": settings.yahoo_configured,
        "connected": settings.yahoo_configured and auth.is_connected(),
        "redirect_uri": settings.yahoo_redirect_uri,
        "league_key": league.active_league_key(),
        "league_id_env": settings.yahoo_league_id,
        "info": info,
        "teams_sorted": sorted(
            info["teams"], key=lambda t: (t.get("draft_position") or 99, t.get("name", ""))
        ),
        "user_leagues": user_leagues,
        "job": job,
        "logs": log_rows,
        "sync": sync_view(),
    }


@router.get("/yahoo", response_class=HTMLResponse)
def yahoo_page(request: Request, msg: str = "", error: str = ""):
    return templates.TemplateResponse(request, "yahoo.html", _page_context(request, msg, error))


@router.get("/yahoo/login")
def yahoo_login():
    try:
        return RedirectResponse(auth.authorization_url(), status_code=302)
    except YahooError as exc:
        return _redirect(str(exc), error=True)


@router.post("/yahoo/connect")
def yahoo_connect(pasted: str = Form("")):
    try:
        auth.connect(pasted)
    except YahooError as exc:
        return _redirect(str(exc), error=True)
    return _redirect("Verbunden! Jetzt die Liga synchronisieren.")


@router.get("/auth/callback")
def auth_callback(request: Request):
    """Direct callback when the app runs behind https (e.g. on the server later)."""
    try:
        auth.connect(str(request.url))
    except YahooError as exc:
        return _redirect(str(exc), error=True)
    return _redirect("Verbunden! Jetzt die Liga synchronisieren.")


@router.post("/yahoo/disconnect")
def yahoo_disconnect():
    auth.disconnect()
    return _redirect("Verbindung getrennt. Du kannst dich jederzeit neu verbinden.")


@router.post("/yahoo/leagues")
def yahoo_leagues():
    try:
        leagues = api.user_nba_leagues(get_client())
    except YahooError as exc:
        return _redirect(str(exc), error=True)
    with session_scope() as session:
        set_json(
            session,
            KV_USER_LEAGUES,
            [
                {
                    "league_key": lg.league_key,
                    "name": lg.name,
                    "num_teams": lg.num_teams,
                    "draft_status": lg.draft_status,
                    "season": lg.season,
                }
                for lg in leagues
            ],
        )
    return _redirect(f"{len(leagues)} Basketball-Liga(en) gefunden.")


@router.post("/yahoo/league")
def choose_league(league_key: str = Form(...)):
    league.set_active_league(league_key.strip())
    return _redirect("Liga ausgewählt. Jetzt synchronisieren.")


@router.post("/yahoo/sync")
def start_league_sync():
    def work() -> str:
        summary = league.sync_league(get_client(), list(get_catalog()))
        text = (
            f"{summary.league_name}: {summary.teams} Teams, dein Team „{summary.my_team}“"
            + (
                f" pickt an Position {summary.my_slot}"
                if summary.my_slot
                else " (Draft-Reihenfolge noch offen)"
            )
            + f", {summary.players} Spieler geladen"
        )
        if summary.unmatched:
            text += f", {summary.unmatched} davon ohne eigene Projektion"
        if summary.unsupported_categories:
            text += f". Achtung, nicht unterstützte Kategorien: {', '.join(summary.unsupported_categories)}"
        return text + "."

    jobs.run_background("league-sync", work)
    return _redirect()


@router.get("/yahoo/job", response_class=HTMLResponse)
def job_status(request: Request):
    return templates.TemplateResponse(
        request, "_job.html", {"job": jobs.status("league-sync"), "polled": True}
    )
