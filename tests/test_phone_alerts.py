"""Phone alerts: rule validation, crossing/re-arming, dedupe, routes."""

from datetime import date

import pytest

from stockskill.alerts import phone as AL


def test_new_rule_validation():
    r = AL.new_rule("price_above", "nvda", 200)
    assert r["ticker"] == "NVDA" and r["value"] == 200.0 and r["on"]
    assert AL.new_rule("move", None, 5)["ticker"] == "*"
    assert AL.new_rule("insider_buy")["value"] == 100_000.0
    with pytest.raises(ValueError):
        AL.new_rule("price_below", "NVDA", None)
    with pytest.raises(ValueError):
        AL.new_rule("price_above", None, 10)
    with pytest.raises(ValueError):
        AL.new_rule("nope")


def test_price_level_fires_once_and_rearms():
    rule = {"id": "r1", "type": "price_above", "ticker": "NVDA", "value": 200.0, "on": True}
    st = {}
    assert AL.evaluate_prices([rule], {"NVDA": {"price": 199.0}}, st, "2026-09-24") == []
    ev = AL.evaluate_prices([rule], {"NVDA": {"price": 201.0}}, st, "2026-09-24")
    assert len(ev) == 1 and "NVDA rose to $201.00" == ev[0]["title"]
    assert AL.evaluate_prices([rule], {"NVDA": {"price": 202.0}}, st, "2026-09-24") == []   # still above: quiet
    AL.evaluate_prices([rule], {"NVDA": {"price": 199.5}}, st, "2026-09-24")                # within 1%: not re-armed
    assert AL.evaluate_prices([rule], {"NVDA": {"price": 201.0}}, st, "2026-09-24") == []
    AL.evaluate_prices([rule], {"NVDA": {"price": 197.0}}, st, "2026-09-24")                # re-armed
    assert len(AL.evaluate_prices([rule], {"NVDA": {"price": 200.0}}, st, "2026-09-24")) == 1


def test_move_rule_over_watchlist_once_per_day():
    rule = {"id": "m", "type": "move", "ticker": "*", "value": 5.0, "on": True}
    q = {"AAA": {"price": 10.0, "change_pct": -0.062}, "BBB": {"price": 5.0, "change_pct": 0.01}}
    st = {}
    ev = AL.evaluate_prices([rule], q, st, "2026-09-24", ["AAA", "BBB"])
    assert [e["ticker"] for e in ev] == ["AAA"] and "down 6.2%" in ev[0]["title"]
    assert AL.evaluate_prices([rule], q, st, "2026-09-24", ["AAA", "BBB"]) == []
    assert len(AL.evaluate_prices([rule], q, st, "2026-09-25", ["AAA", "BBB"])) == 1


def test_paused_rules_are_ignored():
    rule = {"id": "r", "type": "price_below", "ticker": "X", "value": 10.0, "on": False}
    assert AL.evaluate_prices([rule], {"X": {"price": 1.0}}, {}, "2026-09-24") == []


def test_daily_event_builders_dedupe():
    st = {}
    r = {"id": "b"}
    c = [{"ticker": "MU", "close": 120.0, "change": 0.04, "score": 3}]
    assert len(AL.breakout_events(r, c, st, "2026-09-24")) == 1
    assert AL.breakout_events(r, c, st, "2026-09-24") == []
    ins = {"AAA": [{"name": "JANE DOE", "date": "2026-09-23", "code": "P", "shares": 10_000, "price": 20.0},
                   {"name": "JOHN ROE", "date": "2026-09-23", "code": "S", "shares": -50_000, "price": 20.0},
                   {"name": "SMALL", "date": "2026-09-23", "code": "P", "shares": 10, "price": 20.0}]}
    ev = AL.insider_events({"id": "i", "value": 100_000}, ins, st, "2026-09-21")
    assert len(ev) == 1 and ev[0]["title"] == "Insider bought AAA: $0.20M" and "Jane Doe" in ev[0]["body"]
    assert AL.insider_events({"id": "i", "value": 100_000}, ins, st, "2026-09-21") == []
    er = AL.earnings_events({"id": "e"}, [{"ticker": "NKE", "date": "2026-09-28", "timing": "post", "eps_est": 0.44}], st)
    assert er[0]["title"] == "NKE reports Monday after the close"


def test_next_trading_day_skips_weekend():
    assert AL.next_trading_day(date(2026, 9, 25)) == date(2026, 9, 28)   # Fri -> Mon
    assert AL.next_trading_day(date(2026, 9, 23)) == date(2026, 9, 24)


def test_send_needs_topic_and_posts_json(monkeypatch):
    assert AL.send({"title": "x"}) is False
    sent = {}

    class R:
        status_code = 200
    import requests
    monkeypatch.setattr(requests, "post", lambda url, data=None, timeout=None: (sent.update(url=url, data=data), R())[1])
    monkeypatch.setenv("NTFY_TOPIC", "t-123")
    monkeypatch.setenv("STOCKSKILL_PUBLIC_URL", "https://example.test/")
    assert AL.send({"title": "NVDA up 5%", "ticker": "NVDA"}) is True
    import json
    body = json.loads(sent["data"])
    assert sent["url"] == "https://ntfy.sh" and body["topic"] == "t-123"
    assert body["click"] == "https://example.test/analysis/NVDA"


def test_store_roundtrip_and_state_pruning(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_ALERTS_FILE", str(tmp_path / "a.json"))
    assert AL.load() == {"rules": [], "log": [], "state": {}}
    AL.save({"rules": [{"id": "x"}], "log": [{"title": str(i)} for i in range(100)],
             "state": {"bo:A:2000-01-01": "2000-01-01", "arm:x": "fired", "bo:B:today": date.today().isoformat()}})
    d = AL.load()
    assert d["rules"] == [{"id": "x"}] and len(d["log"]) == 60
    assert set(d["state"]) == {"arm:x", "bo:B:today"}


def test_alert_routes_private_only(tmp_path, monkeypatch):
    from stockskill.server import create_app
    monkeypatch.setenv("STOCKSKILL_ALERTS_FILE", str(tmp_path / "a.json"))
    pub = create_app(tickers_path=str(tmp_path / "t.csv"), public=True).test_client()
    assert pub.get("/alerts").status_code == 404 and pub.get("/api/alerts").status_code == 404
    c = create_app(tickers_path=str(tmp_path / "t.csv"), public=False,
                   holdings_path=str(tmp_path / "h.csv")).test_client()
    d = c.get("/api/alerts").get_json()
    assert d["ok"] and d["topic"] is None and d["suggested"].startswith("stockskill-")
    assert c.post("/api/alerts", json={"type": "price_above", "ticker": "NVDA", "value": "250"}).get_json()["ok"]
    assert c.post("/api/alerts", json={"type": "price_above", "ticker": "NVDA"}).status_code == 400
    assert c.post("/api/alerts", json={"type": "breakout"}).get_json()["ok"]
    assert c.post("/api/alerts", json={"type": "breakout"}).status_code == 400          # only one
    rules = c.get("/api/alerts").get_json()["rules"]
    assert len(rules) == 2
    c.post(f"/api/alerts/{rules[0]['id']}/toggle")
    assert c.get("/api/alerts").get_json()["rules"][0]["on"] is False
    c.delete(f"/api/alerts/{rules[1]['id']}")
    assert len(c.get("/api/alerts").get_json()["rules"]) == 1
    assert c.post("/api/alerts/test").status_code == 400                              # no topic
    assert c.get("/alerts").status_code == 200


def test_checker_can_be_turned_off_per_process(monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "t-123")
    monkeypatch.setenv("STOCKSKILL_ALERTS", "0")
    c = AL.Checker(lambda: [], lambda: ("", []))
    c.start()
    assert c._started is False
