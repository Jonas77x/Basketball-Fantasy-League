"""Monte-Carlo model of the other managers' picks, based on Yahoo ADP.

Each simulated opponent pick takes the available player with the smallest "ADP + noise".
The noise grows with ADP: early picks are predictable, later rounds are chaotic.
"""

import numpy as np

SIMULATIONS = 2000
NOISE_SCALE = 0.2
NOISE_MIN = 2.0
NO_ADP_BASE = 175.0


def effective_adp(adp: list[float | None], blend: list[float | None], values: np.ndarray) -> np.ndarray:
    """Yahoo ADP where known; otherwise blended ADP (other platforms) a bit later;
    otherwise far back, ordered by our own value."""
    result = np.empty(len(adp))
    missing = []
    for i, (yahoo, other) in enumerate(zip(adp, blend, strict=True)):
        if yahoo is not None:
            result[i] = yahoo
        elif other is not None:
            result[i] = max(other, 120.0) + 10.0
        else:
            missing.append(i)
    if missing:
        order = sorted(missing, key=lambda i: -values[i])
        for rank, i in enumerate(order):
            result[i] = NO_ADP_BASE + 40.0 + rank
    return result


def noise_sd(adp: np.ndarray) -> np.ndarray:
    return np.maximum(NOISE_MIN, NOISE_SCALE * adp)


def simulate_taken(
    adp_eff: np.ndarray,
    available: np.ndarray,
    n_picks: int,
    sims: int = SIMULATIONS,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Boolean matrix (sims x len(available)): True where the player is taken by others within n_picks."""
    n = len(available)
    taken = np.zeros((sims, n), dtype=bool)
    n_picks = min(n_picks, n)
    if n_picks <= 0 or n == 0:
        return taken
    rng = rng or np.random.default_rng()
    base = adp_eff[available]
    keys = base + rng.standard_normal((sims, n)) * noise_sd(base)
    idx = np.argpartition(keys, n_picks - 1, axis=1)[:, :n_picks]
    np.put_along_axis(taken, idx, True, axis=1)
    return taken


def lookahead_scores(fit: np.ndarray, taken: np.ndarray) -> np.ndarray:
    """Two-pick lookahead for each candidate X (all arrays aligned to the available players):
    fit(X) + expected best fit still available at my next pick if I take X now.
    Players who would come back anyway are therefore less urgent."""
    if taken.shape[1] == 0:
        return fit.copy()
    masked = np.where(taken, -np.inf, fit[None, :])
    if masked.shape[1] >= 2:
        top2 = np.argpartition(-masked, 1, axis=1)[:, :2]
        vals = np.take_along_axis(masked, top2, axis=1)
        order = np.argsort(-vals, axis=1)
        best_idx = np.take_along_axis(top2, order[:, :1], axis=1)[:, 0]
        best = np.take_along_axis(vals, order[:, :1], axis=1)[:, 0]
        second = np.take_along_axis(vals, order[:, 1:2], axis=1)[:, 0]
    else:
        best_idx = np.zeros(masked.shape[0], dtype=int)
        best = masked[:, 0]
        second = np.full(masked.shape[0], -np.inf)
    floor = float(np.min(fit)) if len(fit) else 0.0
    best = np.where(np.isfinite(best), best, floor)
    second = np.where(np.isfinite(second), second, floor)
    expected_next = np.full(len(fit), best.mean())
    penalty = np.bincount(best_idx, weights=best - second, minlength=len(fit)) / masked.shape[0]
    return fit + expected_next - penalty


def pick_by_adp(adp_eff: np.ndarray, available: np.ndarray, rng: np.random.Generator) -> int:
    """One simulated opponent pick (practice mode). Returns an index into the full player array."""
    base = adp_eff[available]
    keys = base + rng.standard_normal(len(available)) * noise_sd(base)
    return int(available[int(np.argmin(keys))])
