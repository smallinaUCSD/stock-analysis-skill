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


def _signup(c, email="a@example.com", pw="a-long-password-1", confirm=True):
    r = c.post("/auth/signup", json={"email": email, "password": pw, "accept": True})
    if confirm:                                  # the emailed code confirms the address first
        from stockskill.accounts import db
        u = db.by_email(email)
        S._CODES.pop((u["id"], "verify"), None)
        code = "424242"
        S._CODES[(u["id"], "verify")] = (S.generate_password_hash(code), time.time() + 600, 0)
        assert c.post("/api/me/verify-email", json={"code": code}).get_json()["ok"]
    return r


def _link(text, path):
    return re.search(re.escape(path) + r"\?t=([\w.\-]+)", text).group(1)


def test_signup_confirms_email_with_a_code_first(app, outbox):
    from stockskill.accounts import db
    c = app.test_client()
    r = _signup(c, confirm=False).get_json()
    assert r["next"] == "/verify-email"
    first = outbox[0]
    assert first["to"] == "a@example.com" and first["subject"] == "Confirm your email"
    code = re.search(r"(\d{6})", first["text"]).group(1)
    assert c.get("/").headers["Location"].endswith("/verify-email")              # the app waits for the code
    assert c.get("/api/me").status_code == 403
    assert c.get("/verify-email").status_code == 200
    assert c.post("/api/me/verify-email/send", json={"auto": True}).get_json()["sent"] is False   # one is out
    assert c.post("/api/me/verify-email", json={"code": "000000" if code != "000000" else "111111"}).status_code == 400
    ok = c.post("/api/me/verify-email", json={"code": code}).get_json()
    assert ok["ok"] and ok["next"] == "/welcome"
    assert db.by_email("a@example.com")["email_verified"] == 1
    assert outbox[-1]["subject"] == "Welcome to SM Investments" and "/notifications/verify" not in outbox[-1]["text"]
    assert c.get("/api/me").status_code == 200


def test_wrong_address_can_be_fixed_before_confirming(app, outbox):
    from stockskill.accounts import db
    c = app.test_client()
    _signup(c, confirm=False)
    _signup(app.test_client(), email="taken@example.com")
    assert c.post("/api/me/verify-email/change", json={"email": "taken@example.com"}).status_code == 409
    r = c.post("/api/me/verify-email/change", json={"email": "b@example.com"}).get_json()
    assert r["ok"] and outbox[-1]["to"] == "b@example.com" and outbox[-1]["subject"] == "Confirm your email"
    code = re.search(r"(\d{6})", outbox[-1]["text"]).group(1)
    assert c.post("/api/me/verify-email", json={"code": code}).get_json()["ok"]
    assert db.by_email("b@example.com")["email_verified"] == 1 and db.by_email("a@example.com") is None


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


def test_one_account_per_inbox(app, outbox):
    from stockskill.accounts import db
    assert db.canonical_email(" J.Smith+stocks@GoogleMail.com ") == "jsmith@gmail.com"
    assert db.canonical_email("ann+x@outlook.com") == "ann@outlook.com"
    assert db.canonical_email("a.b@company.com") == "a.b@company.com"          # dots only ignored by Gmail
    _signup(app.test_client(), email="jsmith@gmail.com")
    for twin in ("J.Smith@gmail.com", "jsmith+stocks@gmail.com", "j.s.m.i.t.h@googlemail.com"):
        r = app.test_client().post("/auth/signup", json={"email": twin, "password": "a-long-password-1", "accept": True})
        assert r.status_code == 409, twin
    c = app.test_client()                                                    # the same inbox signs in to it
    assert c.post("/auth/login", json={"email": "J.Smith@gmail.com", "password": "a-long-password-1"}).get_json()["ok"]
    assert db.duplicate_accounts() == []


def test_new_google_account_confirms_email_with_a_code(app, outbox, monkeypatch):
    from stockskill.accounts import auth, db
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(auth, "verify_google_token", lambda t, cid: {"sub": "g-9", "email": "g@example.com",
                                                                     "given_name": "Gee", "family_name": "Oh"})
    c = app.test_client()
    r = c.post("/auth/google", json={"credential": "x"}).get_json()
    assert r["ok"] and r["next"] == "/verify-email" and db.by_email("g@example.com")["email_verified"] == 0
    assert c.post("/api/me/verify-email/send", json={"auto": True}).get_json()["sent"]
    code = re.search(r"(\d{6})", outbox[-1]["text"]).group(1)
    assert c.post("/api/me/verify-email", json={"code": code}).get_json()["ok"]


# --- the security review's findings stay fixed ------------------------------------------

EVIL = "</script><script>alert(document.domain)</script>"


def test_script_json_cannot_close_the_script():
    from stockskill.safejs import script_json
    out = script_json({"a": EVIL, "b": "x&y "})
    assert "</script" not in out and "<" not in out and "&" not in out and " " not in out
    import json
    assert json.loads(out) == {"a": EVIL, "b": "x&y "}


def test_reflected_values_are_not_executable(app, outbox):
    c = app.test_client()
    r = c.get("/reset?t=" + EVIL)
    assert r.status_code == 400 and b"alert(document.domain)" not in r.data
    page = c.get("/login?next=" + EVIL).get_data(as_text=True)
    assert "alert(document.domain)" not in page and 'NEXT=""' in page
    assert 'NEXT="/screener?x=1"' in c.get("/login?next=/screener?x=1").get_data(as_text=True)
    assert 'NEXT=""' in c.get("/login?next=//evil.example/x").get_data(as_text=True)
    _signup(c)
    assert "</script><script>alert" not in c.get("/trades?q=" + EVIL).get_data(as_text=True)


def test_names_in_the_board_config_are_escaped(app, outbox, monkeypatch):
    from stockskill.accounts.pages import personalize_board
    html = personalize_board("<html><head></head><body></body></html>", {"first_name": EVIL, "last_name": "X",
                                                                         "email": "a@example.com"}, ["AAPL"])
    assert "</script><script>alert" not in html


def test_security_headers(app):
    h = app.test_client().get("/terms").headers
    assert h["X-Content-Type-Options"] == "nosniff" and h["X-Frame-Options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in h["Content-Security-Policy"] and h["Referrer-Policy"]


def test_google_sign_in_evicts_an_unconfirmed_squatter(app, outbox, monkeypatch):
    from stockskill.accounts import auth, db
    attacker = app.test_client()
    _signup(attacker, email="victim@gmail.com", confirm=False)            # never proves the inbox
    assert attacker.post("/auth/passkey/register/options").status_code == 403   # can't plant a passkey either
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(auth, "verify_google_token", lambda t, cid: {"sub": "g-v", "email": "victim@gmail.com",
                                                                     "given_name": "Vic", "family_name": "Tim"})
    victim = app.test_client()
    assert victim.post("/auth/google", json={"credential": "x"}).get_json()["ok"]
    u = db.by_email("victim@gmail.com")
    assert u["google_sub"] == "g-v" and u["email_verified"] == 1 and u["password_hash"] is None
    auth._SEEN.clear()
    assert attacker.get("/api/me").status_code == 401                     # their session is gone
    r = app.test_client().post("/auth/login", json={"email": "victim@gmail.com", "password": "a-long-password-1"})
    assert r.status_code == 401                                           # and their password no longer works
