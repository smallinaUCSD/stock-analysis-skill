import math
from datetime import date

import pytest

from stockskill.trade.expected_move import option_price, pick_expiries, straddle_move


def test_option_price_prefers_live_mid_then_last():
    assert option_price(1.0, 1.2, 0.9) == (pytest.approx(1.1), "mid")
    assert option_price(0, 0, 2.5) == (2.5, "last")           # after hours: no quotes
    assert option_price(None, None, None) == (None, None)
    assert option_price(1.3, 1.2, 0) == (None, None)          # crossed quote, no last


def test_straddle_move_and_implied_vol_round_trip():
    spot, sigma, days = 100.0, 0.40, 30
    t = days / 365
    straddle = math.sqrt(2 / math.pi) * spot * sigma * math.sqrt(t)
    m = straddle_move(spot, straddle / 2, straddle / 2, days)
    assert m["iv"] == pytest.approx(0.40)
    assert m["move_pct"] == pytest.approx(straddle / spot)
    assert m["low"] == pytest.approx(spot - straddle) and m["high"] == pytest.approx(spot + straddle)
    assert straddle_move(100, 1, 1, 0) is None


def test_pick_expiries_week_month_and_earnings():
    today = date(2026, 9, 24)
    ex = ["2026-09-25", "2026-10-02", "2026-10-09", "2026-10-16", "2026-10-23", "2026-11-20"]
    got = pick_expiries(ex, today, earnings="2026-11-05")
    assert got == [("Next week", "2026-10-02"), ("About a month", "2026-10-23"),
                   ("Through earnings", "2026-11-20")]
    # earnings before the month expiry: that row is labeled instead of duplicated
    got2 = pick_expiries(ex, today, earnings="2026-10-20")
    assert ("About a month (includes earnings)", "2026-10-23") in got2 and len(got2) == 2
    assert pick_expiries([], today) == []
