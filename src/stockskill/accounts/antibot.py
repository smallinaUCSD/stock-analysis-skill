"""Quiet protection against automated sign-ups and credential stuffing, on top of
the per-IP and per-account rate limits. Nothing for a person to solve:

* a honeypot field people never see (bots that fill every input fill it too);
* a signed form token issued when the page is drawn, so a script has to load the
  page first, and it can't be reused for a day;
* a minimum time on the page for sign-ups (a person takes more than 2 seconds to
  type an email and a password; a script doesn't).

STOCKSKILL_ANTIBOT=0 turns it off (tests drive the API directly).
"""

from __future__ import annotations

import os
import time

SALT = "form-token"
MAX_AGE = 86400


def _serializer():
    from itsdangerous import URLSafeTimedSerializer
    from .auth import _secret_key
    return URLSafeTimedSerializer(_secret_key(), salt=SALT)


def enabled() -> bool:
    return os.environ.get("STOCKSKILL_ANTIBOT", "1") != "0"


def form_token() -> str:
    return _serializer().dumps(round(time.time(), 2))


def check(body: dict, min_seconds: float = 0.0) -> str | None:
    """Why this submission looks automated, or None when it looks like a person."""
    if not enabled():
        return None
    if str(body.get("website") or "").strip():
        return "Something went wrong. Please reload the page and try again."
    try:
        issued = float(_serializer().loads(str(body.get("ft") or ""), max_age=MAX_AGE))
    except Exception:  # noqa: BLE001 - missing, forged or expired
        return "This page has expired. Reload it and try again."
    if time.time() - issued < min_seconds:
        return "That was quick! Please check the form and try again."
    return None
