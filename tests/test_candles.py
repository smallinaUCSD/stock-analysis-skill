from datetime import date, timedelta

from stockskill.technicals.candles import chart_bars, slice_period, weekly


def _ohlcv(n, start=date(2026, 1, 5)):          # 2026-01-05 is a Monday
    days = []
    d = start
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return {"dates": days, "open": [float(i) for i in range(n)],
            "high": [i + 2.0 for i in range(n)], "low": [i - 1.0 for i in range(n)],
            "close": [i + 0.5 for i in range(n)], "volume": [100] * n}


def test_weekly_aggregates_each_iso_week():
    w = weekly(_ohlcv(10))                       # two full Mon-Fri weeks
    assert w["dates"] == ["2026-01-09", "2026-01-16"]
    assert w["open"] == [0.0, 5.0]               # first open of the week
    assert w["high"] == [6.0, 11.0]              # max high
    assert w["low"] == [-1.0, 4.0]               # min low
    assert w["close"] == [4.5, 9.5]              # last close
    assert w["volume"] == [500, 500]


def test_slice_period_trims_every_series():
    s = slice_period(_ohlcv(400), "1y")
    assert len(s["dates"]) == len(s["close"]) == len(s["volume"]) == 253
    assert len(slice_period(_ohlcv(50), "1y")["dates"]) == 50


def test_chart_bars_switches_to_weekly_for_long_periods():
    o = _ohlcv(1300)
    daily = chart_bars(o, "1y")
    assert daily["interval"] == "1d" and isinstance(daily["dates"][0], str)
    wk = chart_bars(o, "5y")
    assert wk["interval"] == "1wk" and len(wk["dates"]) < 300
