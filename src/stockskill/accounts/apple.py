"""Sign in with Apple.

The page opens Apple's sign-in (their JS, in a popup) and gets back an ID token:
a JWT signed by Apple (RS256). We check the signature against Apple's published
keys, that it was issued by Apple for our Services ID (APPLE_CLIENT_ID), hasn't
expired, and carries a verified email, then sign the person in the same way as
Google: a returning Apple account, an existing account with that email (linked),
or a new one. 2-step verification applies on devices not yet trusted.

Off unless APPLE_CLIENT_ID is set. Setup (Apple Developer account): an App ID
with "Sign in with Apple", a Services ID (this is APPLE_CLIENT_ID) with the site's
domain and return URL (https://<site>/login), and, to email people who hide
their address, the sending domain registered under "Private Email Relay".
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import threading
import time

from flask import jsonify, request

from . import db

ISSUER = "https://appleid.apple.com"
JWKS_URL = "https://appleid.apple.com/auth/keys"
_KEYS: dict = {"at": 0.0, "keys": []}
_LOCK = threading.Lock()


def client_id() -> str | None:
    return (os.environ.get("APPLE_CLIENT_ID") or "").strip() or None


def _b64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _apple_keys(refresh: bool = False) -> list[dict]:
    with _LOCK:
        if refresh or not _KEYS["keys"] or time.time() - _KEYS["at"] > 86400:
            import requests
            r = requests.get(JWKS_URL, timeout=10)
            r.raise_for_status()
            _KEYS.update(at=time.time(), keys=r.json().get("keys") or [])
        return list(_KEYS["keys"])


def verify_token(token: str, aud: str, keys=None) -> dict | None:
    """Claims from an Apple ID token, or None if anything about it is off."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    try:
        head_b, body_b, sig_b = token.split(".")
        head, claims = json.loads(_b64(head_b)), json.loads(_b64(body_b))
        if head.get("alg") != "RS256":
            return None
        pool = keys if keys is not None else _apple_keys()
        jwk = next((k for k in pool if k.get("kid") == head.get("kid")), None)
        if jwk is None and keys is None:                       # Apple rotated its keys
            jwk = next((k for k in _apple_keys(refresh=True) if k.get("kid") == head.get("kid")), None)
        if jwk is None:
            return None
        pub = rsa.RSAPublicNumbers(int.from_bytes(_b64(jwk["e"]), "big"), int.from_bytes(_b64(jwk["n"]), "big")).public_key()
        pub.verify(_b64(sig_b), f"{head_b}.{body_b}".encode(), padding.PKCS1v15(), hashes.SHA256())
    except (ValueError, KeyError, InvalidSignature, json.JSONDecodeError):
        return None
    except Exception:  # noqa: BLE001 - Apple's keys unreachable, etc.
        return None
    audiences = claims.get("aud") if isinstance(claims.get("aud"), list) else [claims.get("aud")]
    now = time.time()
    if claims.get("iss") != ISSUER or aud not in audiences or float(claims.get("exp") or 0) < now:
        return None
    if float(claims.get("iat") or 0) > now + 300 or not claims.get("sub") or not claims.get("email"):
        return None
    if str(claims.get("email_verified")).lower() != "true":
        return None
    return claims


def init_app(app) -> None:
    from .auth import _SEEN, _ip, _limited, _login, _next_for

    @app.post("/auth/apple")
    def apple_login():
        cid = client_id()
        if not cid:
            return jsonify({"ok": False, "error": "Sign in with Apple isn't set up on this server."}), 400
        if _limited("apple:" + _ip(), 30):
            return jsonify({"ok": False, "error": "Too many attempts. Try again later."}), 429
        b = request.get_json(silent=True) or {}
        c = verify_token(str(b.get("id_token") or ""), cid)
        if not c:
            return jsonify({"ok": False, "error": "Apple sign-in failed. Please try again."}), 401
        sub, email = c["sub"], c["email"].strip().lower()
        u = db.by_apple(sub) or db.by_email(email)
        created = not u
        if u:
            if not u.get("email_verified") and not u.get("apple_sub"):
                # an unconfirmed account made with this address: Apple proved this person owns it (see Google)
                db.update_user(u["id"], password_hash=None, mfa_method=None, mfa_secret=None, mfa_recovery=None)
                db.delete_all_passkeys(u["id"])
                db.revoke_sessions(u["id"])
                _SEEN.clear()
            if not u.get("apple_sub"):
                db.update_user(u["id"], apple_sub=sub)
            if not u.get("email_verified"):
                db.update_user(u["id"], email_verified=1)
            u = db.get_user(u["id"])
        else:
            name = (b.get("user") or {}).get("name") or {}          # Apple sends the name only the first time
            try:
                uid = db.create_user(email, first_name=(name.get("firstName") or None), last_name=(name.get("lastName") or None))
            except sqlite3.IntegrityError:
                return jsonify({"ok": False, "error": "An account with this email already exists. Sign in instead."}), 409
            db.update_user(uid, apple_sub=sub)
            from .attribution import record_signup
            record_signup(uid)
            db.account_event("created", "apple")
            u = db.get_user(uid)
        if not created:
            from .devices import is_trusted, second_step
            if second_step(u) and not is_trusted(u):
                from .security import start_mfa
                return start_mfa(u, b.get("next"), via="Apple")
        _login(u["id"], "Apple")
        return jsonify({"ok": True, "next": _next_for(u, b.get("next"))})
