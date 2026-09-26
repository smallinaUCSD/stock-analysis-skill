"""Several devices and unusual sign-ins: what counts as unusual, the alert
and its "wasn't you?" link, idle expiry, the device cap, and keeping open
pages on other devices in step. No network; places come from a fake database."""

import time

import pytest

from stockskill import geoip
from stockskill.accounts import risk

CHROME_MAC = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
SAFARI_IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
                 "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
PLACES = {"8.8.8.8": ("Austin", "Texas", "US", "United States", 30.27, -97.74),
          "8.8.4.4": ("Dallas", "Texas", "US", "United States", 32.78, -96.80),
          "5.5.5.5": ("Moscow", "Moscow", "RU", "Russia", 55.75, 37.62)}


class FakeReader:
    def get(self, ip):
        p = PLACES.get(ip)
        if not p:
            return None
        return {"city": {"names": {"en": p[0]}}, "subdivisions": [{"names": {"en": p[1]}}],
                "country": {"iso_code": p[2], "names": {"en": p[3]}}, "location": {"latitude": p[4], "longitude": p[5]}}


# --- the rules ------------------------------------------------------------------

H = [{"cc": "US", "browser": "Chrome", "os": "macOS", "device": "desktop", "ip": "8.8.8.8", "last_seen": 1000.0}]
WHERE = {"8.8.8.8": {"lat": 30.27, "lon": -97.74}}.get


def test_nothing_to_compare_with_means_no_flags():
    assert risk.assess({"cc": "RU", "browser": "Safari", "os": "iOS", "device": "mobile", "ts": 2000}, []) == []


def test_same_place_and_device_is_fine():
    new = {"cc": "US", "browser": "Chrome", "os": "macOS", "device": "desktop", "lat": 32.78, "lon": -96.8, "ts": 1000 + 3600}
    assert risk.assess(new, H, 0, WHERE) == []                      # Austin -> Dallas in an hour: 300 km, fine


def test_each_reason():
    far = {"cc": "RU", "browser": "Safari", "os": "iOS", "device": "mobile", "lat": 55.75, "lon": 37.62, "ts": 1000 + 3600}
    assert risk.assess(far, H, 6, WHERE) == ["failed attempts", "impossible travel", "new country", "new device"]
    later = dict(far, ts=1000 + 30 * 3600)                          # 30 hours later: a flight is possible
    assert risk.assess(later, H, 0, WHERE) == ["new country", "new device"]
    unknown = {"browser": "Chrome", "os": "macOS", "device": "desktop", "ts": 5000}     # no place: not compared
    assert risk.assess(unknown, H, 0, WHERE) == []
    assert "browser and device" in risk.explain(["new device"]) and " and " in risk.explain(["new country", "new device"])


# --- the app --------------------------------------------------------------------

@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_AUTH", "1")
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    monkeypatch.setenv("STOCKSKILL_PUBLIC_URL", "https://site.test")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    tk = tmp_path / "t.csv"
    tk.write_text("[M7]\nAAPL, MSFT\n")
    from stockskill.accounts import auth, groups, notify
    groups._CACHE["groups"] = None
    auth._HITS.clear()
    auth._SEEN.clear()
    geoip.lookup.cache_clear()
    monkeypatch.setattr(geoip, "_reader", lambda: FakeReader())
    mails = []
    monkeypatch.setattr(notify, "send_email", lambda to, subj, text, h=None, unsubscribe=None: mails.append((to, subj, text)) or True)
    from stockskill.server import create_app
    a = create_app(tickers_path=str(tk), public=True)
    a.config["ACCT"]["board"] = None
    a.mails = mails
    yield a
    groups._CACHE["groups"] = None
    geoip.lookup.cache_clear()


def _client(app, ua=CHROME_MAC, ip="8.8.8.8"):
    c = app.test_client()
    c.environ_base.update({"REMOTE_ADDR": ip, "HTTP_USER_AGENT": ua})
    return c


def _setup(c):
    c.post("/auth/signup", json={"email": "a@example.com", "password": "a-long-password-1", "accept": True})
    c.post("/api/me/groups", json={"groups": ["mag7"]})
    c.post("/api/me/profile", json={"first_name": "Ada", "last_name": "L", "dob": "1990-01-01",
                                    "investor_type": "etf", "experience": "beginner"})
    c.post("/api/me/onboarded")


def _login(c, pw="a-long-password-1"):
    return c.post("/auth/login", json={"email": "a@example.com", "password": pw})


def _wait(pred, s=2.0):
    end = time.time() + s
    while time.time() < end and not pred():
        time.sleep(0.02)
    return pred()


def test_familiar_sign_in_sends_no_alert(app):
    _setup(_client(app))
    b = _client(app, ip="8.8.4.4")                                   # same laptop and browser, nearby city
    assert _login(b).get_json()["ok"]
    time.sleep(0.2)
    assert not any("sign-in" in m[1].lower() for m in app.mails)
    assert all(not x["unusual"] for x in b.get("/api/me/sessions").get_json()["sessions"])


def test_unusual_sign_in_alerts_and_not_me_signs_out_everywhere(app):
    from stockskill.accounts import db
    a = _client(app)
    _setup(a)
    b = _client(app, SAFARI_IPHONE, "5.5.5.5")
    assert _login(b).get_json()["ok"]
    assert _wait(lambda: any(m[1] == "Unusual sign-in to your account" for m in app.mails))
    mail = next(m for m in app.mails if m[1] == "Unusual sign-in to your account")
    assert "Moscow, Russia" in mail[2] and "Safari on iOS" in mail[2] and "5.5.5.5" in mail[2]
    assert "impossible travel" not in mail[2] and "too far from your last sign-in" in mail[2]
    s = a.get("/api/me/sessions").get_json()["sessions"]
    phone = next(x for x in s if not x["this"])
    assert phone["unusual"] == ["impossible travel", "new country", "new device"]
    inbox = a.get("/api/me/notifications").get_json()["items"]
    assert inbox[0]["kind"] == "security" and "Moscow" in inbox[0]["body"]
    link = next(x for x in mail[2].split() if "/security/not-me?t=" in x)
    tok = link.split("t=", 1)[1].strip()
    anon = app.test_client()
    assert anon.get("/security/not-me?t=nope").status_code == 400
    page = anon.get("/security/not-me?t=" + tok)
    assert page.status_code == 200 and b"Sign out everywhere" in page.data
    r = anon.post("/security/not-me", json={"t": tok}).get_json()
    assert r["ok"] and r["signed_out"] == 2 and r["password"]
    assert a.get("/api/me").status_code == 401 and b.get("/api/me").status_code == 401
    assert _wait(lambda: any(m[1] == "Reset your password" for m in app.mails))
    with db.conn() as cx:
        assert cx.execute("SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL").fetchone()[0] == 0


def test_many_failures_then_success_is_flagged(app):
    _setup(_client(app))
    b = _client(app)
    for _ in range(5):
        _login(b, "wrong-password-123")
    from stockskill.accounts import auth
    auth._HITS.clear()                                               # past the rate limit
    assert _login(b).get_json()["ok"]
    s = b.get("/api/me/sessions").get_json()["sessions"]
    assert next(x for x in s if x["this"])["unusual"] == ["failed attempts"]


def test_idle_sessions_expire_and_devices_are_capped(app, monkeypatch):
    from stockskill.accounts import auth, db
    a = _client(app)
    _setup(a)
    with a.session_transaction() as sess:
        sid = sess["sid"]
    with db.conn() as cx:
        cx.execute("UPDATE sessions SET last_seen=? WHERE id=?", (time.time() - 31 * 86400, sid))
    auth._SEEN.clear()
    assert a.get("/api/me").status_code == 401
    monkeypatch.setattr(db, "MAX_ACTIVE_SESSIONS", 3)
    monkeypatch.setattr(db.cap_sessions, "__defaults__", (3,))
    cs = [_client(app) for _ in range(4)]
    for c in cs:
        _login(c)
        time.sleep(0.01)
    auth._SEEN.clear()
    assert cs[0].get("/api/me").status_code == 401                  # the oldest was signed out
    assert all(c.get("/api/me").status_code == 200 for c in cs[1:])


def test_sync_reports_changes_from_other_devices(app):
    a = _client(app)
    _setup(a)
    b = _client(app)
    _login(b)
    b.post("/api/me/watchlist", json={"add": ["NVDA"]})
    b.post("/api/me/theme", json={"theme": "dark"})
    d = a.get("/api/me/sync").get_json()
    assert "NVDA" in d["tickers"] and d["theme"] == "dark" and isinstance(d["unread"], int)
