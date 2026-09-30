"""Where sign-ups come from.

A page visit that arrives with campaign tags (?utm_source=linkedin&utm_medium=...)
or from another site sets a first-party cookie remembering that touch for 60 days;
when that browser creates an account, the touch is saved on the account. The admin
page groups sign-ups by it. No third-party trackers, nothing leaves the server.

Explicit campaign tags win over an earlier touch (the newest campaign link someone
clicked is the one that brought them back); a plain referral only fills an empty
cookie, so browsing around the site doesn't overwrite it.
"""

from __future__ import annotations

import base64
import json
import re
from urllib.parse import urlparse

from flask import g, request

COOKIE = "smi_src"
MAX_AGE = 60 * 86400

# referring hosts -> the source name used in reports
_HOSTS = [
    (("linkedin.com", "lnkd.in"), "linkedin"),
    (("t.co", "x.com", "twitter.com"), "x"),
    (("instagram.com",), "instagram"),
    (("facebook.com", "fb.com", "fb.me"), "facebook"),
    (("threads.net", "threads.com"), "threads"),
    (("tiktok.com",), "tiktok"),
    (("reddit.com", "redd.it"), "reddit"),
    (("news.ycombinator.com",), "hackernews"),
    (("youtube.com", "youtu.be"), "youtube"),
    (("google.",), "google"),
    (("bing.com",), "bing"),
    (("duckduckgo.com",), "duckduckgo"),
]
_SOCIAL = {"linkedin", "x", "instagram", "facebook", "threads", "tiktok", "reddit", "hackernews", "youtube"}
_SEARCH = {"google", "bing", "duckduckgo"}


def clean(v, n: int = 60) -> str | None:
    """Keep a tag short and plain (letters, digits, - _ . /), lower case."""
    v = re.sub(r"[^a-z0-9_.\-/ ]", "", str(v or "").strip().lower())[:n].strip()
    return v or None


def source_for_host(host: str) -> str:
    host = (host or "").lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    for keys, name in _HOSTS:
        for k in keys:
            if (k.endswith(".") and (host.startswith(k) or f".{k}" in host)) or host == k or host.endswith("." + k):
                return name
    return host


def touch(args, referrer: str, own_host: str, path: str) -> dict | None:
    """The attribution a request carries, or None when it carries none."""
    ref = urlparse(referrer or "").netloc.lower()
    external = bool(ref) and ref.split(":")[0] not in {own_host.split(":")[0], ""}
    src = clean(args.get("utm_source"))
    if src:
        return {"s": src, "m": clean(args.get("utm_medium")), "c": clean(args.get("utm_campaign"), 80),
                "r": clean(ref if external else "", 80), "l": clean(path, 80), "u": 1}
    if external:
        name = source_for_host(ref)
        medium = "social" if name in _SOCIAL else "search" if name in _SEARCH else "referral"
        return {"s": clean(name), "m": medium, "c": None, "r": clean(ref, 80), "l": clean(path, 80)}
    return None


def encode(t: dict) -> str:
    """URL-safe base64 of compact JSON: a cookie value that needs no quoting."""
    return base64.urlsafe_b64encode(json.dumps(t, separators=(",", ":")).encode()).decode().rstrip("=")


def read(raw: str | None) -> dict | None:
    try:
        raw = (raw or "").strip('"')
        d = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        return d if isinstance(d, dict) and d.get("s") else None
    except (ValueError, TypeError):
        return None


def init_app(app) -> None:
    @app.before_request
    def _attribution_in():
        if request.method != "GET" or request.path.startswith(("/api/", "/static/")):
            return None
        from .consent import optional_allowed
        if not optional_allowed():                 # they chose essential cookies only
            return None
        t = touch(request.args, request.referrer or "", request.host or "", request.path)
        have = read(request.cookies.get(COOKIE))
        if t and (t.get("u") or not have):
            g._src_cookie = t
        elif not have:
            g._src_cookie = {"s": "direct", "m": None, "c": None, "r": None, "l": clean(request.path, 80)}
        return None

    @app.after_request
    def _attribution_out(resp):
        t = g.pop("_src_cookie", None)
        if t is not None:
            secure = request.is_secure or (app.config.get("SESSION_COOKIE_SECURE") is True)
            resp.set_cookie(COOKIE, encode(t), max_age=MAX_AGE, httponly=True,
                            samesite="Lax", secure=secure)
        return resp


def record_signup(uid: int) -> None:
    """Save this browser's first-touch source on a new account ('direct' if none)."""
    from . import db
    t = read(request.cookies.get(COOKIE)) or getattr(g, "_src_cookie", None) or {"s": "direct"}
    db.update_user(uid, src_source=t.get("s"), src_medium=t.get("m"), src_campaign=t.get("c"),
                   src_referrer=t.get("r"), src_landing=t.get("l"))
