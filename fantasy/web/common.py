"""Shared web helpers: templates with German number formats, pool parameters."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates

from fantasy import draftroom
from fantasy.web.draft_view import SORTS, PoolParams

WEB_DIR = Path(__file__).parent
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


def check_kind(kind: str) -> str:
    if kind not in draftroom.KINDS:
        raise HTTPException(404)
    return kind


def pool_params(q: str = "", pos: str = "Alle", sort: str = "fit", limit: int = 60) -> PoolParams:
    return PoolParams(q=q, pos=pos, sort=sort if sort in SORTS else "fit", limit=max(20, min(limit, 400)))


def pool_form(
    pool_q: str = Form(""),
    pool_pos: str = Form("Alle"),
    pool_sort: str = Form("fit"),
    pool_limit: int = Form(60),
) -> PoolParams:
    """Pool filters sent along with every draft action (hx-include="#pool-filters")."""
    return pool_params(pool_q, pool_pos, pool_sort, pool_limit)


def pool_query(
    pool_q: str = "", pool_pos: str = "Alle", pool_sort: str = "fit", pool_limit: int = 60
) -> PoolParams:
    return pool_params(pool_q, pool_pos, pool_sort, pool_limit)


PoolFormDep = Annotated[PoolParams, Depends(pool_form)]
PoolQueryDep = Annotated[PoolParams, Depends(pool_query)]
