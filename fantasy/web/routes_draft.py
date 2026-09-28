"""Draft room routes (manual entry, practice draft, Yahoo live sync, AI advice)."""

import json

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from fantasy import draftroom
from fantasy.ai.client import AiUnavailable
from fantasy.ai.draft_advice import draft_advice
from fantasy.config import get_settings
from fantasy.db import session_scope
from fantasy.engine.categories import CATEGORIES
from fantasy.engine.draft import DraftSettings
from fantasy.sources.snapshots import read_meta
from fantasy.web.common import PoolFormDep, PoolQueryDep, check_kind, templates
from fantasy.web.draft_view import PoolParams, build_view, search
from fantasy.yahoo import auth
from fantasy.yahoo.draftsync import get_sync, seconds_since

router = APIRouter()


def sync_view() -> dict:
    settings = get_settings()
    connected = settings.yahoo_configured and auth.is_connected()
    status = get_sync().status
    return {
        "connected": connected,
        "running": status.running,
        "picks_made": status.picks_made,
        "draft_status": status.draft_status,
        "ago": seconds_since(status.last_poll),
        "interval": status.interval,
        "error": status.error,
        "unmatched": status.unmatched[-3:],
    }


def context(request: Request, kind: str, pool: PoolParams, message: str = "") -> dict:
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        view = build_view(draft, kind, pool)
    return {
        "request": request,
        "v": view,
        "message": message,
        "ai_enabled": get_settings().ai_enabled,
        "meta": read_meta(),
        "sync": sync_view(),
    }


def board(request: Request, kind: str, pool: PoolParams, message: str = "") -> HTMLResponse:
    return templates.TemplateResponse(request, "draft/_board.html", context(request, kind, pool, message))


@router.get("/draft", response_class=HTMLResponse)
def draft_page(request: Request, kind: str = "live"):
    kind = check_kind(kind)
    return templates.TemplateResponse(request, "draft/page.html", context(request, kind, PoolParams()))


@router.get("/draft/{kind}/refresh")
def refresh(request: Request, kind: str, pool: PoolQueryDep, v: str = ""):
    """Polled by the browser: returns the board only if something changed (other device, Yahoo sync)."""
    kind = check_kind(kind)
    with session_scope() as session:
        current = draftroom.version_of(draftroom.get_draft(session, kind))
    if current == v:
        return Response(status_code=204)
    return board(request, kind, pool)


@router.post("/draft/{kind}/pick", response_class=HTMLResponse)
def pick(request: Request, kind: str, pool: PoolFormDep, player_id: str = Form(""), name: str = Form("")):
    kind = check_kind(kind)
    message = ""
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        try:
            row = draftroom.add_pick(session, draft, player_id=player_id or None, name=name or None)
            if kind == "practice" and row.mine and draftroom.options_of(draft).get("auto_opponents", True):
                draftroom.simulate_opponents(session, draft, seed=row.overall)
        except draftroom.PickError as exc:
            message = str(exc)
    return board(request, kind, pool, message)


@router.post("/draft/{kind}/undo", response_class=HTMLResponse)
def undo(request: Request, kind: str, pool: PoolFormDep):
    kind = check_kind(kind)
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        if kind == "practice":
            draftroom.undo_to_my_last_pick(session, draft)
        else:
            draftroom.undo_last(session, draft)
    return board(request, kind, pool)


@router.post("/draft/{kind}/simulate", response_class=HTMLResponse)
def simulate_opponents(request: Request, kind: str, pool: PoolFormDep):
    kind = check_kind(kind)
    if kind != "practice":
        raise HTTPException(400, "Nur im Übungs-Draft")
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        draftroom.simulate_opponents(session, draft, seed=len(draft.picks) + 1)
    return board(request, kind, pool)


@router.post("/draft/{kind}/punts", response_class=HTMLResponse)
def set_punts(request: Request, kind: str, pool: PoolFormDep, punts: str = Form(""), toggle: str = Form("")):
    kind = check_kind(kind)
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        settings = draftroom.settings_of(draft)
        if toggle in CATEGORIES:
            current = set(settings.punts) ^ {toggle}
            settings.punts = [c for c in settings.categories if c in current]
        else:
            chosen = {c for c in punts.split(",") if c in CATEGORIES}
            settings.punts = [c for c in settings.categories if c in chosen]
        draftroom.save_settings(draft, settings)
    return board(request, kind, pool)


@router.post("/draft/{kind}/settings")
def save_settings(
    kind: str,
    teams: int = Form(12),
    my_slot: int = Form(1),
    rounds: int = Form(13),
    risk: str = Form(""),
    roster: str = Form(""),
    team_names: str = Form(""),
    auto_opponents: str = Form(""),
):
    kind = check_kind(kind)
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        old = draftroom.settings_of(draft)
        slots = [s.strip().upper() for s in roster.replace(",", " ").split() if s.strip()]
        names = [n.strip() for n in team_names.splitlines()]
        settings = DraftSettings(
            teams=max(4, min(teams, 20)),
            my_slot=my_slot,
            rounds=max(5, min(rounds, 25)),
            categories=old.categories,
            punts=old.punts,
            roster=slots or old.roster,
            risk=bool(risk),
            team_names=names if any(names) else [],
        )
        settings.my_slot = max(1, min(settings.my_slot, settings.teams))
        draftroom.save_settings(draft, settings)
        if kind == "practice":
            draft.options_json = json.dumps({"auto_opponents": bool(auto_opponents)})
    return RedirectResponse(f"/draft?kind={kind}", status_code=303)


@router.post("/draft/{kind}/reset")
def reset(kind: str):
    kind = check_kind(kind)
    with session_scope() as session:
        draftroom.reset(session, draftroom.get_draft(session, kind))
    return RedirectResponse(f"/draft?kind={kind}", status_code=303)


@router.get("/draft/{kind}/search", response_class=HTMLResponse)
def quick_search(request: Request, kind: str, q: str = ""):
    kind = check_kind(kind)
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        hits = search(draft, q)
        state = draftroom.state_of(draft)
    return templates.TemplateResponse(
        request,
        "draft/_search.html",
        {"hits": hits, "q": q, "kind": kind, "my_turn": state.is_my_turn, "done": state.is_done},
    )


@router.get("/draft/{kind}/pool", response_class=HTMLResponse)
def pool_list(request: Request, kind: str, pool: PoolQueryDep):
    kind = check_kind(kind)
    return templates.TemplateResponse(request, "draft/_pool.html", context(request, kind, pool))


@router.post("/draft/{kind}/ai", response_class=HTMLResponse)
def ai_advice(request: Request, kind: str):
    kind = check_kind(kind)
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        state = draftroom.state_of(draft)
        advisor = draftroom.advisor_for(draft)
        analysis = advisor.analyze(state, seed=state.current_pick)
    try:
        result = draft_advice(state, analysis, {p.id: p for p in advisor.players})
        cost = (
            "aus dem Zwischenspeicher" if result.cached else f"Kosten ca. {result.cost_usd * 100:.1f} US-Cent"
        )
        text = f"{result.text}\n\n({cost})"
    except AiUnavailable as exc:
        text = str(exc)
    return HTMLResponse(templates.get_template("draft/_ai.html").render(text=text))


# ---------- Yahoo live sync ----------


def _sync_box(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "draft/_sync.html", {"sync": sync_view()})


@router.get("/draft/live/sync/status", response_class=HTMLResponse)
def sync_status(request: Request):
    return _sync_box(request)


@router.post("/draft/live/sync/start", response_class=HTMLResponse)
def sync_start(request: Request):
    if sync_view()["connected"]:
        get_sync().start()
    return _sync_box(request)


@router.post("/draft/live/sync/stop", response_class=HTMLResponse)
def sync_stop(request: Request):
    get_sync().stop()
    return _sync_box(request)
