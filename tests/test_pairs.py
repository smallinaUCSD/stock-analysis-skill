import math
import random

import pytest

from stockskill.signals import pairs as P


def _walk(n, seed, drift=0.0003, vol=0.01, start=100.0):
    rnd = random.Random(seed)
    out = [start]
    for _ in range(n - 1):
        out.append(out[-1] * (1 + rnd.gauss(drift, vol)))
    return out


def _twin(base, seed, noise=0.004):
    rnd = random.Random(seed)
    return [x * (1 + rnd.gauss(0, noise)) for x in base]


def test_select_pairs_picks_the_closest_same_group_pair():
    base = _walk(300, 1)
    w = {"A": base, "B": _twin(base, 2), "C": _walk(300, 3), "D": _twin(base, 4)}
    groups = {"A": "semi", "B": "semi", "C": "semi", "D": "bank"}
    got = P.select_pairs(w, groups, top=5, min_corr=0.3)
    assert got[0][:2] == ("A", "B")
    assert all(g[:2] != ("A", "D") for g in got)            # different group
    same = {"X": base, "Y": list(base)}                       # identical: a share class
    assert P.select_pairs(same, {"X": "g", "Y": "g"}) == []


def test_trade_pair_opens_on_divergence_and_closes_on_convergence():
    f = 252
    a = [100.0] * f + [110.0, 112.0, 100.0, 100.0]           # a jumps rich, then comes back
    b = [100.0] * f + [100.0, 100.0, 100.0, 100.0]
    a[10] = 100.5                                            # a little formation noise -> sigma > 0
    trades = P.trade_pair(a, b, formation=f, entry=2.0)
    assert len(trades) == 1
    tr = trades[0]
    assert tr["converged"] and tr["open"] == f and tr["close"] == f + 2
    assert tr["ret"] == pytest.approx(-(100 / 110 - 1))       # short a from 110 back to 100


def test_backtest_and_stretched_now_on_synthetic_pairs():
    base = _walk(900, 7)
    closes = {"A": base, "B": _twin(base, 8, 0.01), "C": _walk(900, 9), "D": _twin(_walk(900, 9), 10)}
    groups = {t: "g" for t in closes}
    bt = P.backtest(closes, groups, top=3)
    assert bt["periods"] == (900 - 252) // 126 and bt["trades"] >= 1
    assert 0 <= bt["win_rate"] <= 1 and bt["avg_days"] > 0
    now = P.stretched_now(closes, groups, top=3)
    assert now and all(set(x) >= {"a", "b", "z", "rich", "cheap", "stretched"} for x in now)
    assert P.backtest({"A": [1] * 10, "B": [1] * 11}, groups) is None


def test_spread_z_series():
    a = [100 * math.exp(0.001 * i) for i in range(200)]
    b = [100.0] * 200
    z = P.spread_z_series(a, b, lookback=100)
    assert z[0] is None and z[-1] is not None and z[-1] > 1      # a keeps pulling ahead
