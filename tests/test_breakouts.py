import numpy as np

from stockskill.signals import breakouts as B


def _series(n=400, seed=1, drift=0.0008):
    rnd = np.random.default_rng(seed)
    c = 100 * np.cumprod(1 + rnd.normal(drift, 0.01, n))
    return c


def test_score_day_requires_close_above_prior_20_day_high():
    c = np.full(300, 100.0)
    c[:200] = np.linspace(80, 100, 200)
    c[-1] = 110.0                                     # breaks out today
    v = np.full(300, 1e6)
    v[-1] = 3e6                                       # on 3x volume
    f = B.features(c, c, v, np.linspace(100, 101, 300))
    s = B.score_day(f, 299)
    assert s and s["level"] == 100.0 and s["checks"]["volume"] and s["checks"]["near_52w_high"]
    assert B.score_day(f, 250) is None                # flat day: no breakout


def test_scan_and_backtest_shapes():
    uni = {f"T{i}": {"close": _series(seed=i), "high": None, "volume": None} for i in range(4)}
    bt = B.backtest(uni)
    assert set(bt) >= {"A", "B", "C", "base"} and bt["base"]["20"]["mean"] is not None
    assert all(r["grade"] in "ABC" for r in B.scan(uni))


def test_bench_on_carries_last_value_over_gaps():
    got = B.bench_on(["2026-01-02", "2026-01-03", "2026-01-05"], ["2026-01-02", "2026-01-05"], [10.0, 12.0])
    assert list(got) == [10.0, 10.0, 12.0]
