"""Accounts: sign-up/in, the sign-in gate, onboarding, per-user watchlists,
Google token checks, account deletion. No network."""

from datetime import date

import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_AUTH", "1")
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("STOCKSKILL_PUBLIC_URL", raising=False)
    tk = tmp_path / "t.csv"
    tk.write_text("[M7]\nAAPL, MSFT, NVDA\n\n[SEMIS]\nAMD, MU\n")
    from stockskill.accounts import auth, groups
    groups._CACHE["groups"] = None
    auth._HITS.clear()
    from stockskill.server import create_app
    a = create_app(tickers_path=str(tk), public=True)
    a.config["ACCT"]["board"] = None               # don't start background board adds
    yield a
    groups._CACHE["groups"] = None


def _signup(c, email="a@example.com", pw="a-long-password-1", accept=True):
    return c.post("/auth/signup", json={"email": email, "password": pw, "accept": accept})


PROFILE = {"first_name": "Ada", "last_name": "Lovelace", "dob": "1990-12-10", "investor_type": "etf",
           "experience": "intermediate", "gender": "na", "referral": None}


def test_signed_out_visitors_see_landing_and_are_gated(app):
    c = app.test_client()
    home = c.get("/")
    assert home.status_code == 200 and b"Research stocks the way professionals do" in home.data
    for p in ("/login", "/signup", "/terms", "/privacy", "/healthz"):
        assert c.get(p).status_code == 200, p
    r = c.get("/analysis/NVDA")
    assert r.status_code == 302 and "/login?next=/analysis/NVDA" in r.headers["Location"]
    assert c.get("/api/screener").status_code == 401


def test_signup_validation_and_duplicate(app):
    c = app.test_client()
    assert _signup(c, email="nope").status_code == 400
    assert _signup(c, pw="short").status_code == 400
    assert _signup(c, pw="aaaaaaaaaaaa").status_code == 400          # too few distinct characters
    assert _signup(c, accept=False).status_code == 400
    r = _signup(c)
    assert r.status_code == 200 and r.get_json()["next"] == "/welcome"
    c2 = app.test_client()
    assert _signup(c2).status_code == 409


def test_onboarding_flow_builds_the_watchlist(app):
    c = app.test_client()
    _signup(c)
    assert c.get("/screener").headers["Location"].endswith("/welcome")   # must finish setup first
    assert c.post("/api/me/onboarded").status_code == 400
    groups = c.get("/api/groups").get_json()["groups"]
    assert {g["key"] for g in groups} >= {"mag7", "dow30", "semis"}
    assert c.post("/api/me/groups", json={"groups": ["bogus"]}).status_code == 400
    r = c.post("/api/me/groups", json={"groups": ["mag7", "semis"]}).get_json()
    assert r["ok"] and r["count"] == 5
    kid = dict(PROFILE, dob=date(date.today().year - 16, 1, 1).isoformat())
    assert "18 or older" in c.post("/api/me/profile", json=kid).get_json()["error"]
    assert c.post("/api/me/profile", json=dict(PROFILE, investor_type="x")).status_code == 400
    assert c.post("/api/me/profile", json=PROFILE).get_json()["ok"]
    assert c.post("/api/me/onboarded").get_json()["ok"]
    me = c.get("/api/me").get_json()
    assert me["watchlist"] == ["AAPL", "MSFT", "NVDA", "AMD", "MU"]
    assert me["user"]["first_name"] == "Ada" and me["user"]["groups"] == ["mag7", "semis"]
    assert [p[0] for p in me["options"]["experience"]] == ["beginner", "intermediate", "advanced"]
    assert "password_hash" not in me["user"]


def test_login_logout_and_safe_redirect(app):
    c = app.test_client()
    _signup(c)
    c.post("/api/me/groups", json={"groups": ["mag7"]})
    c.post("/api/me/profile", json=PROFILE)
    c.post("/api/me/onboarded")
    c.get("/logout")
    assert c.get("/account").status_code == 302
    bad = c.post("/auth/login", json={"email": "a@example.com", "password": "wrong-password"})
    assert bad.status_code == 401 and "incorrect" in bad.get_json()["error"]
    ok = c.post("/auth/login", json={"email": "A@Example.com", "password": "a-long-password-1", "next": "//evil.com"})
    assert ok.get_json()["next"] == "/"                                   # no open redirect
    ok = c.post("/auth/login", json={"email": "a@example.com", "password": "a-long-password-1", "next": "/screener"})
    assert ok.get_json()["next"] == "/screener"
    assert c.get("/account").status_code == 200


def test_login_rate_limit(app):
    c = app.test_client()
    for _ in range(8):
        c.post("/auth/login", json={"email": "x@example.com", "password": "nope-nope-nope"})
    assert c.post("/auth/login", json={"email": "x@example.com", "password": "nope-nope-nope"}).status_code == 429


def test_cross_site_posts_are_blocked(app):
    c = app.test_client()
    r = c.post("/auth/signup", json={"email": "b@example.com", "password": "a-long-password-1", "accept": True},
               headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_board_is_personalised(app, monkeypatch):
    from stockskill.server.watchlist_service import WatchlistService
    monkeypatch.setattr(WatchlistService, "html", lambda self, force=False: "<html><body><div class='bar'></div></body></html>")
    c = app.test_client()
    _signup(c)
    c.post("/api/me/groups", json={"groups": ["semis"]})
    c.post("/api/me/profile", json=PROFILE)
    c.post("/api/me/onboarded")
    page = c.get("/").get_data(as_text=True)
    assert 'new Set(["AMD", "MU"])' in page and "Ada's watchlist" in page and "/logout" in page


def test_watchlist_edit_and_account_deletion(app):
    c = app.test_client()
    _signup(c)
    c.post("/api/me/groups", json={"groups": ["mag7"]})
    r = c.post("/api/me/watchlist", json={"add": ["net", "bad ticker!"], "remove": ["MSFT"]}).get_json()
    assert r["watchlist"] == ["AAPL", "NVDA", "NET"]
    assert c.post("/api/me/delete", json={"confirm": "nope"}).status_code == 400
    assert c.post("/api/me/delete", json={"confirm": "delete"}).get_json()["ok"]
    assert c.get("/api/me").status_code == 401
    from stockskill.accounts import db
    assert db.by_email("a@example.com") is None


def test_google_token_checks(monkeypatch):
    from stockskill.accounts import auth
    import requests

    class R:
        def __init__(self, j, code=200):
            self._j, self.status_code = j, code

        def json(self):
            return self._j
    good = {"aud": "cid", "iss": "https://accounts.google.com", "exp": "9999999999", "email_verified": "true",
            "sub": "123", "email": "g@example.com"}
    monkeypatch.setattr(requests, "get", lambda *a, **k: R(good))
    assert auth.verify_google_token("t", "cid")["sub"] == "123"
    for bad in ({"aud": "other"}, {"iss": "evil.com"}, {"exp": "1"}, {"email_verified": "false"}):
        monkeypatch.setattr(requests, "get", lambda *a, _b=bad, **k: R(dict(good, **_b)))
        assert auth.verify_google_token("t", "cid") is None


def test_google_sign_in_creates_then_links(app, monkeypatch):
    from stockskill.accounts import auth, db
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    claims = {"sub": "g-1", "email": "a@example.com", "given_name": "Ada", "family_name": "L"}
    monkeypatch.setattr(auth, "verify_google_token", lambda t, cid: claims)
    c = app.test_client()
    _signup(c)                                            # an email account already exists
    c.get("/logout")
    r = c.post("/auth/google", json={"credential": "x"}).get_json()
    assert r["ok"] and db.by_email("a@example.com")["google_sub"] == "g-1"
    claims = {"sub": "g-2", "email": "new@example.com", "given_name": "New", "family_name": "User"}
    c2 = app.test_client()
    c2.post("/auth/google", json={"credential": "x"})
    me = c2.get("/api/me").get_json()["user"]
    assert me["first_name"] == "New" and me["needs_terms"] is True      # Terms accepted on the first screen
    assert c2.post("/api/me/terms", json={"accept": True}).get_json()["ok"]
    assert c2.get("/api/me").get_json()["user"]["needs_terms"] is False


def test_passkey_options_need_sign_in(app):
    c = app.test_client()
    assert c.post("/auth/passkey/register/options").status_code == 401
    _signup(c)
    o = c.post("/auth/passkey/register/options").get_json()
    assert o["rp"]["id"] == "localhost" and o["authenticatorSelection"]["residentKey"] == "required"
    a = c.post("/auth/passkey/login/options").get_json()
    assert a["rpId"] == "localhost" and len(a["challenge"]) > 20
    bad = c.post("/auth/passkey/login/verify", json={"credential": {"id": "nope"}})
    assert bad.status_code == 401
