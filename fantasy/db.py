"""SQLite database (SQLAlchemy 2.x). Timestamps are stored in UTC."""

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from fantasy.config import get_settings
from fantasy.timeutil import utcnow


class Base(DeclarativeBase):
    pass


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # "live" or "practice"
    settings_json: Mapped[str] = mapped_column(Text, default="{}")
    options_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    picks: Mapped[list["DraftPickRow"]] = relationship(
        back_populates="draft", cascade="all, delete-orphan", order_by="DraftPickRow.overall"
    )


class DraftPickRow(Base):
    __tablename__ = "draft_picks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id"))
    overall: Mapped[int] = mapped_column(Integer)
    slot: Mapped[int] = mapped_column(Integer)
    player_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    mine: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual, yahoo, simulated
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    draft: Mapped[Draft] = relationship(back_populates="picks")


class AiText(Base):
    """Cached AI answers plus token usage, used for the daily budget."""

    __tablename__ = "ai_texts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    purpose: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(60))
    text: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OAuthToken(Base):
    """Yahoo OAuth tokens. Lives only in the local database (var/, never committed)."""

    __tablename__ = "oauth_tokens"

    provider: Mapped[str] = mapped_column(String(20), primary_key=True)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user_guid: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KeyValue(Base):
    """Small JSON documents: league info, OAuth state, sync status."""

    __tablename__ = "key_values"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class YahooPlayer(Base):
    """A Yahoo player in the active league, mapped to our catalog (if possible)."""

    __tablename__ = "yahoo_players"

    player_key: Mapped[str] = mapped_column(String(40), primary_key=True)
    catalog_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    team: Mapped[str] = mapped_column(String(10), default="")
    positions: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(20), default="")
    injury_note: Mapped[str] = mapped_column(String(200), default="")
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Yahoo overall rank (OR)
    average_pick: Mapped[float | None] = mapped_column(Float, nullable=True)  # Yahoo ADP
    percent_drafted: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SyncLog(Base):
    """One line per Yahoo sync step, e.g. every live-draft poll (to verify live updates)."""

    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    picks_made: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


_engine = None
_factory = None
_engine_lock = threading.Lock()


def _session_factory():
    """Create engine and session factory once; safe when several threads start at the same time."""
    global _engine, _factory
    factory = _factory
    if factory is not None:
        return factory
    with _engine_lock:
        if _factory is None:
            path = get_settings().db_path
            path.parent.mkdir(parents=True, exist_ok=True)
            engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

            @event.listens_for(engine, "connect")
            def _pragmas(dbapi_conn, _record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

            Base.metadata.create_all(engine)
            _engine = engine
            _factory = sessionmaker(engine, expire_on_commit=False)
        return _factory


def get_engine():
    _session_factory()
    return _engine


def reset_engine() -> None:
    """Forget the engine (tests use a fresh database per test)."""
    global _engine, _factory
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _factory = None


@contextmanager
def session_scope() -> Iterator[Session]:
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_json(session: Session, key: str, default=None):
    row = session.get(KeyValue, key)
    return json.loads(row.value_json) if row else default


def set_json(session: Session, key: str, value) -> None:
    row = session.get(KeyValue, key)
    if row is None:
        row = KeyValue(key=key)
        session.add(row)
    row.value_json = json.dumps(value, ensure_ascii=False)
    row.updated_at = utcnow()


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; they are stored as UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
