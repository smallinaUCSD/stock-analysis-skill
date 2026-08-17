"""Virtue-of-Complexity timing: learns a predictable signal, honest OOS reporting."""

import numpy as np

from stockskill.regime.voc import voc_timing


def _closes_from_ar(coef, n_months=200, sigma=0.02, seed=1):
    """Daily closes whose monthly returns follow an AR(1) with the given coef."""
    rng = np.random.default_rng(seed)
    r = [0.0]
    for _ in range(n_months):
        r.append(coef * r[-1] + rng.normal(0, sigma))
    px = [100.0]
    for mr in r[1:]:
        for _ in range(21):
            px.append(px[-1] * (1 + mr / 21))
    return px


def test_voc_learns_predictable_momentum():
    res = voc_timing(_closes_from_ar(0.6), n_features=400)
    assert res is not None
    assert res.oos_r2 > 0.02                       # captures the AR(1) structure
    assert res.timing_sharpe > res.buyhold_sharpe  # timing adds value
    assert res.signal in ("risk-on", "risk-off", "neutral")


def test_voc_deterministic_given_seed():
    px = _closes_from_ar(0.4)
    a = voc_timing(px, n_features=300, seed=3)
    b = voc_timing(px, n_features=300, seed=3)
    assert a.prediction == b.prediction and a.oos_r2 == b.oos_r2


def test_voc_too_short_is_none():
    assert voc_timing([100.0 * 1.001 ** i for i in range(200)], min_train=24) is None
