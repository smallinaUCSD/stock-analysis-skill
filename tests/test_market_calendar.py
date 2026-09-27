"""Market calendar: holidays and early closes in the market clock, monthly
options expiration, the merged event list and its .ics export."""

from datetime import date, datetime

from stockskill.data import market_calendar as MC
from stockskill.marketclock import ET, market_status


def test_holidays_and_early_closes_in_the_clock():
    assert market_status(datetime(2026, 11, 26, 11, 0, tzinfo=ET)).label == "holiday"      # Thanksgiving
    assert market_status(datetime(2026, 11, 26, 11, 0, tzinfo=ET)).is_weekday is False
    assert market_status(datetime(2026, 11, 27, 12, 30, tzinfo=ET)).label == "open"        # half day
    assert market_status(datetime(2026, 11, 27, 13, 30, tzinfo=ET)).label == "after-hours"
    assert market_status(datetime(2026, 11, 30, 13, 30, tzinfo=ET)).label == "open"        # a normal Monday


def test_options_expiration_third_friday():
    ex = MC.monthly_expirations(date(2026, 1, 1), date(2026, 12, 31))
    assert [d.isoformat() for d, _ in ex][:4] == ["2026-01-16", "2026-02-20", "2026-03-20", "2026-04-17"]
    assert [q for _, q in ex].count(True) == 4                                      # triple witching quarters
    ex27 = dict(MC.monthly_expirations(date(2027, 3, 1), date(2027, 3, 31)))
    assert date(2027, 3, 19) in ex27                                                # (Good Friday is the 26th)


def test_events_merge_and_filter():
    earn = [{"ticker": "NVDA", "date": "2026-11-18", "timing": "post", "eps_est": 1.21},
            {"ticker": "WMT", "date": "2026-11-19", "timing": "pre", "eps_est": 0.6}]       # not on the watchlist
    econ = [{"date": "2026-11-13", "time": "08:30", "name": "CPI inflation", "importance": 3, "source": "BLS",
             "last": {"text": "2.9%", "period": "Sep"}},
            {"date": "2026-11-13", "time": "10:00", "name": "Minor thing", "importance": 1, "source": "BLS"},
            {"date": "2026-12-09", "time": "14:00", "name": "Fed rate decision", "importance": 3, "source": "Fed"}]
    ipos = [{"date": "2026-11-20", "symbol": "NEWCO", "name": "NewCo", "low": 18.0, "high": 20.0, "exchange": "NASDAQ"}]
    ev = MC.events(["NVDA", "AAPL"], date(2026, 11, 1), date(2026, 12, 31), earn, econ, ipos)
    kinds = {(e["kind"], e["date"]) for e in ev}
    assert ("earnings", "2026-11-18") in kinds and ("earnings", "2026-11-19") not in kinds
    assert ("economy", "2026-11-13") in kinds and ("fed", "2026-12-09") in kinds
    assert ("market", "2026-11-26") in kinds and ("market", "2026-11-27") in kinds and ("ipo", "2026-11-20") in kinds
    assert ("options", "2026-12-18") in kinds
    cpi = next(e for e in ev if e["title"] == "CPI inflation")
    assert cpi["detail"] == "last: 2.9% (Sep)" and not any(e["title"] == "Minor thing" for e in ev)
    nv = next(e for e in ev if e["kind"] == "earnings")
    assert nv["time"] == "16:05" and "after the close" in nv["detail"] and "$1.21" in nv["detail"]
    assert [e["date"] for e in ev] == sorted(e["date"] for e in ev)


def test_ics_export():
    ev = MC.events([], date(2026, 11, 26), date(2026, 11, 27), [], [], [])
    ics = MC.to_ics(ev)
    assert ics.startswith("BEGIN:VCALENDAR") and ics.rstrip().endswith("END:VCALENDAR")
    assert "DTSTART;VALUE=DATE:20261126" in ics and "SUMMARY:Market closed" in ics
    assert "DTSTART;TZID=America/New_York:20261127T130000" in ics
