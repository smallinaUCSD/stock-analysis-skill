"""Password strength: long enough, not trivially guessable, and not a password
that has already leaked in a data breach.

The breach check uses Have I Been Pwned's range API with k-anonymity: only the
first 5 characters of the password's SHA-1 leave this server, never the password
or its full hash. If the service can't be reached the check is skipped (a
sign-up shouldn't fail because a third party is down). STOCKSKILL_HIBP=0 turns
it off.
"""

from __future__ import annotations

import hashlib
import os
import re

MIN, MAX = 10, 200
_COMMON = ("password", "passw0rd", "qwerty", "letmein", "welcome", "iloveyou", "admin", "abc123", "monkey",
           "dragon", "sunshine", "princess", "football", "baseball", "trustno1", "123456", "111111")
_RUNS = re.compile(r"(0123|1234|2345|3456|4567|5678|6789|abcd|bcde|qwer|asdf|zxcv)")


def pwned_count(pw: str) -> int:
    """How many times this password appears in known breaches (0 if unknown or unreachable)."""
    if os.environ.get("STOCKSKILL_HIBP", "1") == "0":
        return 0
    digest = hashlib.sha1(pw.encode("utf-8")).hexdigest().upper()
    prefix, rest = digest[:5], digest[5:]
    try:
        import requests
        r = requests.get(f"https://api.pwnedpasswords.com/range/{prefix}", timeout=3,
                         headers={"Add-Padding": "true", "User-Agent": "sm-investments-password-check"})
        if r.status_code != 200:
            return 0
        for line in r.text.splitlines():
            h, _, n = line.partition(":")
            if h.strip() == rest:
                return int(n.strip() or 0)
    except Exception:  # noqa: BLE001
        return 0
    return 0


def problem(pw: str, email: str = "") -> str | None:
    """Why this password isn't acceptable, or None when it's fine."""
    if len(pw) < MIN:
        return f"Use a password of at least {MIN} characters."
    if len(pw) > MAX:
        return f"Use a password of at most {MAX} characters."
    low = pw.lower()
    if pw.isdigit() or len(set(pw)) < 5 or low == (email or "").lower():
        return "That password is too easy to guess."
    name = (email or "").split("@")[0].lower()
    if len(name) >= 4 and name in low:
        return "Don't use your email address in your password."
    kinds = sum(bool(re.search(p, pw)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    if len(pw) < 16 and (any(w in low for w in _COMMON) or (_RUNS.search(low) and kinds < 3)):
        return "That password is too easy to guess. Try a longer phrase, or mix in numbers and symbols."
    n = pwned_count(pw)
    if n:
        return f"That password has appeared in {n:,} data breaches, so attackers try it first. Choose a different one."
    return None
