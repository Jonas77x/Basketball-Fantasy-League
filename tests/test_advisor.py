import numpy as np

from fantasy.engine import simulate
from fantasy.engine.advisor import DraftAdvisor, matchup_win_probability
from fantasy.engine.draft import DraftPick, DraftSettings, DraftState, slot_for_pick
from fantasy.engine.rosterfit import unfilled_slots
from fantasy.players.catalog import get_catalog


def run_draft(settings: DraftSettings, seed: int = 7):
    players = list(get_catalog())
    advisor = DraftAdvisor(players, settings)
    rng = np.random.default_rng(seed)
    picks: list[DraftPick] = []
    analyses = []
    while True:
        state = DraftState(settings, picks)
        if state.is_done:
            return players, advisor, state, analyses
        n = state.current_pick
        if state.is_my_turn:
            analysis = advisor.analyze(state, sims=300, seed=n)
            analyses.append(analysis)
            best = analysis.candidates[0].player
            picks.append(DraftPick(n, slot_for_pick(n, settings.teams), best.id, best.name, True))
        else:
            drafted = state.drafted_ids()
            available = np.array([i for i, p in enumerate(players) if p.id not in drafted])
            i = simulate.pick_by_adp(advisor.adp_eff, available, rng)
            picks.append(
                DraftPick(n, slot_for_pick(n, settings.teams), players[i].id, players[i].name, False)
            )


def test_full_simulated_draft_gives_complete_valid_team():
    settings = DraftSettings(teams=12, my_slot=6, rounds=13)
    players, advisor, state, analyses = run_draft(settings)
    mine = state.my_player_ids()
    assert len(mine) == 13 and len(set(mine)) == 13
    by_id = {p.id: p for p in players}
    assert unfilled_slots([by_id[i].positions for i in mine], settings.starting_slots) == []
    assert all(a.mode == "my_turn" and a.candidates for a in analyses)
    assert all(a.candidates[0].reasons for a in analyses)


def test_waiting_mode_forecasts_availability():
    settings = DraftSettings(teams=12, my_slot=12, rounds=13)
    players = list(get_catalog())
    advisor = DraftAdvisor(players, settings)
    analysis = advisor.analyze(DraftState(settings, []), sims=500, seed=1)
    assert analysis.mode == "waiting"
    assert analysis.picks_until == 11
    assert all(c.p_available is not None and c.p_available >= 0.35 for c in analysis.candidates)
    top_adp = min(players, key=lambda p: p.adp or 999)
    assert analysis.p_available[advisor.index[top_adp.id]] < 0.05


def test_punt_suggestion_for_bad_free_throw_start():
    players = list(get_catalog())
    by_name = {p.name: p for p in players}
    settings = DraftSettings(teams=12, my_slot=7, rounds=13)
    advisor = DraftAdvisor(players, settings)
    mine = {7: "Giannis Antetokounmpo", 18: "Alperen Sengün", 31: "Jalen Duren"}
    used = {by_name[n].id for n in mine.values()}
    others = [players[i] for i in np.argsort(advisor.adp_eff) if players[i].id not in used]
    picks = []
    for n in range(1, 42):
        p = by_name[mine[n]] if n in mine else others.pop(0)
        picks.append(DraftPick(n, slot_for_pick(n, 12), p.id, p.name, n in mine))
    analysis = advisor.analyze(DraftState(settings, picks), sims=300, seed=1)
    assert analysis.punt_options
    assert analysis.punt_options[0].punts == ("ft",)
    assert "FT%" in analysis.punt_options[0].text


def test_matchup_probability():
    assert matchup_win_probability([0.5] * 9) == 0.5
    assert matchup_win_probability([1.0] * 5 + [0.0] * 4) == 1.0
    assert matchup_win_probability([0.9] * 9) > 0.99
