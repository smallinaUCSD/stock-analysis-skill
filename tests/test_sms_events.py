"""Text-message alerts (phone numbers, codes, delivery), big-move market
events, and summaries that survive a failed or interrupted run. No network."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from stockskill.accounts import notify as N
from stockskill.accounts import sms as S

ET = ZoneInfo("America/New_York")


def test_normalize_phone_and_mask():
    assert S.normalize_phone("(415) 555-0134") == "+14155550134"
    assert S.normalize_phone("1-415-555-0134") == "+14155550134"
    assert S.normalize_phone("+44 20 7946 0958") == "+442079460958"
    for bad in ("", "12345", "(015) 555-0134", "+0123456789", "call me"):
        assert S.normalize_phone(bad) is None, bad
    assert S.mask("+14155550134") == "(•••) •••-0134"


def test_alert_text_is_short_and_has_opt_out():
    t = S.alert_text("SM Investments", "NVDA is up 6.1% today", "x" * 900, "https://site.test/analysis/NVDA")
    assert len(t) <= S.MAX_LEN and t.startswith("SM Investments: NVDA is up 6.1% today")
    assert t.endswith("https://site.test/analysis/NVDA\nReply STOP to opt out.")


def test_codes_expire_and_limit_tries(monkeypatch):
    code = S.new_code(1, "+14155550134")
    assert S.check_code(1, "000000" if code != "000000" else "111111") is None
    assert S.check_code(1, code) == "+14155550134"
    assert S.check_code(1, code) is None                           # one use
    S.new_code(2, "+14155550134")
    for _ in range(5):
        S.check_code(2, "not-it")
    assert S.check_code(2, S._CODES.get(2, {}).get("hash", "")) is None


def test_market_events_levels_and_no_repeats():
    q = {"SPY": {"change_pct": -0.021}, "NVDA": {"change_pct": 0.061, "price": 190.0},
         "AMD": {"change_pct": -0.012}, "MU": {"change_pct": 0.11}}
    keys, title, lines, url = N.market_events(["NVDA", "AMD", "MU"], q, set())
    assert title == "The S&P 500 is down 2.1% today"
    assert set(keys) == {"SPY:down:0.02", "NVDA:up:0.05", "MU:up:0.05", "MU:up:0.1"}
    assert lines[1].startswith("<b>MU</b> +11.0%")                 # biggest move first
    assert N.market_events(["NVDA", "AMD", "MU"], q, set(keys))[0] == []          # nothing new
    q["MU"]["change_pct"] = 0.07                                   # pulled back: stays quiet
    assert N.market_events(["MU"], {"MU": q["MU"]}, set(keys))[0] == []
    k, title, _, url = N.market_events(["AMD"], {"AMD": {"change_pct": 0.052}}, set())
    assert k == ["AMD:up:0.05"] and title == "AMD is up 5.2% today" and url == "/analysis/AMD"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_AUTH", "1")
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    monkeypatch.setenv("STOCKSKILL_PUBLIC_URL", "https://site.test")
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "STOCKSKILL_NOTIFY", "TWILIO_ACCOUNT_SID",
              "TWILIO_AUTH_TOKEN", "TWILIO_FROM", "TWILIO_MESSAGING_SERVICE_SID"):
        monkeypatch.delenv(k, raising=False)
    tk = tmp_path / "t.csv"
    tk.write_text("[M7]\nAAPL, NVDA\n\n[SEMIS]\nAMD, MU\n")
    from stockskill.accounts import auth, groups
    groups._CACHE["groups"] = None
    auth._HITS.clear()
    S._CODES.clear()
    from stockskill.server import create_app
    a = create_app(tickers_path=str(tk), public=True)
    a.config["ACCT"]["board"] = None
    yield a
    groups._CACHE["groups"] = None


def _onboarded(c):
    c.post("/auth/signup", json={"email": "a@example.com", "password": "a-long-password-1", "accept": True})
    c.post("/api/me/groups", json={"groups": ["mag7"]})
    c.post("/api/me/profile", json={"first_name": "Ada", "last_name": "L", "dob": "1990-01-01",
                                    "investor_type": "etf", "experience": "beginner"})
    c.post("/api/me/onboarded")


def test_phone_saved_before_texts_are_switched_on(app):
    c = app.test_client()
    _onboarded(c)
    assert c.get("/api/me").get_json()["sms_ready"] is False
    assert c.post("/api/me/phone", json={"phone": "415 555 0134"}).status_code == 400       # no consent
    assert c.post("/api/me/phone", json={"phone": "12", "consent": True}).status_code == 400
    r = c.post("/api/me/phone", json={"phone": "415 555 0134", "consent": True}).get_json()
    assert r["ok"] and r["pending"] and r["phone"] == "(•••) •••-0134"
    c.post("/api/me/notify", json={"times": "both", "sms": True, "events": True})
    n = c.get("/api/me").get_json()["user"]["notify"]
    assert n["sms"] and n["events"] and n["phone"] == "(•••) •••-0134" and not n["phone_verified"]
    assert c.post("/api/me/phone/remove").get_json()["ok"]
    assert c.get("/api/me").get_json()["user"]["notify"]["phone"] == ""


def test_phone_code_and_text_delivery(app, monkeypatch):
    from stockskill.accounts import db
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC1")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "t")
    monkeypatch.setenv("TWILIO_FROM", "+18885550100")
    texts = []
    monkeypatch.setattr(S, "send_sms", lambda to, body: texts.append((to, body)) or (True, None))
    c = app.test_client()
    _onboarded(c)
    r = c.post("/api/me/phone", json={"phone": "(415) 555-0134", "consent": True}).get_json()
    assert r["code_sent"] and texts[0][0] == "+14155550134"
    code = texts[0][1].split("your code is ")[1][:6]
    assert c.post("/api/me/phone/verify", json={"code": "999999" if code != "999999" else "111111"}).status_code == 400
    assert c.post("/api/me/phone/verify", json={"code": code}).get_json()["verified"]
    u = db.by_email("a@example.com")
    assert u["phone_verified"] == 1 and u["notify_sms"] == 1 and u["sms_consent_at"]
    out = N.deliver(u, "event", "NVDA is up 6.1% today", ["<b>NVDA</b> +6.1%"], "/analysis/NVDA", "ev:k", "NVDA is up 6.1% today")
    assert out["sms"] is True and texts[-1][1].startswith("SM Investments: NVDA is up 6.1% today")
    assert "https://site.test/analysis/NVDA" in texts[-1][1]
    with db.conn() as cx:
        assert cx.execute("SELECT channels FROM notifications WHERE dedupe='ev:k'").fetchone()[0] == "inapp,sms"


def test_market_events_run_once_per_level(app, monkeypatch):
    from stockskill.accounts import db
    c = app.test_client()
    _onboarded(c)
    u = db.by_email("a@example.com")
    db.update_user(u["id"], notify_events=1, notify_inapp=1)
    q = {"NVDA": {"change_pct": 0.064, "price": 190.0}, "SPY": {"change_pct": 0.004}}
    monkeypatch.setattr(N, "_quotes", lambda tks, cd, live_only=False: q)
    s = N.Scheduler(app, lambda t: None)
    s.last_trades = 9e18
    assert s.run_events(date(2026, 9, 25)) == 1
    assert s.run_events(date(2026, 9, 25)) == 0                      # same move: quiet
    q["NVDA"]["change_pct"] = 0.105
    assert s.run_events(date(2026, 9, 25)) == 1                      # crossed 10%
    titles = [n["title"] for n in db.notifications(u["id"])]
    assert titles == ["NVDA is up 10.5% today", "NVDA is up 6.4% today"]


def test_summary_retried_after_a_failed_run(app, monkeypatch):
    from stockskill.accounts import db
    c = app.test_client()
    _onboarded(c)
    u = db.by_email("a@example.com")
    db.update_user(u["id"], summary_times="post", notify_inapp=1)
    calls = {"n": 0}

    def flaky(tks, cd, live_only=False):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("quote service down")
        return {"SPY": {"change_pct": 0.01}}
    monkeypatch.setattr(N, "_quotes", flaky)
    import stockskill.data.earnings as E
    import stockskill.data.economy as EC
    monkeypatch.setattr(E, "calendar", lambda tks, days: [])
    monkeypatch.setattr(EC, "calendar", lambda cd, back, ahead: [])
    s = N.Scheduler(app, lambda t: None)
    s.last_trades = s.last_events = 9e18
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(N.time, "time", lambda: clock["t"])
    s.tick(datetime(2026, 9, 25, 16, 31, tzinfo=ET))                # fails
    assert db.notifications(u["id"]) == []
    clock["t"] += 60
    s.tick(datetime(2026, 9, 25, 16, 32, tzinfo=ET))                # too soon to retry
    assert calls["n"] == 1
    clock["t"] += 300
    s.tick(datetime(2026, 9, 25, 16, 37, tzinfo=ET))                # retried and sent
    assert [n["title"] for n in db.notifications(u["id"])] == ["Market close · Fri Sep 25"]
    clock["t"] += 600
    s.tick(datetime(2026, 9, 25, 16, 47, tzinfo=ET))                # done: not again
    assert calls["n"] == 2
