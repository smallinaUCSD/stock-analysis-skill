"""Where sign-ups come from: campaign tags / referring sites -> a first-party
cookie -> saved on the new account -> the admin report."""

import pytest

from stockskill.accounts import attribution as A


def test_source_names_and_touches():
    assert A.source_for_host("www.linkedin.com") == "linkedin"
    assert A.source_for_host("lnkd.in") == "linkedin"
    assert A.source_for_host("t.co") == "x"
    assert A.source_for_host("l.instagram.com") == "instagram"
    assert A.source_for_host("www.google.co.uk") == "google"
    assert A.source_for_host("news.ycombinator.com") == "hackernews"
    assert A.source_for_host("blog.example.org") == "blog.example.org"

    t = A.touch({"utm_source": "LinkedIn", "utm_medium": "social", "utm_campaign": "beta_launch<script>"},
                "", "smi.example", "/")
    assert t == {"s": "linkedin", "m": "social", "c": "beta_launchscript", "r": None, "l": "/", "u": 1}
    t = A.touch({}, "https://www.reddit.com/r/stocks/", "smi.example", "/")
    assert t["s"] == "reddit" and t["m"] == "social" and t["r"] == "www.reddit.com"
    assert A.touch({}, "https://smi.example/calendar", "smi.example", "/") is None      # our own pages
    assert A.touch({}, "", "smi.example", "/") is None


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_AUTH", "1")
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    monkeypatch.setenv("STOCKSKILL_ADMINS", "boss@example.com")
    monkeypatch.setenv("STOCKSKILL_ANALYTICS_DB", str(tmp_path / "analytics.db"))
    tk = tmp_path / "t.csv"
    tk.write_text("[M7]\nAAPL\n")
    from stockskill.server import create_app
    app = create_app(tickers_path=str(tk), public=True)
    app.config["ACCT"]["board"] = None
    return app.test_client()


def _cookie(c):
    ck = c.get_cookie(A.COOKIE)
    return A.read(ck.value) if ck else None


def test_campaign_link_to_signup_to_admin(client):
    client.get("/?utm_source=linkedin&utm_medium=social&utm_campaign=beta_launch")
    assert _cookie(client)["s"] == "linkedin"
    client.get("/signup", headers={"Referer": "https://www.reddit.com/"})       # a later referral doesn't overwrite it
    assert _cookie(client)["s"] == "linkedin"
    r = client.post("/auth/signup", json={"email": "ana@example.com", "password": "a-long-password-1", "accept": True})
    assert r.status_code == 200
    from stockskill.accounts import db
    u = db.by_email("ana@example.com")
    assert (u["src_source"], u["src_medium"], u["src_campaign"], u["src_landing"]) == ("linkedin", "social", "beta_launch", "/")

    boss = client.application.test_client()
    boss.post("/auth/signup", json={"email": "boss@example.com", "password": "a-long-password-2", "accept": True})
    db.update_user(db.by_email("boss@example.com")["id"], email_verified=1, onboarded=1)
    rows = boss.get("/api/admin/report").get_json().get("signup_sources") or []
    li = [r for r in rows if r["source"] == "linkedin"]
    assert li and li[0]["signups"] == 1 and li[0]["campaign"] == "beta_launch"


def test_newer_campaign_wins_and_direct_default(client):
    client.get("/")
    assert _cookie(client)["s"] == "direct"
    client.get("/?utm_source=x&utm_campaign=launch_b")
    assert _cookie(client)["s"] == "x" and _cookie(client)["c"] == "launch_b"
