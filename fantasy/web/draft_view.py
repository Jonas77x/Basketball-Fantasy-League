"""Turns draft state + analysis into plain dicts for the templates."""

from dataclasses import dataclass

from fantasy.draftroom import advisor_for, options_of, state_of
from fantasy.engine.categories import CATEGORIES
from fantasy.engine.draft import round_of, slot_for_pick
from fantasy.players.names import normalize_name

POSITIONS = ["Alle", "PG", "SG", "SF", "PF", "C"]
SORTS = {"fit": "passt zu deinem Team", "value": "Gesamtwert", "adp": "Yahoo-ADP"}


@dataclass
class PoolParams:
    q: str = ""
    pos: str = "Alle"
    sort: str = "fit"
    limit: int = 60


def stat_cell(player, key: str) -> str:
    if key == "fg":
        return f"{player.fg_pct * 100:.1f}"
    if key == "ft":
        return f"{player.ft_pct * 100:.1f}"
    stat = {"to": "tov"}.get(key, key)
    return f"{player.stats[stat]:.1f}"


def short_name(name: str) -> str:
    """'Michael Porter Jr.' -> 'Porter' (for button labels)."""
    parts = [x for x in name.split() if x.rstrip(".").lower() not in {"jr", "sr", "ii", "iii", "iv"}]
    return parts[-1] if parts else name


def _tone(z: float) -> str:
    alpha = min(55, abs(z) * 20)
    color = "var(--good)" if z >= 0 else "var(--bad)"
    return f"background:color-mix(in srgb,{color} {alpha:.0f}%,transparent)"


def build_view(draft, kind: str, pool: PoolParams) -> dict:
    state = state_of(draft)
    settings = state.settings
    advisor = advisor_for(draft)
    analysis = advisor.analyze(state, seed=state.current_pick)
    players = advisor.players
    val = advisor.valuation
    punts = set(settings.punts)

    # ----- clock -----
    current = min(state.current_pick, settings.total_picks)
    rnd = round_of(current, settings.teams)
    strip = []
    if not state.is_done:
        start = (rnd - 1) * settings.teams + 1
        for n in range(start, start + settings.teams):
            strip.append(
                {
                    "n": n,
                    "past": n < state.current_pick,
                    "now": n == state.current_pick,
                    "me": slot_for_pick(n, settings.teams) == settings.my_slot,
                }
            )
    clock = {
        "pick": current,
        "round": rnd,
        "in_round": current - (rnd - 1) * settings.teams,
        "done": state.is_done,
        "my_turn": state.is_my_turn,
        "on_clock": settings.team_name(state.on_the_clock) if state.on_the_clock else "",
        "picks_until": analysis.picks_until,
        "next_pick": analysis.next_pick,
        "strip": strip,
        "has_picks": bool(state.picks),
    }

    # ----- recommendations -----
    def card(c) -> dict:
        p = c.player
        return {
            "id": p.id,
            "name": p.name,
            "last_name": short_name(p.name),
            "team": p.team,
            "pos": p.pos_label,
            "value": c.value,
            "p": c.p_available,
            "reasons": c.reasons,
            "tags": c.tags,
            "notes": p.notes,
            "games": p.games,
            "adp": p.adp,
            "rookie": p.is_rookie,
        }

    recos = [card(c) for c in analysis.candidates[:3]]

    # ----- team -----
    by_id = {p.id: p for p in players}
    roster = []
    for pick in state.my_picks():
        p = by_id.get(pick.player_id) if pick.player_id else None
        roster.append(
            {
                "name": pick.name,
                "info": f"{p.team}, {p.pos_label}" if p else "eigener Eintrag",
                "overall": pick.overall,
            }
        )
    final = analysis.team.final_totals
    scale = max(3.0, *(abs(v) for v in final.values())) if final else 3.0
    bars = []
    for key in settings.categories:
        v = final.get(key, 0.0)
        width = abs(v) / scale * 50
        style = (
            f"left:50%;width:{width:.1f}%;background:var(--good)"
            if v >= 0
            else f"right:50%;width:{width:.1f}%;background:var(--bad)"
        )
        bars.append(
            {
                "key": key,
                "label": CATEGORIES[key].label,
                "value": v,
                "now": analysis.team.totals.get(key, 0.0),
                "style": style,
                "off": key in punts,
                "win": analysis.team.final_win_prob.get(key, 0.5),
            }
        )
    team = {
        "roster": roster,
        "bars": bars,
        "win_chance": analysis.team.win_chance,
        "expected_cats": analysis.team.expected_cats,
        "unfilled": sorted(set(analysis.team.unfilled)),
        "size": len(roster),
        "has_players": bool(state.my_player_ids()),
    }
    punt_options = [
        {"label": o.label, "text": o.text, "punts": ",".join(o.punts), "gain": o.gain}
        for o in analysis.punt_options
    ]

    # ----- log -----
    log = [
        {
            "overall": p.overall,
            "round": round_of(p.overall, settings.teams),
            "name": p.name,
            "team": settings.team_name(p.slot),
            "mine": p.mine,
        }
        for p in reversed(state.picks)
    ]

    # ----- pool -----
    drafted = state.drafted_ids()
    idx = [i for i, p in enumerate(players) if p.id not in drafted]
    if pool.pos in POSITIONS[1:]:
        idx = [i for i in idx if pool.pos in players[i].positions]
    if pool.q.strip():
        tokens = normalize_name(pool.q).split()
        idx = [i for i in idx if all(t in players[i].search_key for t in tokens)]
    if pool.sort == "value":
        idx.sort(key=lambda i: -analysis.values[i])
    elif pool.sort == "adp":
        idx.sort(key=lambda i: advisor.adp_eff[i])
    else:
        idx.sort(key=lambda i: -analysis.fit[i])
    total_rows = len(idx)
    rows = []
    for rank, i in enumerate(idx[: pool.limit], 1):
        p = players[i]
        cells = []
        for j, key in enumerate(val.categories):
            z = float(val.z[i, j])
            cells.append(
                {
                    "label": CATEGORIES[key].label,
                    "text": stat_cell(p, key),
                    "style": _tone(z),
                    "off": key in punts,
                }
            )
        score = analysis.values[i] if pool.sort == "value" else analysis.fit[i]
        rows.append(
            {
                "rank": rank,
                "id": p.id,
                "name": p.name,
                "team": p.team,
                "pos": p.pos_label,
                "age": p.age,
                "games": p.games,
                "adp": p.adp,
                "score": float(score),
                "cells": cells,
                "notes": p.notes,
                "rookie": p.is_rookie,
                "p": analysis.p_available.get(i),
            }
        )

    return {
        "kind": kind,
        "settings": settings,
        "options": options_of(draft),
        "clock": clock,
        "mode": analysis.mode,
        "headline": analysis.headline,
        "recos": recos,
        "team": team,
        "punt_options": punt_options,
        "log": log,
        "pool": {"rows": rows, "total": total_rows, "params": pool, "more": total_rows > pool.limit},
        "categories": [
            {"key": k, "label": CATEGORIES[k].label, "punted": k in punts} for k in settings.categories
        ],
        "positions": POSITIONS,
        "sorts": SORTS,
    }


def search(draft, query: str, limit: int = 8) -> list[dict]:
    """Quick entry: available players matching the query, most likely picks first."""
    tokens = normalize_name(query).split()
    if not tokens:
        return []
    state = state_of(draft)
    advisor = advisor_for(draft)
    drafted = state.drafted_ids()
    hits = []
    for i, p in enumerate(advisor.players):
        if p.id in drafted:
            continue
        key = p.search_key
        if all(t in key for t in tokens):
            starts = any(part.startswith(tokens[0]) for part in key.split())
            hits.append((0 if starts else 1, float(advisor.adp_eff[i]), p))
    hits.sort(key=lambda h: (h[0], h[1]))
    return [
        {"id": p.id, "name": p.name, "team": p.team, "pos": p.pos_label, "adp": p.adp}
        for _, _, p in hits[:limit]
    ]
