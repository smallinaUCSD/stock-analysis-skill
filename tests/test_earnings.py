"""Earnings: release timing from SEC timestamps, reaction day, history."""

from datetime import date, timedelta

from stockskill.data.earnings import dedupe_releases, history, reaction, release_timing, stats


def test_release_timing_in_new_york_time():
    # 20:21 UTC in August = 4:21pm EDT -> after the close
    assert release_timing("2026-08-26T20:21:19.000Z") == (date(2026, 8, 26), "post")
    # 11:30 UTC in January = 6:30am EST -> before the open
    assert release_timing("2026-01-13T11:30:00.000Z") == (date(2026, 1, 13), "pre")
    assert release_timing("2026-03-02T15:00:00.000Z")[1] == "during"
    # 02:00 UTC is still the previous evening in New York
    assert release_timing("2026-02-26T02:00:00.000Z") == (date(2026, 2, 25), "post")
    assert release_timing("garbage") is None


def _days():
    # Mon 2026-08-24 .. Fri 2026-08-28, then Mon 2026-08-31
    ds = [date(2026, 8, 24) + timedelta(days=i) for i in range(5)] + [date(2026, 8, 31)]
    return ds, [100.0, 101.0, 102.0, 110.0, 99.0, 105.0]


def test_reaction_after_close_uses_next_session():
    ds, cs = _days()
    r = reaction(ds, cs, date(2026, 8, 26), "post")        # Wed after close -> Thu vs Wed
    assert r["day"] == "2026-08-27" and abs(r["move"] - (110 / 102 - 1)) < 1e-12


def test_reaction_before_open_uses_same_session():
    ds, cs = _days()
    r = reaction(ds, cs, date(2026, 8, 26), "pre")         # Wed before open -> Wed vs Tue
    assert r["day"] == "2026-08-26" and abs(r["move"] - (102 / 101 - 1)) < 1e-12


def test_reaction_on_weekend_reacts_monday():
    ds, cs = _days()
    r = reaction(ds, cs, date(2026, 8, 29), "post")        # Saturday -> Mon vs Fri
    assert r["day"] == "2026-08-31" and abs(r["move"] - (105 / 99 - 1)) < 1e-12
    assert reaction(ds, cs, date(2026, 9, 5), "pre") is None   # no data yet


def test_dedupe_keeps_one_per_quarter():
    rows = [{"date": date(2026, 7, 14)}, {"date": date(2026, 7, 20)}, {"date": date(2026, 4, 14)}]
    out = dedupe_releases(rows)
    assert [r["date"] for r in out] == [date(2026, 7, 14), date(2026, 4, 14)]


def test_history_matches_surprises_and_market():
    ds, cs = _days()
    ohlcv = {"dates": ds, "close": cs}
    spy = {"dates": ds, "close": [100.0, 100.0, 100.0, 101.0, 101.0, 101.0]}
    rel = [{"date": date(2026, 8, 26), "timing": "post"}, {"date": date(2026, 8, 25), "timing": "pre"}]
    surp = [{"quarter": 2, "year": 2027, "estimate": 2.0, "actual": 2.2, "surprise_pct": 10.0}]
    h = history(rel, ohlcv, spy, surp)
    assert h[0]["fq"] == "Q2 FY2027" and h[0]["eps_act"] == 2.2
    assert abs(h[0]["market"] - 0.01) < 1e-12
    assert "eps_act" not in h[1]
    st = stats(h, surp)
    assert st["n"] == 2 and st["up"] == 2 and st["beats"] == 1 and st["beat_n"] == 1


def test_earnings_routes(tmp_path, monkeypatch):
    from stockskill.data import earnings as E
    from stockskill.data import finnhub
    from stockskill.server import create_app
    c = create_app(tickers_path=str(tmp_path / "t.csv"), public=True).test_client()
    assert c.get("/earnings?t=nvda").status_code == 200
    assert c.get("/api/earnings/calendar").get_json()["ok"] is False      # no Finnhub key in tests
    monkeypatch.setattr(E, "releases", lambda t, d=None: [{"date": date(2026, 8, 26), "timing": "post"}])
    monkeypatch.setattr(E, "surprises", lambda t: [])
    monkeypatch.setattr(E, "upcoming", lambda t: {"date": "2026-11-17", "timing": "post"})
    monkeypatch.setattr(E, "recommendations", lambda t: [])
    d = c.get("/api/earnings/ZZZ").get_json()
    assert d["ok"] and d["next"]["date"] == "2026-11-17" and d["usual_timing"] == "post"
    monkeypatch.setattr(finnhub, "has_finnhub", lambda: True)
    monkeypatch.setattr(E, "calendar", lambda tks, days: [{"ticker": "ZZZ", "date": "2026-10-01", "timing": None}])
    cal = c.get("/api/earnings/calendar").get_json()
    assert cal["ok"] and cal["rows"][0]["usual_timing"] == "post"
