"""Required 2-step verification with remembered devices, password strength,
anti-automation, cookie consent, the update opt-in and Sign in with Apple."""

import base64
import json
import re
import time

import pytest

from stockskill.accounts import security as S


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_AUTH", "1")
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    monkeypatch.setenv("STOCKSKILL_ANALYTICS_DB", str(tmp_path / "analytics.db"))
    tk = tmp_path / "t.csv"
    tk.write_text("[M7]\nAAPL\n")
    from stockskill.server import create_app
    a = create_app(tickers_path=str(tk), public=True)
    a.config["ACCT"]["board"] = None
    return a


@pytest.fixture
def outbox(monkeypatch):
    from stockskill.accounts import notify
    sent = []
    monkeypatch.setattr(notify, "email_ready", lambda: True)
    monkeypatch.setattr(notify, "send_simple", lambda to, subject, lines, url=None, label="": sent.append(
        {"to": to, "subject": subject, "text": " ".join(lines)}) or True)

    class Now:
        def __init__(self, target, args=(), daemon=None):
            self.t, self.a = target, args

        def start(self):
            self.t(*self.a)
    monkeypatch.setattr(S.threading, "Thread", Now)
    return sent


def _confirmed(app, email="a@example.com"):
    from stockskill.accounts import db
    c = app.test_client()
    c.post("/auth/signup", json={"email": email, "password": "a-long-password-1", "accept": True})
    db.update_user(db.by_email(email)["id"], email_verified=1, onboarded=1)
    c.get("/logout")
    return c


def _code(outbox):
    return re.search(r"Your code: (\d{6})", outbox[-1]["subject"]).group(1)


def test_every_sign_in_needs_a_code_until_the_device_is_remembered(app, outbox):
    c = _confirmed(app)
    login = {"email": "a@example.com", "password": "a-long-password-1"}
    r = c.post("/auth/login", json=login).get_json()
    assert r["mfa"] == "email" and r["email_hint"].startswith("a")
    assert c.get("/api/me").status_code == 401
    assert c.post("/auth/mfa", json={"code": _code(outbox), "remember": False}).get_json()["ok"]
    c.get("/logout")
    assert c.post("/auth/login", json=login).get_json().get("mfa") == "email"      # not remembered: asked again
    assert c.post("/auth/mfa", json={"code": _code(outbox)}).get_json()["ok"]     # remembered this time
    assert c.get_cookie("smi_dev").http_only
    c.get("/logout")
    assert c.post("/auth/login", json=login).get_json()["ok"]                      # trusted: straight in
    other = app.test_client()
    assert other.post("/auth/login", json=login).get_json().get("mfa") == "email"  # a new browser still asks
    me = c.get("/api/me").get_json()["user"]
    assert me["mfa_effective"] == "email" and me["trusted_devices"] == 1
    assert c.post("/api/me/devices/forget").get_json()["ok"]
    c.get("/logout")
    assert c.post("/auth/login", json=login).get_json().get("mfa") == "email"      # forgotten


def test_opt_out_and_no_email_fallback(app, outbox, monkeypatch):
    c = _confirmed(app)
    login = {"email": "a@example.com", "password": "a-long-password-1"}
    monkeypatch.setenv("STOCKSKILL_REQUIRE_2FA", "0")
    assert c.post("/auth/login", json=login).get_json()["ok"]
    c.get("/logout")
    monkeypatch.setenv("STOCKSKILL_REQUIRE_2FA", "1")
    from stockskill.accounts import notify
    monkeypatch.setattr(notify, "email_ready", lambda: False)                     # can't email codes: don't lock out
    assert c.post("/auth/login", json=login).get_json()["ok"]


def test_password_strength(monkeypatch):
    from stockskill.accounts import passwords as P
    assert "10 characters" in P.problem("short")
    assert P.problem("1234567890123") == "That password is too easy to guess."
    assert "email address" in P.problem("my-alexsmith-pw!", "alexsmith@example.com")
    assert "too easy" in P.problem("Password2024", "x@example.com")
    assert P.problem("correct horse battery staple", "x@example.com") is None
    monkeypatch.setattr(P, "pwned_count", lambda pw: 3861)
    assert "3,861 data breaches" in P.problem("correct horse battery staple")


def test_breach_lookup_is_k_anonymous(monkeypatch):
    import hashlib
    from stockskill.accounts import passwords as P
    real = P._real_pwned_count
    pw = "correct horse battery staple"
    digest = hashlib.sha1(pw.encode()).hexdigest().upper()
    seen = {}

    class R:
        status_code = 200
        text = f"0000000000000000000000000000000000A:1\n{digest[5:]}:42\n"

    def fake_get(url, timeout=None, headers=None):
        seen["url"] = url
        return R()
    import requests
    monkeypatch.setattr(requests, "get", fake_get)
    assert real(pw) == 42 and seen["url"].endswith("/range/" + digest[:5]) and pw not in seen["url"]
    monkeypatch.setattr(requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    assert real(pw) == 0                                                           # unreachable: don't block


def test_anti_automation(app, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_ANTIBOT", "1")
    from stockskill.accounts import antibot
    c = app.test_client()
    body = {"email": "b@example.com", "password": "a-long-password-1", "accept": True}
    assert "expired" in c.post("/auth/signup", json=body).get_json()["error"]          # no token: a script
    with app.test_request_context():
        ft = antibot.form_token()
    assert "quick" in c.post("/auth/signup", json={**body, "ft": ft}).get_json()["error"]   # 0 s on the page
    assert "wrong" in c.post("/auth/signup", json={**body, "ft": ft, "website": "http://spam"}).get_json()["error"]
    real = time.time
    monkeypatch.setattr(antibot.time, "time", lambda: real() + 5)
    assert c.post("/auth/signup", json={**body, "ft": ft}).get_json()["ok"]
    page = app.test_client().get("/signup").data
    assert b'id="hp-web"' in page and b"FT=" in page


def test_cookie_consent(app):
    from stockskill.accounts import attribution as A
    c = app.test_client()
    assert b'id="smi-ck"' in c.get("/").data                                       # no choice yet: the banner
    assert c.get_cookie(A.COOKIE) is not None
    r = c.post("/api/consent", json={"choice": "essential"})
    assert r.get_json()["ok"] and c.get_cookie("smi_consent").value == "essential"
    assert c.get_cookie(A.COOKIE) is None                                          # the optional cookie is gone
    page = c.get("/?utm_source=linkedin").data
    assert b'id="smi-ck"' not in page and c.get_cookie(A.COOKIE) is None           # and it stays gone
    policy = c.get("/cookies").data
    assert b"smi_src" in policy and b"essential cookies only" in policy
    assert c.post("/api/consent", json={"choice": "maybe"}).status_code == 400


def test_update_opt_in(app):
    from stockskill.accounts import db
    c = app.test_client()
    c.post("/auth/signup", json={"email": "c@example.com", "password": "a-long-password-1", "accept": True})
    assert db.by_email("c@example.com")["notify_updates"] == 0                     # unticked by default
    app.test_client().post("/auth/signup", json={"email": "d@example.com", "password": "a-long-password-1",
                                                 "accept": True, "updates": True})
    u = db.by_email("d@example.com")
    assert u["notify_updates"] == 1 and u["updates_consent_at"]


# --- Sign in with Apple ---------------------------------------------------------------

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


@pytest.fixture
def apple_key():
    from cryptography.hazmat.primitives.asymmetric import rsa
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    n = k.public_key().public_numbers()
    jwk = {"kty": "RSA", "kid": "k1", "alg": "RS256", "n": _b64(n.n.to_bytes(256, "big")), "e": _b64(n.e.to_bytes(3, "big"))}
    return k, jwk


def _token(k, claims, kid="k1"):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    h = _b64(json.dumps({"alg": "RS256", "kid": kid}).encode())
    b = _b64(json.dumps(claims).encode())
    sig = k.sign(f"{h}.{b}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{h}.{b}.{_b64(sig)}"


def _claims(**kw):
    now = time.time()
    return {"iss": "https://appleid.apple.com", "aud": "com.smi.web", "sub": "apple-1", "email": "ap@example.com",
            "email_verified": "true", "iat": now, "exp": now + 600, **kw}


def test_apple_token_checks(apple_key):
    from stockskill.accounts import apple
    k, jwk = apple_key
    assert apple.verify_token(_token(k, _claims()), "com.smi.web", [jwk])["sub"] == "apple-1"
    assert apple.verify_token(_token(k, _claims(aud="someone.else")), "com.smi.web", [jwk]) is None
    assert apple.verify_token(_token(k, _claims(exp=time.time() - 1)), "com.smi.web", [jwk]) is None
    assert apple.verify_token(_token(k, _claims(iss="https://evil.example")), "com.smi.web", [jwk]) is None
    assert apple.verify_token(_token(k, _claims(email_verified="false")), "com.smi.web", [jwk]) is None
    t = _token(k, _claims())
    head, body, sig = t.split(".")
    forged = _b64(json.dumps(_claims(sub="someone-else")).encode())
    assert apple.verify_token(f"{head}.{forged}.{sig}", "com.smi.web", [jwk]) is None


def test_apple_sign_in_route(app, apple_key, monkeypatch):
    from stockskill.accounts import apple, db
    k, jwk = apple_key
    assert app.test_client().post("/auth/apple", json={"id_token": "x"}).status_code == 400   # not set up
    monkeypatch.setenv("APPLE_CLIENT_ID", "com.smi.web")
    monkeypatch.setattr(apple, "_apple_keys", lambda refresh=False: [jwk])
    c = app.test_client()
    r = c.post("/auth/apple", json={"id_token": _token(k, _claims()), "user": {"name": {"firstName": "Ap", "lastName": "Ple"}}})
    assert r.get_json()["ok"]
    u = db.by_apple("apple-1")
    assert u["email"] == "ap@example.com" and u["first_name"] == "Ap"
    assert c.post("/auth/apple", json={"id_token": "not.a.token"}).status_code == 401
    assert b"apple-btn" in app.test_client().get("/login").data
