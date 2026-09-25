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


def test_dividend_summary():
    from datetime import date
    from stockskill.data.dividends import summarize
    hist = []
    for y, amt in ((2019, 0.40), (2020, 0.41), (2021, 0.42), (2022, 0.44), (2023, 0.46), (2024, 0.485), (2025, 0.51)):
        for m in (3, 6, 9, 12):
            hist.append((f"{y}-{m:02d}-15", amt))
    hist.append(("2023-06-20", 0.92))                        # a glitch: two payments merged
    hist += [("2026-03-15", 0.53), ("2026-06-15", 0.53)]
    s = summarize(hist, price=70.0, eps=3.0, next_ex="2026-09-01", today=date(2026, 8, 1))
    assert s["pays"] and s["frequency"] == "Quarterly" and s["streak"] == 6
    assert abs(s["ttm"] - (0.51 * 2 + 0.53 * 2)) < 1e-9 and abs(s["yield"] - s["ttm"] / 70) < 1e-12
    assert abs(s["payout_ratio"] - s["ttm"] / 3.0) < 1e-12 and s["next_ex"] == "2026-09-01"
    assert s["since"] == 2019 and s["years"][-1]["year"] == 2026
    assert summarize([], 10.0) == {"pays": False}
    old = summarize([("2019-01-01", 0.2)], 10.0, today=date(2026, 1, 1))
    assert old["pays"] is False and old["yield"] is None
