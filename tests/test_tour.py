"""The first-run walkthrough: shown until finished or skipped, then not again."""

import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_AUTH", "1")
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    tk = tmp_path / "t.csv"
    tk.write_text("[M7]\nAAPL\n")
    from stockskill.server import create_app
    a = create_app(tickers_path=str(tk), public=True)
    a.config["ACCT"]["board"] = None
    return a


def test_tour_until_done(app):
    from stockskill.accounts import db, pages
    c = app.test_client()
    c.post("/auth/signup", json={"email": "t@example.com", "password": "a-long-password-1", "accept": True})
    u = db.by_email("t@example.com")
    db.update_user(u["id"], email_verified=1, onboarded=1)
    html = pages.personalize_board("<html><head></head><body></body></html>", db.get_user(u["id"]), ["AAPL"])
    assert '"tour":true' in html.replace(" ", "") and "window.smiTour=" in html and "Take the tour" in html
    assert c.post("/api/me/tour", json={"done": True}).get_json()["ok"]
    html = pages.personalize_board("<html><head></head><body></body></html>", db.get_user(u["id"]), ["AAPL"])
    assert '"tour":false' in html.replace(" ", "") and "window.smiTour=" in html     # replayable from the menu
