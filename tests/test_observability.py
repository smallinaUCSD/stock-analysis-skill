"""Usage analytics: user-agent classes, the collector, the report, and the
admin-only dashboard. No network; the analytics DB lives in tmp (conftest)."""

import pytest

from stockskill import observability as OBS

CHROME_MAC = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
SAFARI_IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
                 "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")


def test_classify_ua():
    assert OBS.classify_ua(CHROME_MAC) == ("desktop", "Chrome", "macOS")
    assert OBS.classify_ua(SAFARI_IPHONE) == ("mobile", "Safari", "iOS")
    assert OBS.classify_ua("Mozilla/5.0 (Linux; Android 14; Pixel Tablet) Chrome/128.0 Safari/537.36")[0] == "tablet"
    for bot in ("", "curl/8.4", "python-requests/2.31", "Googlebot/2.1"):
        assert OBS.classify_ua(bot) is None, bot


def test_visitor_id_is_daily_and_opaque():
    a = OBS.visitor_id("1.2.3.4", CHROME_MAC, "2026-09-01", "s")
    assert a == OBS.visitor_id("1.2.3.4", CHROME_MAC, "2026-09-01", "s")
    assert a != OBS.visitor_id("1.2.3.4", CHROME_MAC, "2026-09-02", "s")
    assert "1.2.3.4" not in a and len(a) == 16


def test_collector_and_report():
    col = OBS.Collector("secret")
    col.record("/analysis/<ticker>", "/analysis/NVDA", "GET", 200, 120.0, 7, "1.1.1.1", CHROME_MAC,
               "https://news.example.com/x", "NVDA", True)
    col.record("/", "/", "GET", 200, 40.0, None, "2.2.2.2", SAFARI_IPHONE, "", None, True)
    col.record("/api/screener", "/api/screener", "GET", 500, 900.0, 7, "1.1.1.1", CHROME_MAC, "", None, False)
    col.record("/api/quotes", "/api/quotes", "GET", 200, 5.0, 7, "1.1.1.1", CHROME_MAC, "", None, False)  # skipped
    col.record("/", "/", "GET", 200, 5.0, None, "3.3.3.3", "curl/8", "", None, True)                  # bot
    assert col.event("quicklook", "NVDA", 7, "1.1.1.1", CHROME_MAC)
    assert not col.event("bad name!", "", 7, "1.1.1.1", CHROME_MAC)
    col.flush()
    r = OBS.report(7)
    assert r["active_now"] == 2
    assert {d["name"] for d in r["devices"]} == {"desktop", "mobile"}
    assert r["top_stocks"][0]["ticker"] == "NVDA"
    assert any(f["name"] == "quicklook" for f in r["top_features"])
    assert any(x["name"] == "news.example.com" for x in r["referrers"])
    assert r["recent_errors"][0]["path"] == "/api/screener"


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
    from stockskill.server import create_app
    a = create_app(tickers_path=str(tk), public=True)
    a.config["ACCT"]["board"] = None
    yield a
    groups._CACHE["groups"] = None


def test_admin_is_hidden_from_everyone_else(app, monkeypatch):
    c = app.test_client()
    assert c.post("/api/t", json={"name": "landing_signup"}, headers={"User-Agent": CHROME_MAC}).status_code == 204
    assert c.get("/admin").status_code in (302, 404)          # signed out: gated
    c.post("/auth/signup", json={"email": "a@example.com", "password": "a-long-password-1", "accept": True})
    c.post("/api/me/groups", json={"groups": ["mag7"]})
    c.post("/api/me/profile", json={"first_name": "Ada", "last_name": "L", "dob": "1990-01-01", "investor_type": "etf",
                                    "experience": "beginner", "gender": "na", "referral": None})
    c.post("/api/me/onboarded")
    assert c.get("/admin").status_code == 404
    assert c.get("/api/admin/report").status_code == 404
    monkeypatch.setenv("STOCKSKILL_ADMINS", "someone@example.com, A@example.com")
    assert c.get("/admin").status_code == 200
    r = c.get("/api/admin/report?days=7").get_json()
    assert r["ok"] and r["accounts"] == 1 and "health" in r and "retention" in r
