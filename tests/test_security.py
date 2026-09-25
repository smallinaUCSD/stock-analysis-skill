"""2-step verification, backup codes, password reset, email change, and the
welcome / security emails."""

import re
import time

import pytest

from stockskill.accounts import security as S

RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"      # base32 of "12345678901234567890" (RFC 6238)


def test_totp_matches_rfc_vectors():
    assert S.totp(RFC_SECRET, 59) == "287082"
    assert S.totp(RFC_SECRET, 1111111109) == "081804"
    assert S.totp(RFC_SECRET, 2000000000) == "279037"
    assert S.check_totp(RFC_SECRET, "287082", at=59 + 30) is not None     # one step of drift is fine
    assert S.check_totp(RFC_SECRET, "287082", at=59 + 120) is None
    assert S.check_totp(RFC_SECRET, "12345", at=59) is None


def test_recovery_codes_work_once(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "u.db"))
    from stockskill.accounts import db
    db.init()
    uid = db.create_user("x@example.com")
    codes, stored = S.new_recovery_codes(3)
    db.update_user(uid, mfa_recovery=stored)
    assert re.fullmatch(r"[a-z2-7]{4}-[a-z2-7]{4}", codes[0])
    assert S.use_recovery_code(db.get_user(uid), codes[1].replace("-", "").upper())
    assert not S.use_recovery_code(db.get_user(uid), codes[1])
    assert S.use_recovery_code(db.get_user(uid), codes[0])


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_AUTH", "1")
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    monkeypatch.setenv("STOCKSKILL_PUBLIC_URL", "https://site.test")
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_USER", "sender@test")
    monkeypatch.setenv("SMTP_PASSWORD", "x")
    tk = tmp_path / "t.csv"
    tk.write_text("[M7]\nAAPL\n")
    from stockskill.accounts import auth, groups
    groups._CACHE["groups"] = None
    auth._HITS.clear()
    S._CODES.clear()
    S._USED_STEPS.clear()
    from stockskill.server import create_app
    a = create_app(tickers_path=str(tk), public=True)
    a.config["ACCT"]["board"] = None
    yield a
    groups._CACHE["groups"] = None


@pytest.fixture
def outbox(monkeypatch):
    from stockskill.accounts import notify
    sent = []
    monkeypatch.setattr(notify, "send_simple", lambda to, subject, lines, url=None, label="": sent.append(
        {"to": to, "subject": subject, "text": " ".join(lines)}) or True)
    monkeypatch.setattr(notify, "send_email", lambda to, subject, text, h=None, unsubscribe=None: sent.append(
        {"to": to, "subject": subject, "text": text}) or True)

    class Now:                                   # run "background" sends inline
        def __init__(self, target, args=(), daemon=None):
            self.t, self.a = target, args

        def start(self):
            self.t(*self.a)
    monkeypatch.setattr(S.threading, "Thread", Now)
    return sent


def _signup(c, email="a@example.com", pw="a-long-password-1"):
    return c.post("/auth/signup", json={"email": email, "password": pw, "accept": True})


def _link(text, path):
    return re.search(re.escape(path) + r"\?t=([\w.\-]+)", text).group(1)


def test_welcome_email_with_confirm_link(app, outbox):
    c = app.test_client()
    _signup(c)
    mail = outbox[-1]
    assert mail["to"] == "a@example.com" and mail["subject"] == "Welcome to SMI Research"
    tok = _link(mail["text"], "/notifications/verify")
    assert c.get("/notifications/verify?t=" + tok).status_code == 200
    from stockskill.accounts import db
    assert db.by_email("a@example.com")["email_verified"] == 1


def test_authenticator_sign_in(app, outbox):
    c = app.test_client()
    _signup(c)
    start = c.post("/api/me/mfa/totp/start").get_json()
    assert start["qr"].startswith("<svg") and start["uri"].startswith("otpauth://totp/")
    assert c.post("/api/me/mfa/confirm", json={"method": "totp", "code": "000000"}).status_code == 400
    ok = c.post("/api/me/mfa/confirm", json={"method": "totp", "code": S.totp(start["secret"])}).get_json()
    assert ok["ok"] and len(ok["recovery_codes"]) == 10
    assert outbox[-1]["subject"] == "2-step verification is on"
    c.get("/logout")
    r = c.post("/auth/login", json={"email": "a@example.com", "password": "a-long-password-1"}).get_json()
    assert r["ok"] is False and r["mfa"] == "totp"
    assert c.get("/api/me").status_code == 401                          # not signed in yet
    assert c.post("/auth/mfa", json={"code": "111111"}).status_code == 401
    assert c.post("/auth/mfa", json={"code": ok["recovery_codes"][0]}).get_json()["ok"]
    assert c.get("/api/me").get_json()["user"]["recovery_left"] == 9


def test_authenticator_code_cannot_be_replayed(app, outbox):
    c = app.test_client()
    _signup(c)
    start = c.post("/api/me/mfa/totp/start").get_json()
    c.post("/api/me/mfa/confirm", json={"method": "totp", "code": S.totp(start["secret"])})
    for expect in (True, False):
        c.get("/logout")
        c.post("/auth/login", json={"email": "a@example.com", "password": "a-long-password-1"})
        r = c.post("/auth/mfa", json={"code": S.totp(start["secret"])}).get_json()
        assert r["ok"] is expect


def test_emailed_code_sign_in_and_turning_off(app, outbox):
    c = app.test_client()
    _signup(c)
    assert c.post("/api/me/mfa/email/start").get_json()["ok"]
    code = re.search(r"\b(\d{6})\b", outbox[-1]["subject"]).group(1)
    assert c.post("/api/me/mfa/confirm", json={"method": "email", "code": code}).get_json()["ok"]
    c.get("/logout")
    r = c.post("/auth/login", json={"email": "a@example.com", "password": "a-long-password-1"}).get_json()
    assert r["mfa"] == "email" and r["email_hint"] == "a•@example.com"
    code = re.search(r"\b(\d{6})\b", outbox[-1]["subject"]).group(1)
    assert c.post("/auth/mfa", json={"code": code}).get_json()["ok"]
    assert c.post("/api/me/mfa/disable", json={"password": "wrong-password"}).status_code == 400
    assert c.post("/api/me/mfa/disable", json={"password": "a-long-password-1"}).get_json()["ok"]
    assert outbox[-1]["subject"] == "2-step verification is off"


def test_forgot_and_reset_password(app, outbox):
    c = app.test_client()
    _signup(c)
    c.get("/logout")
    n = len(outbox)
    assert c.post("/auth/forgot", json={"email": "nobody@example.com"}).get_json()["ok"]    # same answer
    assert len(outbox) == n
    c.post("/auth/forgot", json={"email": "a@example.com"})
    tok = _link(outbox[-1]["text"], "/reset")
    assert c.get("/reset?t=" + tok).status_code == 200
    assert c.post("/auth/reset", json={"token": tok, "password": "short"}).status_code == 400
    assert c.post("/auth/reset", json={"token": tok, "password": "brand-new-password-2"}).get_json()["ok"]
    assert outbox[-1]["subject"] == "Your password was changed"
    assert c.post("/auth/reset", json={"token": tok, "password": "another-password-33"}).status_code == 400   # used
    assert c.post("/auth/login", json={"email": "a@example.com", "password": "brand-new-password-2"}).get_json()["ok"]


def test_change_email(app, outbox):
    from stockskill.accounts import db
    c = app.test_client()
    _signup(c)
    _signup(app.test_client(), email="taken@example.com")
    assert c.post("/api/me/email", json={"email": "taken@example.com", "password": "a-long-password-1"}).status_code == 409
    assert c.post("/api/me/email", json={"email": "new@example.com", "password": "nope"}).status_code == 400
    assert c.post("/api/me/email", json={"email": "new@example.com", "password": "a-long-password-1"}).get_json()["ok"]
    mail = outbox[-1]
    assert mail["to"] == "new@example.com"
    tok = _link(mail["text"], "/account/email/confirm")
    assert app.test_client().get("/account/email/confirm?t=" + tok).status_code == 200
    u = db.by_email("new@example.com")
    assert u and u["email_verified"] == 1 and db.by_email("a@example.com") is None
    assert outbox[-1]["to"] == "a@example.com" and "changed" in outbox[-1]["subject"]      # old address told
    assert app.test_client().get("/account/email/confirm?t=" + tok).status_code == 400    # single use
