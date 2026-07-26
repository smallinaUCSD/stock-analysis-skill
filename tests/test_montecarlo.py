import math

import pytest

from stockskill.montecarlo import montecarlo, estimate_params, daily_returns
from stockskill.montecarlo.simulate import summarize


def test_daily_returns():
    assert daily_returns([100, 110, 121]) == pytest.approx([0.10, 0.10])


def test_estimate_params():
    drift, vol = estimate_params([0.01] * 20)      # constant -> zero vol
    assert drift == pytest.approx(0.01 * 252)
    assert vol == pytest.approx(0.0)
    assert estimate_params([0.01]) == (0.0, 0.0)   # too short


def test_gbm_zero_vol_is_deterministic():
    # constant +0.1%/day -> vol 0 -> every path identical
    closes = [100.0 * (1.001 ** i) for i in range(300)]
    r = montecarlo(closes, days=63, n_paths=1000, method="gbm", seed=1)
    assert r.vol_annual == pytest.approx(0.0, abs=1e-9)
    assert r.expected_return == pytest.approx(math.exp(0.063) - 1, abs=1e-6)
    assert r.prob_up == 1.0
    assert r.pctiles["p5"] == pytest.approx(r.pctiles["p95"])   # no spread


def test_reproducible():
    closes = [100.0 + i + (i % 5) for i in range(300)]
    a = montecarlo(closes, days=40, n_paths=5000, seed=7)
    b = montecarlo(closes, days=40, n_paths=5000, seed=7)
    assert a.expected_return == b.expected_return
    assert a.prob_gain == b.prob_gain


def test_drift_adjust_raises_expectation():
    closes = [100.0 * (1.0005 ** i) for i in range(300)]
    base = montecarlo(closes, days=63, n_paths=8000, seed=3, drift_adj=0.0)
    up = montecarlo(closes, days=63, n_paths=8000, seed=3, drift_adj=0.30)
    assert up.expected_return > base.expected_return


def test_summarize_probabilities():
    r = summarize([0.2, -0.2, 0.05, -0.05], spot=100, days=63, n_paths=4,
                  method="gbm", drift=0.1, vol=0.3, gain=0.10, loss=0.10)
    assert r.prob_gain == pytest.approx(0.25)   # only +0.2
    assert r.prob_loss == pytest.approx(0.25)   # only -0.2
    assert r.prob_up == pytest.approx(0.5)
    assert r.pctiles["p50"] == pytest.approx(0.0)
    assert r.var_95 == r.pctiles["p5"]


def test_bootstrap_runs():
    closes = [100.0 * (1.0 + 0.01 * ((i % 7) - 3)) ** 1 for i in range(300)]
    r = montecarlo(closes, days=30, n_paths=3000, method="bootstrap", seed=2)
    assert 0.0 <= r.prob_up <= 1.0 and r.method == "bootstrap"
