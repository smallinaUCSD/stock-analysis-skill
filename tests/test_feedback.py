"""The Feedback button and the "Was this brief useful?" links."""

import re

import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_AUTH", "1")
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    monkeypatch.setenv("STOCKSKILL_ADMINS", "boss@example.com")
    monkeypatch.setenv("STOCKSKILL_ANALYTICS_DB", str(tmp_path / "analytics.db"))
    monkeypatch.setenv("STOCKSKILL_PUBLIC_URL", "https://smi.example")
    tk = tmp_path / "t.csv"
    tk.write_text("[M7]\nAAPL\n")
    from stockskill.server import create_app
    a = create_app(tickers_path=str(tk), public=True)
    a.config["ACCT"]["board"] = None
    return a


def _user(app, email):
    from stockskill.accounts import db
    c = app.test_client()
    c.post("/auth/signup", json={"email": email, "password": "a-long-password-1", "accept": True})
    db.update_user(db.by_email(email)["id"], email_verified=1, onboarded=1, first_name="Ana")
    return c, db.by_email(email)


def test_widget_only_for_signed_in_pages(app):
    anon = app.test_client()
    assert b'id="smi-fb"' not in anon.get("/").data                      # landing, signed out
    c, _ = _user(app, "ana@example.com")
    assert c.get("/calendar").data.count(b'id="smi-fb"') == 1
    assert b'id="smi-fb"' not in c.get("/terms").data


def test_send_and_triage_feedback(app, monkeypatch):
    from stockskill.accounts import feedback as FB, db
    sent = []
    monkeypatch.setattr(FB, "_email_admins", lambda *a: sent.append(a))
    c, u = _user(app, "ana@example.com")
    assert c.post("/api/feedback", json={"message": " "}).status_code == 400
    assert c.post("/api/feedback", json={"message": "x" * 2001}).status_code == 400
    r = c.post("/api/feedback", json={"message": "The calendar needs a week view", "page": "/calendar?t=secret",
                                      "viewport": "1440x900"}, headers={"User-Agent": "TestBrowser/1"})
    assert r.status_code == 200 and r.get_json()["ok"]
    row = db.feedback_list()[0]
    assert (row["message"], row["page"], row["viewport"], row["ua"], row["status"], row["email"]) == \
        ("The calendar needs a week view", "/calendar", "1440x900", "TestBrowser/1", "new", "ana@example.com")
    assert c.get("/api/admin/feedback").status_code == 404                # not an admin
    boss, _ = _user(app, "boss@example.com")
    d = boss.get("/api/admin/feedback").get_json()
    assert d["ok"] and d["feedback"][0]["id"] == row["id"]
    assert boss.post(f"/api/admin/feedback/{row['id']}", json={"status": "shipped", "note": "Week view added"}).get_json()["ok"]
    assert db.feedback_list()[0]["status"] == "shipped"
    assert boss.post(f"/api/admin/feedback/{row['id']}", json={"status": "bogus"}).status_code == 400
    db.delete_user(u["id"])                                              # the message stays, without the account
    assert db.feedback_list()[0]["email"] is None


def test_brief_rating_links(app, monkeypatch):
    from stockskill.accounts import db, notify
    _, u = _user(app, "ana@example.com")
    u = {**db.get_user(u["id"]), "notify_email": 1, "email_verified": 1}
    out = {}
    monkeypatch.setattr(notify, "send_email", lambda to, subj, text, htm, **k: out.update(text=text, html=htm) or True)
    notify.deliver(u, "summary", "Before the bell", ["Markets were quiet."], "/", "sum:2026-09-30:pre")
    assert "Was this brief useful?" in out["html"] and "Was this brief useful? Yes:" in out["text"]
    yes = re.search(r"Yes: (\S+)", out["text"]).group(1)
    path = yes.replace("https://smi.example", "")
    anon = app.test_client()                                             # clicked from an inbox, maybe signed out
    page = anon.get(path)
    assert page.status_code == 200 and b"Thanks for the feedback" in page.data
    assert db.brief_rating_stats()["yes"] == 0                           # a link scanner's GET doesn't vote
    q = dict(p.split("=", 1) for p in path.split("?", 1)[1].split("&"))
    from urllib.parse import unquote
    body = {"k": unquote(q["k"]), "t": q["t"], "v": "yes"}
    assert anon.post("/api/brief/rate", json=body).get_json()["ok"]
    assert anon.post("/api/brief/rate", json={**body, "comment": "More on my sectors"}).get_json()["ok"]
    s = db.brief_rating_stats()
    assert (s["yes"], s["no"]) == (1, 0) and s["comments"][0]["comment"] == "More on my sectors"
    assert s["by_brief"][0]["brief"] == "Before the bell"
    assert anon.post("/api/brief/rate", json={**body, "t": body["t"] + "x"}).status_code == 400   # forged
    assert anon.post("/api/brief/rate", json={**body, "k": "sum:2026-10-01:pre"}).status_code == 400  # other brief
    assert anon.get(path.replace("v=yes", "v=maybe")).status_code == 400
    notify.deliver(u, "event", "Big move", ["NVDA -5%"], "/", "ev:1")
    assert "Was this brief useful?" not in out["html"]                   # only the briefs ask
