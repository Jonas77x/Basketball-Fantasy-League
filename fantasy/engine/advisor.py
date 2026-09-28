"""Draft advisor: recommendations with German reasons, team balance and punt suggestions."""

import itertools
import math
from dataclasses import dataclass, field

import numpy as np

from fantasy.engine import simulate
from fantasy.engine.categories import CATEGORIES, label, labels
from fantasy.engine.draft import DraftSettings, DraftState
from fantasy.engine.rosterfit import fills_open_slot, unfilled_slots
from fantasy.engine.valuation import HEALTHY_GAMES, Valuation

NEED_WEIGHT = 0.25
PUNT_MIN_GAIN = 0.02  # at least +2 percentage points chance to win a week
PUNT_FROM_MY_PICKS = 2  # suggestions start after my second pick (round 3)
CENTER_CHECK_FROM = 6  # remind about the scarce C slots after this many of my picks


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def matchup_win_probability(probs: list[float]) -> float:
    """Chance to win the week: more than half of the categories (ties count half)."""
    dist = [1.0]
    for p in probs:
        nxt = [0.0] * (len(dist) + 1)
        for k, q in enumerate(dist):
            nxt[k] += q * (1.0 - p)
            nxt[k + 1] += q * p
        dist = nxt
    n = len(probs)
    win = sum(q for k, q in enumerate(dist) if 2 * k > n)
    tie = sum(q for k, q in enumerate(dist) if 2 * k == n)
    return win + 0.5 * tie


def fmt_pct(p: float) -> str:
    return f"{round(p * 100):d} %"


def good_labels(keys) -> list[str]:
    """Labels for strengths; 'strong at TO' means few turnovers."""
    return ["wenig TO" if k == "to" else label(k) for k in keys]


def bad_labels(keys) -> list[str]:
    return ["viele TO" if k == "to" else label(k) for k in keys]


@dataclass
class Candidate:
    player: object
    idx: int
    value: float
    fit: float
    score: float
    p_available: float | None = None
    strengths: list[str] = field(default_factory=list)
    need_hits: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class PuntOption:
    punts: tuple[str, ...]
    win_chance: float
    gain: float
    text: str

    @property
    def label(self) -> str:
        return " + ".join(labels(self.punts)) if self.punts else "Kein Punt"


@dataclass
class TeamProfile:
    totals: dict[str, float]  # current roster
    final_totals: dict[str, float]  # current roster + expected rest of the draft
    final_win_prob: dict[str, float]  # per category, for the completed roster
    expected_cats: float  # expected category wins per week
    win_chance: float  # chance to win a week against an average team
    unfilled: list[str]


@dataclass
class Analysis:
    mode: str  # "my_turn", "waiting", "done"
    candidates: list[Candidate]
    next_pick: int | None
    picks_until: int
    team: TeamProfile
    punt_options: list[PuntOption]
    headline: str
    values: np.ndarray
    fit: np.ndarray
    p_available: dict[int, float]


class DraftAdvisor:
    def __init__(self, players, settings: DraftSettings):
        self.players = list(players)
        self.settings = settings
        self.valuation = _valuation(self.players, settings.pool_size, tuple(settings.categories))
        self.cats = self.valuation.categories
        z = self.valuation.z
        if settings.risk:
            share = np.clip(self.valuation.games / HEALTHY_GAMES, 0.0, 1.0)[:, None]
            ranking = z.sum(axis=1)
            order = np.argsort(-ranking)
            repl = z[order[settings.pool_size : settings.pool_size + settings.teams]].mean(axis=0)
            z = share * z + (1.0 - share) * repl[None, :]
        self.z_eff = z
        values_all = z.sum(axis=1)
        self.adp_eff = simulate.effective_adp(
            [p.adp for p in self.players], [p.adp_blend for p in self.players], values_all
        )
        self.index = {p.id: i for i, p in enumerate(self.players)}
        self.team_scale = 1.2 * math.sqrt(settings.rounds)
        self._my_turn = False
        self._pressure: dict | None = None

    # ---------- building blocks ----------

    def weights(self, punts) -> np.ndarray:
        return np.array([0.0 if c in punts else 1.0 for c in self.cats])

    def values(self, punts=None) -> np.ndarray:
        punts = self.settings.punts if punts is None else punts
        return self.z_eff @ self.weights(punts)

    def team_totals(self, idx: list[int]) -> np.ndarray:
        if not idx:
            return np.zeros(len(self.cats))
        return self.z_eff[idx].sum(axis=0)

    def needs(self, my_idx: list[int]) -> np.ndarray:
        """Per category: positive = weakness to fix (same formula as the original HTML)."""
        active = self.weights(self.settings.punts) > 0
        need = np.zeros(len(self.cats))
        if len(my_idx) < 2 or active.sum() == 0:
            return need
        totals = self.team_totals(my_idx)
        mean = totals[active].mean()
        sd = totals[active].std() + 0.5
        need[active] = np.clip((mean - totals[active]) / sd, -1.5, 1.5)
        return need

    def fit(self, my_idx: list[int]) -> np.ndarray:
        w = self.weights(self.settings.punts) * (1.0 + NEED_WEIGHT * self.needs(my_idx))
        return self.z_eff @ w

    def win_probabilities(self, totals: np.ndarray) -> dict[str, float]:
        return {c: _phi(totals[j] / self.team_scale) for j, c in enumerate(self.cats)}

    def complete_roster(
        self, my_idx: list[int], available: np.ndarray, future_picks: list[int], punts
    ) -> list[int]:
        """Greedy rest of the draft: at each of my future picks take the best player
        (for this punt strategy) whose ADP says he is probably still there."""
        values = self.values(punts)
        roster = list(my_idx)
        free = available.copy()
        for pick in future_picks:
            candidates = free & (self.adp_eff >= pick)
            if pick == future_picks[0] and self._my_turn:
                candidates = free.copy()
            if not candidates.any():
                candidates = free
            if not candidates.any():
                break
            best = int(np.argmax(np.where(candidates, values, -np.inf)))
            roster.append(best)
            free[best] = False
        return roster

    def outlook(self, roster: list[int]) -> tuple[float, float, dict[str, float]]:
        """(chance to win a week, expected category wins, per-category win chance) vs. an average team."""
        probs = self.win_probabilities(self.team_totals(roster))
        return matchup_win_probability(list(probs.values())), sum(probs.values()), probs

    # ---------- main entry ----------

    def analyze(
        self, state: DraftState, sims: int = simulate.SIMULATIONS, seed: int | None = None
    ) -> Analysis:
        s = self.settings
        rng = np.random.default_rng(seed)
        drafted = state.drafted_ids()
        available = np.array([p.id not in drafted for p in self.players])
        avail_idx = np.flatnonzero(available)
        my_idx = [self.index[i] for i in state.my_player_ids() if i in self.index]
        my_positions = [self.players[i].positions for i in my_idx]
        self._my_turn = state.is_my_turn

        fit = self.fit(my_idx)
        values = self.values()
        future = state.future_my_picks()
        unfilled = unfilled_slots(my_positions, s.starting_slots)

        # Position pressure: only when it matters (few picks left, or still missing centers).
        self._pressure = self._position_pressure(my_idx, my_positions, unfilled, future)
        bonus = np.zeros(len(self.players))
        if self._pressure:
            for i in avail_idx:
                bonus[i] = self._position_bonus(self.players[i].positions, my_positions)

        p_available: dict[int, float] = {}
        candidates: list[Candidate] = []
        next_pick = state.next_my_pick()
        picks_until = state.picks_until_my_turn()

        if state.is_done:
            mode = "done"
        elif state.is_my_turn:
            mode = "my_turn"
            between = state.picks_between_my_next_two() or 0
            taken = simulate.simulate_taken(self.adp_eff, avail_idx, between, sims, rng)
            p_back = 1.0 - taken.mean(axis=0) if between else np.ones(len(avail_idx))
            scores = simulate.lookahead_scores(fit[avail_idx] + bonus[avail_idx], taken)
            order = np.argsort(-scores)[:8]
            following = state.next_my_pick(after=next_pick)
            for k in order:
                i = int(avail_idx[k])
                p_available[i] = float(p_back[k])
                candidates.append(
                    self._candidate(
                        i,
                        values,
                        fit,
                        scores[k],
                        float(p_back[k]),
                        my_idx,
                        my_positions,
                        unfilled,
                        following,
                        state,
                    )
                )
        else:
            mode = "waiting"
            taken = simulate.simulate_taken(self.adp_eff, avail_idx, picks_until, sims, rng)
            p_av = 1.0 - taken.mean(axis=0)
            for k, i in enumerate(avail_idx):
                p_available[int(i)] = float(p_av[k])
            likely = [k for k in range(len(avail_idx)) if p_av[k] >= 0.35]
            likely.sort(key=lambda k: -(fit[avail_idx[k]] + bonus[avail_idx[k]]))
            for k in likely[:8]:
                i = int(avail_idx[k])
                candidates.append(
                    self._candidate(
                        i,
                        values,
                        fit,
                        fit[i] + bonus[i],
                        float(p_av[k]),
                        my_idx,
                        my_positions,
                        unfilled,
                        next_pick,
                        state,
                    )
                )

        team = self._team_profile(my_idx, available, future, unfilled)
        punt_options = self._punt_options(my_idx, available, future, team.win_chance)
        headline = self._headline(mode, candidates, state, next_pick, picks_until)
        return Analysis(
            mode, candidates, next_pick, picks_until, team, punt_options, headline, values, fit, p_available
        )

    # ---------- details ----------

    def _position_pressure(self, my_idx, my_positions, unfilled, future) -> dict | None:
        if not unfilled or not future:
            return None
        if len(future) <= len(unfilled) + 1:
            return {"urgent": True, "slots": sorted(set(unfilled)), "picks_left": len(future)}
        if "C" in unfilled and len(my_idx) >= CENTER_CHECK_FROM:
            centers = sum(1 for pos in my_positions if "C" in pos)
            needed = self.settings.starting_slots.count("C")
            return {"urgent": False, "slots": ["C"], "centers": centers, "needed": needed}
        return None

    def _position_bonus(self, positions, my_positions) -> float:
        pressure = self._pressure
        if not pressure:
            return 0.0
        if pressure["urgent"]:
            return 1.5 if fills_open_slot(positions, my_positions, self.settings.starting_slots) else 0.0
        return 0.3 if "C" in positions else 0.0

    def _position_reason(self, positions, my_positions) -> str:
        pressure = self._pressure
        if not pressure or not self._position_bonus(positions, my_positions):
            return ""
        if pressure["urgent"]:
            return (
                f"Füllt eine offene Position ({', '.join(pressure['slots'])}) – dir bleiben nur noch "
                f"{pressure['picks_left']} Picks."
            )
        return f"Center: Du hast erst {pressure['centers']} für {pressure['needed']} C-Plätze."

    def _team_profile(self, my_idx, available, future, unfilled) -> TeamProfile:
        totals = self.team_totals(my_idx)
        final = self.complete_roster(my_idx, available, future, self.settings.punts) if my_idx else []
        if final:
            chance, cats, probs = self.outlook(final)
        else:
            chance, cats, probs = 0.5, len(self.cats) / 2, {c: 0.5 for c in self.cats}
        final_totals = self.team_totals(final)
        return TeamProfile(
            totals={c: float(totals[j]) for j, c in enumerate(self.cats)},
            final_totals={c: float(final_totals[j]) for j, c in enumerate(self.cats)},
            final_win_prob=probs,
            expected_cats=cats,
            win_chance=chance,
            unfilled=unfilled,
        )

    def _punt_options(self, my_idx, available, future, base_chance) -> list[PuntOption]:
        if len(my_idx) < PUNT_FROM_MY_PICKS or len(future) < 3:
            return []
        current = tuple(sorted(self.settings.punts))
        options: set[tuple[str, ...]] = {()}
        options.update((c,) for c in self.cats)
        options.update(tuple(sorted(pair)) for pair in itertools.combinations(self.cats, 2))
        options.discard(current)
        totals = self.team_totals(my_idx)
        results = []
        for punts in options:
            # Only suggest giving up categories where the team is already behind, never a strength.
            punt_totals = [totals[self.cats.index(c)] for c in punts]
            if punts and (max(punt_totals) >= 0.5 or min(punt_totals) > -0.5):
                continue
            roster = self.complete_roster(my_idx, available, future, punts)
            chance, _, _ = self.outlook(roster)
            gain = chance - base_chance
            if gain >= PUNT_MIN_GAIN:
                results.append(
                    PuntOption(punts, chance, gain, self._punt_text(punts, chance, base_chance, totals))
                )
        results.sort(key=lambda o: -o.gain)
        return results[:3]

    def _punt_text(self, punts, chance, base_chance, totals) -> str:
        if not punts:
            return (
                f"Ohne Punt steigt deine Chance, eine Woche gegen ein Durchschnittsteam zu gewinnen, "
                f"von {fmt_pct(base_chance)} auf {fmt_pct(chance)}."
            )
        names = " und ".join(labels(punts))
        weak = [label(c) for c in punts if totals[self.cats.index(c)] < -0.5]
        why = f" Bei {', '.join(weak)} liegst du ohnehin hinten." if weak else ""
        return (
            f"{names} bewusst opfern: Deine Chance, eine Woche gegen ein Durchschnittsteam zu gewinnen, "
            f"steigt von {fmt_pct(base_chance)} auf {fmt_pct(chance)}.{why}"
        )

    def _candidate(
        self, i, values, fit, score, p_av, my_idx, my_positions, unfilled, next_pick, state
    ) -> Candidate:
        p = self.players[i]
        active = [c for c in self.cats if c not in self.settings.punts]
        need = self.needs(my_idx)
        zrow = self.valuation.z[i]
        strengths = sorted(
            (c for c in active if zrow[self.cats.index(c)] >= 0.6), key=lambda c: -zrow[self.cats.index(c)]
        )[:3]
        need_hits = [c for c in strengths if need[self.cats.index(c)] > 0.3]
        weaknesses = sorted(
            (c for c in active if zrow[self.cats.index(c)] <= -0.8), key=lambda c: zrow[self.cats.index(c)]
        )[:2]
        cand = Candidate(
            p,
            i,
            float(values[i]),
            float(fit[i]),
            float(score),
            p_av,
            good_labels(strengths),
            good_labels(need_hits),
            bad_labels(weaknesses),
        )

        if strengths:
            text = f"Stark bei {', '.join(cand.strengths)}"
            if need_hits:
                text += f" – genau da ist dein Team noch schwach ({', '.join(labels(need_hits))})"
            cand.reasons.append(text + ".")
        if weaknesses:
            cand.reasons.append(f"Schwach bei {', '.join(cand.weaknesses)}.")
        position_reason = self._position_reason(p.positions, my_positions)
        if position_reason:
            cand.reasons.append(position_reason)
        if state.is_my_turn and next_pick:
            if p_av < 0.03:
                cand.reasons.append(
                    f"Kommt nicht zurück: bei deinem Pick {next_pick} ist er praktisch sicher weg."
                )
                cand.tags.append("Kommt nicht zurück")
            elif p_av < 0.25:
                cand.reasons.append(
                    f"Kommt sehr wahrscheinlich nicht zurück: nur {fmt_pct(p_av)} Chance bei deinem Pick {next_pick}."
                )
                cand.tags.append("Kommt nicht zurück")
            elif p_av > 0.7:
                cand.reasons.append(f"Ist mit {fmt_pct(p_av)} bei Pick {next_pick} noch da – kein Zeitdruck.")
        elif not state.is_my_turn and next_pick:
            cand.reasons.append(f"Chance, dass er bei deinem Pick {next_pick} noch da ist: {fmt_pct(p_av)}.")
        if p.adp:
            if p.adp > state.current_pick + 20:
                cand.reasons.append(f"Laut Yahoo-ADP ({p.adp:.0f}) wird er meist später gezogen.")
            elif p.adp < state.current_pick - 8:
                cand.reasons.append(f"Ist gefallen: Yahoo-ADP {p.adp:.0f}.")
                cand.tags.append("Schnäppchen")
        if p.games < 60:
            cand.reasons.append(f"Erwartet nur etwa {p.games:.0f} Spiele.")
            cand.tags.append("Ausfallrisiko")
        if p.is_rookie:
            cand.tags.append("Rookie")
        return cand

    def _headline(self, mode, candidates, state, next_pick, picks_until) -> str:
        if mode == "done":
            return "Draft abgeschlossen."
        if not candidates:
            return "Keine Spieler mehr in der Liste – trag weitere Picks von Hand ein."
        best = candidates[0]
        if mode == "my_turn":
            return f"Empfehlung: {best.player.name}"
        return f"Für deinen Pick {next_pick} sieht es gerade nach {best.player.name} aus"


_VALUATIONS: dict[tuple, Valuation] = {}


def _valuation(players: list, pool_size: int, categories: tuple) -> Valuation:
    """Valuations only depend on the player list, pool size and categories – cache them."""
    key = (tuple(p.id for p in players), pool_size, categories)
    if key not in _VALUATIONS:
        if len(_VALUATIONS) > 8:
            _VALUATIONS.clear()
        _VALUATIONS[key] = Valuation(players, pool_size, categories)
    return _VALUATIONS[key]


def category_label(key: str) -> str:
    return CATEGORIES[key].label
