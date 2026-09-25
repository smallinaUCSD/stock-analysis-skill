"""Economy: iCalendar parsing, release classification, FOMC page, FRED
transforms, Treasury curve summary."""

from datetime import date, datetime

from stockskill.data import economy as E

_ICS = """BEGIN:VCALENDAR\r
BEGIN:VEVENT\r
DTSTART;TZID=US-Eastern:20261014T083000\r
SUMMARY:Consumer Price Index for September\r
  2026\r
END:VEVENT\r
BEGIN:VEVENT\r
DTSTART:20261029T123000Z\r
SUMMARY:GDP (Advance Estimate)\\, 3rd Quarter 2026\r
END:VEVENT\r
BEGIN:VEVENT\r
DTSTART;VALUE=DATE:20261101\r
SUMMARY:All-day thing\r
END:VEVENT\r
END:VCALENDAR\r
"""


def test_parse_ics_folding_timezones_and_escapes():
    ev = E.parse_ics(_ICS)
    assert ev[0] == {"title": "Consumer Price Index for September 2026", "start": datetime(2026, 10, 14, 8, 30)}
    assert ev[1]["title"] == "GDP (Advance Estimate), 3rd Quarter 2026"
    assert ev[1]["start"] == datetime(2026, 10, 29, 8, 30)          # 12:30 UTC = 8:30 EDT
    assert ev[2]["start"] == date(2026, 11, 1)


def test_classify_releases():
    assert E.classify("Consumer Price Index for September 2026")[:2] == ("CPI inflation", 3)
    assert E.classify("Employment Situation")[0] == "Jobs report"
    assert E.classify("GDP (Third Estimate), Industries, Corporate Profits")[0] == "GDP"
    assert E.classify("Gross Domestic Product by State, 2nd Quarter 2026") is None
    assert E.classify("Employee Tenure") is None


def test_parse_fomc_page():
    html = ('<h4><a>2026 FOMC Meetings</a></h4>'
            '<div class="fomc-meeting__month col"><strong>January</strong></div><div class="fomc-meeting__date col">27-28</div>'
            '<div class="fomc-meeting__month col"><strong>April/May</strong></div><div class="fomc-meeting__date col">30-1</div>'
            '<h4><a>2025 FOMC Meetings</a></h4>'
            '<div class="fomc-meeting__month col"><strong>December</strong></div><div class="fomc-meeting__date col">9-10*</div>')
    assert E.parse_fomc(html) == [date(2025, 12, 10), date(2026, 1, 28), date(2026, 5, 1)]


def test_fred_transforms():
    rows = E.parse_fred("observation_date,X\n2025-07-01,100\n2025-08-01,101\n2026-07-01,103\n2026-08-01,104.04\nbad,row\n")
    assert len(rows) == 4
    y = E.reading(rows, "yoy")
    assert abs(y["value"] - 3.0099) < 1e-3 and abs(y["prev"] - 3.0) < 1e-9 and y["period"] == "2026-08-01"
    assert abs(E.reading(rows, "mom")["value"] - 1.0097) < 1e-3
    assert E.reading(rows, "chg")["value"] == 104.04 - 103
    assert E.reading([], "level") is None


def test_display_and_period_labels():
    assert E.display(162.0, "jobs") == "+162K jobs"
    assert E.display(7271.0, "openings") == "7.27M openings"
    assert E.display(-88576.0, "usd_m") == "-$88.6B"
    assert E.display(3.35, "pct_yoy") == "3.4% a year"
    assert E.period_label("2026-04-01", "A191RL1Q225SBEA") == "Q2 2026"
    assert E.period_label("2026-09-19", "ICSA") == "week to Sep 19"
    assert E.period_label("2026-08-01", "CPIAUCSL") == "Aug 2026"


def test_treasury_and_curve_summary():
    csv_ = ('Date,"1 Mo","3 Mo","2 Yr","10 Yr","30 Yr"\n'
            '09/24/2026,4.0,4.2,4.9,5.2,5.5\n09/17/2026,4.0,4.1,4.7,5.0,5.3\n'
            '08/24/2026,3.9,3.9,4.2,4.6,5.2\n09/24/2025,4.2,4.0,3.6,4.2,4.8\n')
    rows = E.parse_treasury(csv_)
    assert rows[0]["date"] == "2026-09-24" and rows[0]["10 Yr"] == 5.2
    s = E.curve_summary(rows)
    assert s["curves"]["now"]["date"] == "2026-09-24" and s["curves"]["1y"]["date"] == "2025-09-24"
    assert s["key"]["10 Yr"]["1w"] == 0.2 and s["key"]["2 Yr"]["1y"] == 1.3
    assert s["spread"][-1] == {"date": "2026-09-24", "s10_2": 0.3, "s10_3m": 1.0}
    assert s["spread"][0]["s10_2"] == 0.6                     # oldest first


def test_weekly_claims_are_thursdays():
    ds = E.weekly_claims(date(2026, 9, 24), date(2026, 10, 10))
    assert ds == [date(2026, 9, 24), date(2026, 10, 1), date(2026, 10, 8)]


def test_economy_route(tmp_path, monkeypatch):
    from stockskill.server import create_app
    monkeypatch.setattr(E, "calendar", lambda d: [{"date": "2026-10-14", "name": "CPI inflation", "importance": 3}])
    monkeypatch.setattr(E, "yield_curve", lambda d: {})
    c = create_app(tickers_path=str(tmp_path / "t.csv"), public=True).test_client()
    assert c.get("/economy").status_code == 200
    d = c.get("/api/economy").get_json()
    assert d["ok"] and d["calendar"][0]["name"] == "CPI inflation"


def test_market_performance_windows():
    from datetime import date, timedelta
    from stockskill.data.markets import performance
    d0 = date(2025, 9, 1)
    dates = [d0 + timedelta(days=i) for i in range(400)]
    closes = [100 + i * 0.1 for i in range(400)]
    p = performance(dates, closes)
    last = closes[-1]
    assert p["last"] == last and abs(p["d1"] - (last / closes[-2] - 1)) < 1e-12
    assert abs(p["w1"] - (last / closes[-8] - 1)) < 1e-12
    ytd_base = closes[dates.index(date(2025, 12, 31))]
    assert abs(p["ytd"] - (last / ytd_base - 1)) < 1e-12
    y = performance(dates, [4.0 + i * 0.001 for i in range(400)], kind="yield")
    assert abs(y["d1"] - 0.001) < 1e-9                    # yields move in points, not percent
    assert len(p["spark"]) in (91, 92) and 70 <= len(p["line"]) <= 76     # calendar-day test data
    assert performance([], []) == {}
