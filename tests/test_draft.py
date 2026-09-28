import numpy as np
import pytest

from fantasy.engine import rosterfit, simulate
from fantasy.engine.draft import DraftPick, DraftSettings, DraftState, slot_for_pick


def test_snake_order():
    assert [slot_for_pick(n, 4) for n in range(1, 13)] == [1, 2, 3, 4, 4, 3, 2, 1, 1, 2, 3, 4]


def test_my_turn_and_next_picks():
    settings = DraftSettings(teams=10, my_slot=3, rounds=3)
    state = DraftState(settings, [])
    assert state.my_pick_numbers() == [3, 18, 23]
    assert not state.is_my_turn
    assert state.picks_until_my_turn() == 2
    picks = [DraftPick(n, slot_for_pick(n, 10), f"p{n}", f"P{n}", n == 3) for n in range(1, 3)]
    state = DraftState(settings, picks)
    assert state.is_my_turn
    assert state.picks_between_my_next_two() == 14
    assert state.next_my_pick(after=3) == 18


def test_draft_done():
    settings = DraftSettings(teams=2, my_slot=1, rounds=1)
    state = DraftState(settings, [DraftPick(1, 1, "a", "A", True), DraftPick(2, 2, "b", "B", False)])
    assert state.is_done and state.on_the_clock is None


def test_settings_roundtrip_clamps_slot():
    settings = DraftSettings.from_dict({"teams": 8, "my_slot": 12, "unknown": 1})
    assert settings.my_slot == 8
    assert DraftSettings.from_dict(settings.to_dict()) == settings


def test_roster_slots_matching():
    slots = ["PG", "SG", "G", "SF", "PF", "F", "C", "C", "UTIL"]
    assert rosterfit.unfilled_slots([["PG", "SG"], ["C"]], slots)
    players = [["PG"], ["SG"], ["PG", "SG"], ["SF"], ["PF"], ["SF", "PF"], ["C"], ["PF", "C"]]
    assert rosterfit.unfilled_slots(players, slots) == []
    assert rosterfit.fills_open_slot(["C"], [["PG"], ["C"]], slots)
    assert not rosterfit.fills_open_slot(["PG"], players, slots)


def test_simulation_takes_low_adp_first():
    adp = np.array([1.0, 2.0, 3.0, 50.0, 100.0])
    available = np.arange(5)
    taken = simulate.simulate_taken(adp, available, n_picks=2, sims=500, rng=np.random.default_rng(1))
    assert taken.sum(axis=1).tolist() == [2] * 500
    share = taken.mean(axis=0)
    assert share[0] > 0.6 and share[4] < 0.01


def test_lookahead_penalises_players_who_come_back():
    fit = np.array([5.0, 4.9, 1.0])
    # Player 0 is always still available at my next pick, player 1 never is.
    taken = np.array([[False, True, False]] * 10)
    scores = simulate.lookahead_scores(fit, taken)
    assert scores[1] > scores[0]  # take the one who will not come back
    assert scores[0] == pytest.approx(5.0 + 1.0)  # taking 0 now leaves only player 2 next time


def test_effective_adp_fallbacks():
    eff = simulate.effective_adp([5.0, None, None], [6.0, 150.0, None], np.array([1.0, 1.0, 1.0]))
    assert eff[0] == 5.0
    assert eff[1] == 160.0
    assert eff[2] > 200
