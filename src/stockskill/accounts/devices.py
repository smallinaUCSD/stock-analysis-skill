"""Two-step verification for every account, remembered per device for 30 days.

Everyone has a second step: their authenticator app if they set one up, otherwise
a 6-digit code emailed to their confirmed address. After a correct code the
browser gets a random token (cookie ``smi_dev``, HttpOnly); the server keeps only
its SHA-256, so it can be revoked (signing out everywhere, a password reset or
"this wasn't me" forgets every device). Passkeys skip the step: a passkey is
already something you have plus something you are.

STOCKSKILL_REQUIRE_2FA=0 turns the requirement off (back to opt-in). If email
isn't set up on the server, emailed codes can't be delivered, so the requirement
falls back to authenticator-app users only rather than locking everyone out.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sys
import time

from flask import current_app, request

from . import db

COOKIE = "smi_dev"
DAYS = 30


def required() -> bool:
    return os.environ.get("STOCKSKILL_REQUIRE_2FA", "1") != "0"


def second_step(u: dict) -> str | None:
    """The second step this person gets at sign-in: 'totp', 'email' or None."""
    if u.get("mfa_method"):
        return u["mfa_method"]
    if not required() or not u.get("email_verified"):
        return None
    from .notify import email_ready
    if not email_ready():
        print("devices: STOCKSKILL_REQUIRE_2FA is on but email isn't set up; emailed codes can't be sent",
              file=sys.stderr, flush=True)
        return None
    return "email"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def is_trusted(u: dict) -> bool:
    """This browser passed the second step for this account within 30 days."""
    raw = request.cookies.get(COOKIE)
    if not raw:
        return False
    row = db.trusted_device(_hash(raw))
    if not row or row["user_id"] != u["id"] or time.time() - row["created_at"] > DAYS * 86400:
        return False
    db.touch_trusted_device(row["id"])
    return True


def remember(resp, uid: int):
    """Mark this browser as trusted for ``uid`` (sets the cookie on ``resp``)."""
    raw = secrets.token_urlsafe(32)
    db.add_trusted_device(_hash(raw), uid, request.headers.get("User-Agent"))
    resp.set_cookie(COOKIE, raw, max_age=DAYS * 86400, httponly=True, samesite="Lax",
                    secure=request.is_secure or bool(current_app.config.get("SESSION_COOKIE_SECURE")))
    return resp
