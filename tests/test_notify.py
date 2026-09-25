"""Notifications: summary text, politician-trade matching, delivery channels,
settings endpoints, email confirm/unsubscribe links, the scheduler."""

from datetime import date, datetime

import pytest

from stockskill.accounts import notify as N

GROUPS = [{"key": "semis", "label": "Semiconductors", "tickers": ["AMD", "MU", "NVDA"]},
          {"key": "energy", "label": "Energy", "tickers": ["XOM", "CVX"]}]
Q = {"SPY": {"change_pct": 0.004}, "QQQ": {"change_pct": 0.01}, "AMD": {"change_pct": 0.03},
     "MU": {"change_pct": -0.01}, "NVDA": {"change_pct": 0.02}, "XOM": {"change_pct": -0.02},
     "CVX": {"change_pct": -0.01}, "AAPL": {"change_pct": 0.005}}


def test_compose_summary_personalised():
    u = {"first_name": "Ada", "summary_groups": "semis,energy"}
    er = [{"ticker": "NVDA", "date": "2026-09-25", "timing": "post"}]
    ec = [{"name": "CPI inflation", "date": "2026-09-25", "time": "08:30"}]
    title, lines, push = N.compose_summary("pre", u, ["AAPL", "AMD", "MU", "XOM"], Q, GROUPS, er, ec, date(2026, 9, 25))
    text = " ".join(lines)
    assert title == "Before the bell · Fri Sep 25" and "Good morning, Ada" in text
    assert "S&amp;P 500" not in text and "S&P 500 <b>+0.4%</b>" in text
    assert text.index("Semiconductors") < text.index("Energy")          # best sector first
    assert "Semiconductors <b>+1.3%</b> (best AMD +3.0%, worst MU -1.0%)" in text
    assert "gainers:</b> AMD +3.0%, AAPL +0.5%" in text and "decliners:</b> XOM -2.0%, MU -1.0%" in text
    assert "NVDA today after the close" in text and "CPI inflation today at 8:30am ET" in text
    assert push.startswith("S&P 500 +0.4%")


def test_compose_summary_close_and_empty():
    title, lines, push = N.compose_summary("post", {}, [], {}, GROUPS, [], [], date(2026, 9, 25))
    assert title.startswith("Market close") and len(lines) == 1 and push == "Your market summary"


def test_trade_events_only_new_and_followed():
    trades = [{"member": "Jane Doe", "filed": "2026-09-20", "ticker": "NVDA", "type": "Buy", "amount": "$1K-$15K"},
              {"member": "Jane Doe", "filed": "2026-08-01", "ticker": "AAPL", "type": "Sell"},     # too old
              {"member": "John Roe", "filed": "2026-09-21", "ticker": "MSFT", "type": "Buy"}]     # not followed
    followed_at = datetime(2026, 9, 10).timestamp()
    late = datetime(2026, 9, 22).timestamp()
    ev = N.trade_events(trades, {"jane": [(1, followed_at), (2, late)]},
                        lambda t: "jane" if t["member"] == "Jane Doe" else "john", today=date(2026, 9, 25))
    assert [(u, t["ticker"]) for u, t, _ in ev] == [(1, "NVDA")]         # user 2 followed after it was filed
    title, lines, url = N.trade_message(trades[0], "jane")
    assert title == "Jane Doe bought NVDA" and url == "/politician/jane" and "45 days" in lines[1]


def test_tokens_roundtrip_and_tamper():
    t = N.token(5, "a@b.com", "unsub", secret="s3cret")
    assert N.read_token(t, "unsub", 60, secret="s3cret") == {"u": 5, "e": "a@b.com"}
    assert N.read_token(t, "verify", 60, secret="s3cret") is None          # wrong purpose
    assert N.read_token(t + "x", "unsub", 60, secret="s3cret") is None


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_AUTH", "1")
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    monkeypatch.setenv("STOCKSKILL_PUBLIC_URL", "https://site.test")
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "STOCKSKILL_NOTIFY"):
        monkeypatch.delenv(k, raising=False)
    tk = tmp_path / "t.csv"
    tk.write_text("[M7]\nAAPL, NVDA\n\n[SEMIS]\nAMD, MU\n")
    from stockskill.accounts import auth, groups
    groups._CACHE["groups"] = None
    auth._HITS.clear()
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


def test_settings_follows_and_inbox(app, monkeypatch):
    c = app.test_client()
    _onboarded(c)
    me = c.get("/api/me").get_json()
    assert me["user"]["notify"]["set"] is False and me["push_key"] and me["email_ready"] is False
    assert c.post("/api/me/notify", json={"times": "soon"}).status_code == 400
    assert c.post("/api/me/notify", json={"times": "pre"}).status_code == 400          # no channel
    r = c.post("/api/me/notify", json={"times": "both", "groups": ["semis", "bogus"], "email": True, "inapp": True}).get_json()
    assert r["ok"] and r["email_pending"] and not r["verification_sent"]            # no SMTP configured
    n = c.get("/api/me").get_json()["user"]["notify"]
    assert n["times"] == "both" and n["groups"] == ["semis"] and n["email"] and n["inapp"] and not n["email_verified"]
    f = c.post("/api/me/follows", json={"add": [{"pid": "jane-doe", "name": "Jane"}, {"pid": "bad pid!"}]}).get_json()
    assert [x["pid"] for x in f["follows"]] == ["jane-doe"]
    assert c.post("/api/me/push", json={"subscription": {"endpoint": "http://x"}}).status_code == 400
    assert c.post("/api/me/push", json={"subscription": {"endpoint": "https://push.test/1",
                                                          "keys": {"p256dh": "k", "auth": "a"}}}).get_json()["ok"]
    sent = []
    monkeypatch.setattr(N, "send_push", lambda uid, t, b, u: sent.append(t) or 1)
    t = c.post("/api/me/notify/test").get_json()
    assert t["inapp"] and t["email"] is False                           # email not confirmed yet
    box = c.get("/api/me/notifications").get_json()
    assert box["unread"] == 1 and box["items"][0]["title"] == "Test notification"
    c.post("/api/me/notifications/read")
    assert c.get("/api/me/notifications").get_json()["unread"] == 0


def test_verify_and_unsubscribe_links(app):
    from stockskill.accounts import db
    c = app.test_client()
    _onboarded(c)
    u = db.by_email("a@example.com")
    with app.app_context():
        bad = c.get("/notifications/verify?t=nope")
        assert bad.status_code == 400
        good = N.token(u["id"], u["email"], "verify", secret=app.secret_key)
        assert c.get("/notifications/verify?t=" + good).status_code == 200
        assert db.get_user(u["id"])["email_verified"] == 1
        db.update_user(u["id"], notify_email=1)
        un = N.token(u["id"], u["email"], "unsub", secret=app.secret_key)
        anon = app.test_client()                                          # works without signing in
        assert anon.post("/notifications/unsubscribe?t=" + un).status_code == 200
        assert db.get_user(u["id"])["notify_email"] == 0


def test_deliver_channels_and_dedupe(app, monkeypatch):
    from stockskill.accounts import db
    c = app.test_client()
    _onboarded(c)
    u = db.by_email("a@example.com")
    db.update_user(u["id"], notify_email=1, email_verified=1, notify_push=1, notify_inapp=1)
    u = db.get_user(u["id"])
    mails, pushes = [], []
    monkeypatch.setattr(N, "send_email", lambda to, s, t, h=None, unsubscribe=None: mails.append((to, s, unsubscribe)) or True)
    monkeypatch.setattr(N, "send_push", lambda uid, t, b, url: pushes.append((t, b)) or 1)
    r = N.deliver(u, "summary", "Title", ["Line <b>one</b>"], "/", "k1", "short")
    assert r == {"inapp": True, "email": True, "push": 1}
    assert mails[0][0] == "a@example.com" and mails[0][2].startswith("https://site.test/notifications/unsubscribe?t=")
    assert pushes == [("Title", "short")]
    assert N.deliver(u, "summary", "Title", ["x"], "/", "k1") == {"duplicate": True}
    assert db.notifications(u["id"])[0]["body"] == "Line one"


def test_scheduler_sends_each_slot_once(app, monkeypatch):
    from stockskill.accounts import db
    c = app.test_client()
    _onboarded(c)
    u = db.by_email("a@example.com")
    db.update_user(u["id"], summary_times="pre", summary_groups="semis", notify_inapp=1)
    monkeypatch.setattr(N, "_quotes", lambda tks, cd: Q)
    import stockskill.data.earnings as E
    import stockskill.data.economy as EC
    monkeypatch.setattr(E, "calendar", lambda tks, days: [])
    monkeypatch.setattr(EC, "calendar", lambda cd, back, ahead: [])
    s = N.Scheduler(app, lambda t: None)
    s.last_trades = 9e18                                                 # skip the trade check
    from zoneinfo import ZoneInfo
    s.tick(datetime(2026, 9, 25, 8, 35, tzinfo=ZoneInfo("America/New_York")))
    s.tick(datetime(2026, 9, 25, 8, 50, tzinfo=ZoneInfo("America/New_York")))
    items = db.notifications(u["id"])
    assert len(items) == 1 and items[0]["title"] == "Before the bell · Fri Sep 25"
    s.tick(datetime(2026, 9, 26, 8, 35, tzinfo=ZoneInfo("America/New_York")))   # Saturday: nothing
    assert len(db.notifications(u["id"])) == 1


def test_pwa_assets(app):
    c = app.test_client()
    sw = c.get("/sw.js")
    assert sw.status_code == 200 and sw.headers["Service-Worker-Allowed"] == "/" and b"showNotification" in sw.data
    assert c.get("/manifest.webmanifest").get_json()["display"] == "standalone"
    png = c.get("/icon-192.png")
    assert png.status_code == 200 and png.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_confirmation_email_failure_is_explained(app, monkeypatch):
    import smtplib
    c = app.test_client()
    _onboarded(c)
    r = c.post("/api/me/notify", json={"times": "pre", "email": True}).get_json()
    assert r["email_pending"] and not r["verification_sent"] and "SMTP settings missing" in r["email_error"]
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_USER", "u@test")
    monkeypatch.setenv("SMTP_PASSWORD", "abcd efgh ijkl mnop")

    class Boom:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, user, pw):
            assert " " not in pw                          # spaces in an app password are dropped
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
    monkeypatch.setattr(smtplib, "SMTP", Boom)
    r = c.post("/api/me/verify/resend").get_json()
    assert not r["ok"] and "app password" in r["error"]
