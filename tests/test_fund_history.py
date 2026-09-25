"""Hedge-fund history: change timeline, copy-the-portfolio simulation, alerts."""

from stockskill.data import funds13f as F


def _h(**pos):
    return {c: {"cusip": c, "name": c + " INC", "value": v, "shares": s, "put_call": None} for c, (v, s) in pos.items()}


def test_quarter_label():
    assert F.quarter_label("2026-06-30") == "Q2 2026" and F.quarter_label("2025-12-31") == "Q4 2025"


def test_history_events_between_quarters():
    q = [{"period": "2026-03-31", "filed": "2026-05-15", "holdings": _h(AAA=(100, 10), BBB=(50, 5))},
         {"period": "2026-06-30", "filed": "2026-08-14", "holdings": _h(AAA=(150, 15), CCC=(40, 4))}]
    ev = {(e["cusip"], e["change"]) for e in F.history_events(q)}
    assert ev == {("AAA", "Added"), ("CCC", "New"), ("BBB", "Sold out")}


def test_copy_performance_rebalances_only_once_public():
    days = ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"]
    prices = {"AAA": (days, [10.0, 11.0, 12.0, 12.0]), "BBB": (days, [20.0, 20.0, 20.0, 30.0])}
    bench = (days, [100.0, 101.0, 102.0, 103.0])
    plan = [("2026-01-02", {"AAA": 1.0}), ("2026-01-06", {"BBB": 1.0})]      # switch when the next filing is public
    p = F.copy_performance(plan, prices, bench)
    # all in AAA: 10k -> 11k -> 12k on Jan 6, then switch to BBB at 20 -> 30 on Jan 7
    assert p["value"] == [10000.0, 11000.0, 12000.0, 18000.0]
    assert abs(p["summary"]["return"] - 0.8) < 1e-9 and abs(p["summary"]["bench_return"] - 0.03) < 1e-9
    assert F.copy_performance([], prices, bench) is None


def test_fund_filing_alert_once(tmp_path, monkeypatch):
    import time
    from datetime import date
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "u.db"))
    from stockskill.accounts import db, notify as N
    db.init()
    uid = db.create_user("a@example.com")
    db.update_user(uid, onboarded=1, notify_inapp=1)
    db.follow(uid, "fund:1067983", "Berkshire Hathaway")
    filed = date.today().isoformat()
    monkeypatch.setattr(F, "_filings", lambda cik, n=2: [{"acc": "0001-26-1", "filed": filed, "period": "2026-06-30", "name": "BERKSHIRE"}])
    monkeypatch.setattr(F, "fund_report", lambda cik, cd=None, top=60: {"fund": "Berkshire Hathaway", "counts": {"New": 2, "Added": 1, "Trimmed": 3, "Sold out": 1}})

    class App:
        config = {"ACCT": {"cache_dir": str(tmp_path), "tickers_path": "x"}}
    s = N.Scheduler(App(), lambda t: None)
    followers = {"fund:1067983": [(uid, time.time() - 86400)]}
    assert s.run_funds(followers) == 1 and s.run_funds(followers) == 0          # once only
    item = db.notifications(uid)[0]
    assert item["title"] == "Berkshire Hathaway filed its Q2 2026 holdings" and "2 new positions" in item["body"]
    late = {"fund:1067983": [(uid, time.time() + 2 * 86400)]}                    # followed after it was filed
    db.delete_user(uid)
    assert s.run_funds(late) == 0
