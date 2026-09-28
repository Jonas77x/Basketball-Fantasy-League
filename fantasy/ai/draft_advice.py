"""AI draft advice (optional): a short second opinion in German, on demand only."""

from fantasy.ai.client import AiResult, ask
from fantasy.engine.advisor import Analysis
from fantasy.engine.categories import label
from fantasy.engine.draft import DraftState

SYSTEM = (
    "Du bist ein erfahrener Fantasy-Basketball-Experte und berätst Jonas während seines Yahoo-Drafts. "
    "Antworte auf Deutsch, locker und direkt, in höchstens 6 Sätzen, ohne Aufzählungszeichen und ohne "
    "Überschriften. Nenne eine klare Empfehlung und eine Alternative. Achte auf Verletzungsrisiko, neue "
    "Rollen nach Teamwechseln, Rookies (unsichere Schätzungen) und die Balance der Kategorien."
)


def _line(player) -> str:
    s = player.stats
    notes = f"; Hinweis: {'; '.join(player.notes)}" if player.notes else ""
    adp = f", Yahoo-ADP {player.adp:.0f}" if player.adp else ""
    return (
        f"{player.name} ({player.team}, {player.pos_label}, {player.age} J.{adp}): Prognose pro Spiel "
        f"{s['pts']:.1f} PTS, {s['reb']:.1f} REB, {s['ast']:.1f} AST, {s['stl']:.1f} STL, {s['blk']:.1f} BLK, "
        f"{s['tpm']:.1f} 3PM, FG {player.fg_pct * 100:.1f}%, FT {player.ft_pct * 100:.1f}%, {s['tov']:.1f} TO, "
        f"ca. {player.games:.0f} Spiele{notes}"
    )


def build_prompt(state: DraftState, analysis: Analysis, catalog: dict) -> str:
    s = state.settings
    cats = ", ".join(label(c) for c in s.categories)
    punts = ", ".join(label(c) for c in s.punts) or "keine"
    mine = [catalog[i] for i in state.my_player_ids() if i in catalog]
    totals = ", ".join(f"{label(k)} {v:+.1f}" for k, v in analysis.team.totals.items())
    if state.is_my_turn:
        following = state.next_my_pick(after=state.current_pick)
        situation = (
            f"Ich bin jetzt dran (Gesamtpick {state.current_pick}). "
            f"Mein nächster Pick danach: {following or 'keiner mehr'}."
        )
    else:
        situation = (
            f"Gerade ist Pick {state.current_pick}, mein nächster Pick ist Nummer {analysis.next_pick}."
        )
    options = "\n".join(
        f"- {_line(c.player)}; Modellwert {c.value:+.1f}"
        + (
            f"; Chance, dass er bei meinem nächsten Pick noch da ist: {round(c.p_available * 100)} %"
            if c.p_available is not None
            else ""
        )
        for c in analysis.candidates[:8]
    )
    return (
        f"Liga: Yahoo, Head-to-Head nach Kategorien ({cats}), {s.teams} Teams, Snake-Draft, {s.rounds} Runden, "
        f"ich picke an Position {s.my_slot}. Bewusst geopferte Kategorien (Punt): {punts}.\n"
        f"{situation}\n"
        f"Mein Team bisher: {'; '.join(_line(p) for p in mine) if mine else 'noch leer'}.\n"
        f"Kategorien-Summe meines Teams (Z-Werte, positiv = stark): {totals}.\n"
        f"Beste Optionen laut meinem Modell:\n{options}\n"
        f"Die Prognosen basieren auf den letzten drei Saisons, Stand Ende September 2026. "
        f"Wen soll ich {'jetzt' if state.is_my_turn else 'bei meinem nächsten Pick'} nehmen und warum?"
    )


def draft_advice(state: DraftState, analysis: Analysis, catalog: dict) -> AiResult:
    return ask("draft", SYSTEM, build_prompt(state, analysis, catalog), max_tokens=600)
