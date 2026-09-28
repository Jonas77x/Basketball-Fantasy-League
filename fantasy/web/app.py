"""FastAPI app."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from fantasy.players.catalog import get_catalog
from fantasy.web import routes_draft, routes_yahoo
from fantasy.web.common import WEB_DIR

app = FastAPI(title="Fantasy-Assistent", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
app.include_router(routes_draft.router)
app.include_router(routes_yahoo.router)


@app.get("/")
def index():
    return RedirectResponse("/draft", status_code=303)


@app.get("/health")
def health():
    return JSONResponse({"ok": True, "players": len(get_catalog())})
