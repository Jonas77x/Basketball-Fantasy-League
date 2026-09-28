import numpy as np
import pytest
from conftest import make_player

from fantasy.engine.valuation import Valuation


def pool():
    players = [make_player(str(i), pts=10 + i, reb=3 + (i % 5), tov=1 + i * 0.1) for i in range(30)]
    players.append(make_player("big", pts=15, reb=12, blk=2.5, fga=10, fg_pct=0.60, fta=6, ft_pct=0.55))
    return players


def test_zscores_are_centered_on_the_pool():
    val = Valuation(pool(), pool_size=20, weights={})
    means = val.z[val.pool_mask].mean(axis=0)
    assert np.allclose(means, 0.0, atol=1e-9)


def test_turnovers_count_negative():
    val = Valuation(pool(), pool_size=20, weights={})
    to = val.categories.index("to")
    assert val.z[val.index["0"], to] > val.z[val.index["29"], to]  # "0" has fewest turnovers


def test_percentages_weighted_by_volume():
    val = Valuation(pool(), pool_size=20, weights={})
    fg, ft = val.categories.index("fg"), val.categories.index("ft")
    big = val.index["big"]
    assert val.z[big, fg] > 1.0
    assert val.z[big, ft] < -1.0


def test_punted_categories_are_ignored():
    val = Valuation(pool(), pool_size=20, weights={})
    big = val.index["big"]
    all_cats = val.totals(val.categories)[big]
    without_ft = val.totals([c for c in val.categories if c != "ft"])[big]
    assert without_ft > all_cats


def test_availability_blends_in_replacement_level():
    players = pool()
    players.append(make_player("fragile", pts=40, reb=12, ast=9, games=39))
    val = Valuation(players, pool_size=20, weights={})
    raw = val.totals(val.categories)
    blended = val.with_availability(raw, replacement=0.0)
    i = val.index["fragile"]
    assert blended[i] == pytest.approx(raw[i] * 0.5)


def test_h2h_weights_shrink_volatile_categories():
    plain = Valuation(pool(), pool_size=20, weights={})
    weighted = Valuation(pool(), pool_size=20)
    ft = plain.categories.index("ft")
    big = plain.index["big"]
    assert abs(weighted.z[big, ft]) < abs(plain.z[big, ft])
