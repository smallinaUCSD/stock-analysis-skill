"""Sign-in history: each sign-in is recorded with method, place and device;
people can see and end their sessions; the admin sees who signed in, when,
from where and for how long. The location database is faked (no download)."""

import pytest

from stockskill import geoip

CHROME_MAC = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
SAFARI_IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
                 "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")


class FakeReader:
    def get(self, ip):
        return {"city": {"names": {"en": "Austin"}}, "subdivisions": [{"names": {"en": "Texas"}}],
                "country": {"iso_code": "US", "names": {"en": "United States"}}} if ip == "8.8.8.8" else None


def test_lookup_and_label(monkeypatch):
    geoip.lookup.cache_clear()
    monkeypatch.setattr(geoip, "_reader", lambda: FakeReader())
    assert geoip.lookup("8.8.8.8") == {"city": "Austin", "region": "Texas", "country": "United States", "cc": "US"}
    assert geoip.lookup("127.0.0.1") == {} and geoip.lookup("100.101.1.2") == {} and geoip.lookup("nope") == {}
    assert geoip.label({"city": "Singapore", "region": "Singapore", "country": "Singapore"}) == "Singapore"
    assert geoip.label({}) == ""
    geoip.lookup.cache_clear()


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_AUTH", "1")
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    tk = tmp_path / "t.csv"
    tk.write_text("[M7]\nAAPL, MSFT\n")
    from stockskill.accounts import auth, groups
    groups._CACHE["groups"] = None
    auth._HITS.clear()
    auth._SEEN.clear()
    geoip.lookup.cache_clear()
    monkeypatch.setattr(geoip, "_reader", lambda: FakeReader())
    from stockskill.server import create_app
    a = create_app(tickers_path=str(tk), public=True)
    a.config["ACCT"]["board"] = None
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


def test_sign_in_is_recorded_with_place_and_device(app):
    c = _client(app)
    _setup(c)
    s = c.get("/api/me/sessions").get_json()["sessions"]
    assert len(s) == 1 and s[0]["this"] and s[0]["active"]
    assert s[0]["where"] == "Austin, Texas, United States" and s[0]["browser"] == "Chrome" and s[0]["os"] == "macOS"
    assert s[0]["method"] == "password (new account)"


def test_sign_out_other_devices_and_failed_attempts(app):
    from stockskill.accounts import db
    a = _client(app)
    _setup(a)
    b = _client(app, SAFARI_IPHONE, "1.1.1.1")
    assert _login(b, "wrong-password-123").status_code == 401
    assert _login(b).get_json()["ok"]
    assert b.get("/api/me").status_code == 200
    mine = a.get("/api/me/sessions").get_json()["sessions"]
    phone = next(x for x in mine if not x["this"])
    assert phone["os"] == "iOS" and phone["where"] == "Unknown location" and phone["method"] == "password"
    assert a.post("/api/me/sessions/revoke", json={"id": next(x for x in mine if x["this"])["id"]}).status_code == 400
    assert a.post("/api/me/sessions/revoke", json={"id": phone["id"]}).get_json()["signed_out"] == 1
    assert b.get("/api/me").status_code == 401                      # the phone is signed out
    assert a.get("/api/me").status_code == 200
    with db.conn() as cx:
        f = cx.execute("SELECT reason, ip FROM login_failures").fetchall()
    assert [tuple(r) for r in f] == [("wrong password", "1.1.1.1")]


def test_password_change_and_logout_end_sessions(app):
    a = _client(app)
    _setup(a)
    b = _client(app, SAFARI_IPHONE)
    _login(b)
    assert a.post("/api/me/password", json={"current": "a-long-password-1",
                                            "password": "another-long-pass-2"}).get_json()["signed_out"] == 1
    assert b.get("/api/me").status_code == 401
    a.get("/logout")
    b2 = _client(app)
    _login(b2, "another-long-pass-2")
    s = b2.get("/api/me/sessions").get_json()["sessions"]
    assert sum(1 for x in s if x["active"]) == 1 and any(not x["active"] for x in s)


def test_older_cookies_get_a_session_record(app):
    from stockskill.accounts import db
    c = _client(app)
    _setup(c)
    with c.session_transaction() as sess:
        sess.pop("sid")
    assert c.get("/api/me").status_code == 200
    with c.session_transaction() as sess:
        assert sess.get("sid")
    assert db.get_session(sess["sid"])["method"] == "earlier sign-in"


def test_admin_sees_sign_ins_and_time_on_site(app, monkeypatch):
    c = _client(app)
    _setup(c)
    monkeypatch.setenv("STOCKSKILL_ADMINS", "a@example.com")
    c.get("/account")
    app.config["OBS"].flush()
    r = c.get("/api/admin/report?days=7").get_json()
    si = r["signins"][0]
    assert si["email"] == "a@example.com" and si["city"] == "Austin" and si["ip"] == "8.8.8.8" and si["browser"] == "Chrome"
    p = r["people"][0]
    assert p["name"] == "Ada L" and p["signins"] == 1 and p["active"] == 1 and p["last_place"] == "Austin, United States"
    assert p["minutes_7d"] >= 0 and "DB-IP" in r["geo_attr"]


def test_time_on_site_counts_visits():
    import sqlite3
    from stockskill.observability import time_on_site
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE hits (uid INTEGER, ts REAL)")
    c.executemany("INSERT INTO hits VALUES (?,?)", [(1, 1000), (1, 1300), (1, 1600), (1, 9000), (2, 5000)])
    assert time_on_site(c, 0) == {1: 30 + 300 + 300 + 30, 2: 30}
