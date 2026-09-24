import math
import random

import pytest

from stockskill.trade import forecast as F
from stockskill.trade import option_ideas as O


def test_ranges_are_ordered_and_widen_with_time():
    r = F.ranges(100.0, 0.30)
    assert [x["days"] for x in r] == [21, 63, 126, 252]
    for x in r:
        assert x["p10"] < x["p25"] < x["p50"] < x["p75"] < x["p90"]
    assert (r[-1]["p90"] - r[-1]["p10"]) > (r[0]["p90"] - r[0]["p10"])
    assert F.ranges(100.0, 0) == []


def test_coverage_is_near_80pct_on_lognormal_prices():
    rnd = random.Random(3)
    c = [100.0]
    for _ in range(2500):
        c.append(c[-1] * math.exp(rnd.gauss(0.043 / 252 - 0.5 * 0.3 ** 2 / 252, 0.3 / math.sqrt(252))))
    cov = F.coverage(c)
    assert cov["n"] > 50 and 0.65 <= cov["inside"] <= 0.95


def test_payoff_and_analysis_of_a_bull_call_spread():
    legs = [{"side": "buy", "kind": "call", "strike": 100.0, "price": 5.0},
            {"side": "sell", "kind": "call", "strike": 110.0, "price": 2.0}]
    a = O.analyze(legs, 100.0, 0.3, 30)
    assert a["net"] == pytest.approx(3.0)
    assert a["max_profit"] == pytest.approx(7.0) and a["max_loss"] == pytest.approx(3.0)
    assert a["breakevens"] == [pytest.approx(103.0, abs=0.1)]
    assert 0.2 < a["pop"] < 0.6


def test_naked_short_call_is_unlimited_loss_and_put_breakeven():
    short_call = O.analyze([{"side": "sell", "kind": "call", "strike": 100.0, "price": 4.0}], 100.0, 0.3, 30)
    assert short_call["max_loss"] is None and short_call["max_profit"] == pytest.approx(4.0)
    csp = O.analyze([{"side": "sell", "kind": "put", "strike": 90.0, "price": 2.0}], 100.0, 0.3, 30)
    assert csp["max_loss"] == pytest.approx(88.0) and csp["breakevens"] == [pytest.approx(88.0, abs=0.1)]


def _chain(spot, iv, days):
    """Rough Black-Scholes-ish prices for a strike ladder."""
    t = days / 365
    out_c, out_p = [], []
    N = O._N
    for k in range(int(spot * 0.6), int(spot * 1.4), 5):
        d1 = (math.log(spot / k) + 0.5 * iv * iv * t) / (iv * math.sqrt(t))
        d2 = d1 - iv * math.sqrt(t)
        c = spot * N.cdf(d1) - k * N.cdf(d2)
        out_c.append({"strike": float(k), "price": round(c, 2)})
        out_p.append({"strike": float(k), "price": round(c - spot + k, 2)})
    return out_c, out_p


def test_ideas_follow_the_view_and_option_richness():
    calls, puts = _chain(100.0, 0.40, 35)
    bull = [i["name"] for i in O.ideas(calls, puts, 100.0, 0.40, 0.30, 35, "bullish")]
    assert "Bull call spread" in bull and "Cash-secured put" in bull
    bear = [i["name"] for i in O.ideas(calls, puts, 100.0, 0.40, 0.30, 35, "bearish")]
    assert bear[0] == "Bear put spread"
    neutral_rich = [i["name"] for i in O.ideas(calls, puts, 100.0, 0.40, 0.30, 35, "neutral")]
    assert "Iron condor" in neutral_rich
    neutral_cheap = [i["name"] for i in O.ideas(calls, puts, 100.0, 0.40, 0.60, 35, "neutral")]
    assert neutral_cheap == ["Covered call (if you own 100 shares)"]
    assert O.view_from(3, 0.7) == "bullish" and O.view_from(-3, 0.3) == "bearish" and O.view_from(0, 0.5) == "neutral"
