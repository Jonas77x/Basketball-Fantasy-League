"""FastAPI app: draft room (phase 1)."""

import json
import logging
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from fantasy import draftroom
from fantasy.ai.client import AiUnavailable
from fantasy.ai.draft_advice import draft_advice
from fantasy.config import get_settings
from fantasy.db import session_scope
from fantasy.engine.categories import CATEGORIES
from fantasy.engine.draft import DraftSettings
from fantasy.players.catalog import get_catalog
from fantasy.sources.snapshots import read_meta
from fantasy.web.draft_view import SORTS, PoolParams, build_view, search

log = logging.getLogger(__name__)
WEB_DIR = Path(__file__).parent

app = FastAPI(title="Fantasy-Assistent", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=WEB_DIR / "templates")


def fmt_num(value: float | None, digits: int = 1, signed: bool = False) -> str:
    if value is None:
        return "–"
    text = f"{value:+.{digits}f}" if signed else f"{value:.{digits}f}"
    return text.replace(".", ",")


def fmt_pct(value: float | None) -> str:
    return "–" if value is None else f"{round(value * 100)} %"


templates.env.filters["num"] = fmt_num
templates.env.filters["pct"] = fmt_pct


def _kind(kind: str) -> str:
    if kind not in draftroom.KINDS:
        raise HTTPException(404)
    return kind


def _pool_params(q: str = "", pos: str = "Alle", sort: str = "fit", limit: int = 60) -> PoolParams:
    return PoolParams(q=q, pos=pos, sort=sort if sort in SORTS else "fit", limit=max(20, min(limit, 400)))


def _context(request: Request, kind: str, pool: PoolParams, message: str = "", ai_text: str = "") -> dict:
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        view = build_view(draft, kind, pool)
    settings = get_settings()
    return {
        "request": request,
        "v": view,
        "message": message,
        "ai_text": ai_text,
        "ai_enabled": settings.ai_enabled,
        "meta": read_meta(),
    }


def _board(request: Request, kind: str, pool: PoolParams, message: str = "") -> HTMLResponse:
    return templates.TemplateResponse(request, "draft/_board.html", _context(request, kind, pool, message))


@app.get("/")
def index():
    return RedirectResponse("/draft", status_code=303)


@app.get("/health")
def health():
    return JSONResponse({"ok": True, "players": len(get_catalog())})


@app.get("/draft", response_class=HTMLResponse)
def draft_page(request: Request, kind: str = "live"):
    kind = _kind(kind)
    return templates.TemplateResponse(request, "draft/page.html", _context(request, kind, PoolParams()))


@app.post("/draft/{kind}/pick", response_class=HTMLResponse)
def pick(
    request: Request,
    kind: str,
    player_id: str = Form(""),
    name: str = Form(""),
    pool_q: str = Form(""),
    pool_pos: str = Form("Alle"),
    pool_sort: str = Form("fit"),
    pool_limit: int = Form(60),
):
    kind = _kind(kind)
    message = ""
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        try:
            row = draftroom.add_pick(session, draft, player_id=player_id or None, name=name or None)
            if kind == "practice" and row.mine and draftroom.options_of(draft).get("auto_opponents", True):
                draftroom.simulate_opponents(session, draft, seed=row.overall)
        except draftroom.PickError as exc:
            message = str(exc)
    return _board(request, kind, _pool_params(pool_q, pool_pos, pool_sort, pool_limit), message)


@app.post("/draft/{kind}/undo", response_class=HTMLResponse)
def undo(
    request: Request,
    kind: str,
    pool_q: str = Form(""),
    pool_pos: str = Form("Alle"),
    pool_sort: str = Form("fit"),
    pool_limit: int = Form(60),
):
    kind = _kind(kind)
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        if kind == "practice":
            draftroom.undo_to_my_last_pick(session, draft)
        else:
            draftroom.undo_last(session, draft)
    return _board(request, kind, _pool_params(pool_q, pool_pos, pool_sort, pool_limit))


@app.post("/draft/{kind}/simulate", response_class=HTMLResponse)
def simulate_opponents(
    request: Request,
    kind: str,
    pool_q: str = Form(""),
    pool_pos: str = Form("Alle"),
    pool_sort: str = Form("fit"),
    pool_limit: int = Form(60),
):
    kind = _kind(kind)
    if kind != "practice":
        raise HTTPException(400, "Nur im Übungs-Draft")
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        draftroom.simulate_opponents(session, draft, seed=len(draft.picks) + 1)
    return _board(request, kind, _pool_params(pool_q, pool_pos, pool_sort, pool_limit))


@app.post("/draft/{kind}/punts", response_class=HTMLResponse)
def set_punts(
    request: Request,
    kind: str,
    punts: str = Form(""),
    toggle: str = Form(""),
    pool_q: str = Form(""),
    pool_pos: str = Form("Alle"),
    pool_sort: str = Form("fit"),
    pool_limit: int = Form(60),
):
    kind = _kind(kind)
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        settings = draftroom.settings_of(draft)
        if toggle in CATEGORIES:
            current = set(settings.punts)
            current ^= {toggle}
            settings.punts = [c for c in settings.categories if c in current]
        else:
            chosen = {c for c in punts.split(",") if c in CATEGORIES}
            settings.punts = [c for c in settings.categories if c in chosen]
        draftroom.save_settings(draft, settings)
    return _board(request, kind, _pool_params(pool_q, pool_pos, pool_sort, pool_limit))


@app.post("/draft/{kind}/settings")
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
    kind = _kind(kind)
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


@app.post("/draft/{kind}/reset")
def reset(kind: str):
    kind = _kind(kind)
    with session_scope() as session:
        draftroom.reset(session, draftroom.get_draft(session, kind))
    return RedirectResponse(f"/draft?kind={kind}", status_code=303)


@app.get("/draft/{kind}/search", response_class=HTMLResponse)
def quick_search(request: Request, kind: str, q: str = ""):
    kind = _kind(kind)
    with session_scope() as session:
        draft = draftroom.get_draft(session, kind)
        hits = search(draft, q)
        state = draftroom.state_of(draft)
    return templates.TemplateResponse(
        request,
        "draft/_search.html",
        {"hits": hits, "q": q, "kind": kind, "my_turn": state.is_my_turn, "done": state.is_done},
    )


@app.get("/draft/{kind}/pool", response_class=HTMLResponse)
def pool(
    request: Request,
    kind: str,
    pool_q: str = "",
    pool_pos: str = "Alle",
    pool_sort: str = "fit",
    pool_limit: int = 60,
):
    kind = _kind(kind)
    ctx = _context(request, kind, _pool_params(pool_q, pool_pos, pool_sort, pool_limit))
    return templates.TemplateResponse(request, "draft/_pool.html", ctx)


@app.post("/draft/{kind}/ai", response_class=HTMLResponse)
def ai_advice(request: Request, kind: str):
    kind = _kind(kind)
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
