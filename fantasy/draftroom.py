"""Draft room service: persistence of the live and the practice draft, pick entry, practice opponents."""

import hashlib
import json
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from fantasy.db import Draft, DraftPickRow
from fantasy.engine import simulate
from fantasy.engine.advisor import DraftAdvisor
from fantasy.engine.draft import DraftPick, DraftSettings, DraftState, slot_for_pick
from fantasy.players.catalog import get_catalog
from fantasy.yahoo.league import overlay

KINDS = ("live", "practice")


def get_draft(session: Session, kind: str = "live") -> Draft:
    if kind not in KINDS:
        raise ValueError(kind)
    draft = session.scalars(select(Draft).where(Draft.kind == kind).order_by(Draft.id.desc())).first()
    if draft is None:
        settings = DraftSettings()
        if kind == "practice":
            live = session.scalars(select(Draft).where(Draft.kind == "live")).first()
            if live is not None:
                settings = settings_of(live)
        draft = Draft(
            kind=kind,
            settings_json=json.dumps(settings.to_dict()),
            options_json=json.dumps({"auto_opponents": kind == "practice"}),
        )
        session.add(draft)
        session.flush()
    return draft


def settings_of(draft: Draft) -> DraftSettings:
    return DraftSettings.from_dict(json.loads(draft.settings_json or "{}"))


def options_of(draft: Draft) -> dict:
    return json.loads(draft.options_json or "{}")


def save_settings(draft: Draft, settings: DraftSettings) -> None:
    draft.settings_json = json.dumps(settings.to_dict())


def state_of(draft: Draft) -> DraftState:
    picks = [DraftPick(r.overall, r.slot, r.player_id, r.name, r.mine) for r in draft.picks]
    return DraftState(settings_of(draft), picks)


def players_for_draft() -> list:
    """Our catalog, enriched with Yahoo ADP/positions/status once the league is synced."""
    return overlay(list(get_catalog()))


def advisor_for(draft: Draft) -> DraftAdvisor:
    return DraftAdvisor(players_for_draft(), settings_of(draft))


def version_of(draft: Draft) -> str:
    """Changes whenever picks or settings change (used by the browser to refresh only when needed)."""
    text = (
        draft.settings_json
        + "|"
        + ";".join(f"{r.overall}:{r.player_id}:{r.name}:{r.mine}" for r in draft.picks)
    )
    return hashlib.sha1(text.encode()).hexdigest()[:16]


class PickError(ValueError):
    pass


def add_pick(
    session: Session,
    draft: Draft,
    player_id: str | None = None,
    name: str | None = None,
    source: str = "manual",
) -> DraftPickRow:
    """Record the pick that is currently on the clock. Whether it is mine follows from the snake order."""
    state = state_of(draft)
    if state.is_done:
        raise PickError("Der Draft ist schon abgeschlossen.")
    catalog = {p.id: p for p in get_catalog()}
    if player_id:
        if player_id not in catalog:
            raise PickError("Unbekannter Spieler.")
        if player_id in state.drafted_ids():
            raise PickError(f"{catalog[player_id].name} ist schon gedraftet.")
        name = catalog[player_id].name
    elif not (name or "").strip():
        raise PickError("Kein Spieler angegeben.")
    overall = state.current_pick
    slot = slot_for_pick(overall, state.settings.teams)
    row = DraftPickRow(
        overall=overall,
        slot=slot,
        player_id=player_id or None,
        name=name.strip(),
        mine=slot == state.settings.my_slot,
        source=source,
    )
    draft.picks.append(row)
    session.flush()
    return row


def undo_last(session: Session, draft: Draft) -> DraftPickRow | None:
    if not draft.picks:
        return None
    row = draft.picks[-1]
    draft.picks.remove(row)
    session.flush()
    return row


def undo_to_my_last_pick(session: Session, draft: Draft) -> None:
    """Practice mode: take back my last pick and every simulated pick after it."""
    while draft.picks:
        row = draft.picks[-1]
        undo_last(session, draft)
        if row.mine:
            break


def reset(session: Session, draft: Draft) -> None:
    draft.picks.clear()
    session.flush()


def simulate_opponents(session: Session, draft: Draft, seed: int | None = None) -> int:
    """Practice mode: let the other teams pick (Yahoo ADP + randomness) until it is my turn."""
    advisor = advisor_for(draft)
    players = advisor.players
    rng = np.random.default_rng(seed)
    count = 0
    while True:
        state = state_of(draft)
        if state.is_done or state.is_my_turn:
            return count
        drafted = state.drafted_ids()
        available = np.array([i for i, p in enumerate(players) if p.id not in drafted])
        if len(available) == 0:
            return count
        i = simulate.pick_by_adp(advisor.adp_eff, available, rng)
        add_pick(session, draft, player_id=players[i].id, source="simulated")
        count += 1


@dataclass
class ExternalPick:
    overall: int
    slot: int
    player_id: str | None
    name: str
    mine: bool


def apply_external_picks(
    session: Session, draft: Draft, picks: list[ExternalPick], source: str = "yahoo"
) -> bool:
    """Make Yahoo the source of truth: its picks replace ours; manual picks that Yahoo has not
    reported yet (API delay) are kept behind them, renumbered. Returns True if anything changed."""
    settings = settings_of(draft)
    external: list[ExternalPick] = []
    for pick in sorted(picks, key=lambda p: p.overall):
        if pick.overall != len(external) + 1:
            break  # only a gap-free sequence of picks is trustworthy
        external.append(pick)
    taken_ids = {p.player_id for p in external if p.player_id}
    taken_names = {p.name for p in external}

    desired = [(p.overall, p.slot, p.player_id, p.name, p.mine, source) for p in external]
    for row in draft.picks:
        if row.source == source or row.overall <= len(external):
            continue
        if (row.player_id and row.player_id in taken_ids) or (not row.player_id and row.name in taken_names):
            continue
        overall = len(desired) + 1
        slot = slot_for_pick(overall, settings.teams)
        desired.append((overall, slot, row.player_id, row.name, slot == settings.my_slot, row.source))

    current = [(r.overall, r.slot, r.player_id, r.name, r.mine, r.source) for r in draft.picks]
    if current == desired:
        return False
    draft.picks.clear()
    session.flush()
    for overall, slot, player_id, name, mine, src in desired:
        draft.picks.append(
            DraftPickRow(overall=overall, slot=slot, player_id=player_id, name=name, mine=mine, source=src)
        )
    session.flush()
    return True
