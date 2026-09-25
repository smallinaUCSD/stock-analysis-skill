"""Analyst ratings summary: consensus label, split, trend, target upside."""

from stockskill.data.analysts import summarize


def _m(period, sb, b, h, s, ss):
    return {"period": period, "strong_buy": sb, "buy": b, "hold": h, "sell": s, "strong_sell": ss}


def test_summary_split_label_trend_and_target():
    tr = [_m("2026-06-01", 20, 40, 10, 0, 0), _m("2026-09-01", 24, 41, 3, 1, 0)]
    s = summarize(tr, target_mean=300.0, price=200.0)
    assert s["analysts"] == 69 and s["label"] == "Buy"
    assert abs(s["buy_pct"] - 65 / 69) < 1e-9 and abs(s["sell_pct"] - 1 / 69) < 1e-9
    assert abs(s["buy_change"] - (65 / 69 - 60 / 70)) < 1e-9 and s["months"] == 2
    assert abs(s["upside"] - 0.5) < 1e-9


def test_labels_across_the_scale():
    assert summarize([_m("x", 10, 0, 0, 0, 0)])["label"] == "Strong buy"
    assert summarize([_m("x", 0, 0, 10, 0, 0)])["label"] == "Hold"
    assert summarize([_m("x", 0, 0, 0, 1, 9)])["label"] == "Strong sell"


def test_no_coverage():
    s = summarize([_m("x", 0, 0, 0, 0, 0)], target_mean=None, price=10.0)
    assert "analysts" not in s and s["upside"] is None
