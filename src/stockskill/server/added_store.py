"""Persistent store for user-added tickers.

The free host's filesystem is ephemeral (reset on every restart, sleep/wake, and
redeploy), so tickers added through the board's Add box vanish unless they are
kept OUTSIDE the instance. This stores the added list in Upstash Redis via its
REST API (HTTP, no driver, free tier) so an added ticker sticks forever.

Enabled when ``UPSTASH_REDIS_REST_URL`` + ``UPSTASH_REDIS_REST_TOKEN`` are set.
Every function degrades gracefully: with no store configured (e.g. local dev) it
returns None / no-ops, and the board falls back to in-memory-only adds.
"""

from __future__ import annotations

import json
import os

_KEY = "stockskill:added"


def _cfg():
    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    return (url.rstrip("/"), token) if (url and token) else (None, None)


def enabled() -> bool:
    return _cfg()[0] is not None


def load_added() -> list[str] | None:
    """Persisted added tickers (upper-cased), [] if none, None if unavailable."""
    url, token = _cfg()
    if not url:
        return None
    try:
        import requests
        r = requests.get(f"{url}/get/{_KEY}",
                         headers={"Authorization": f"Bearer {token}"}, timeout=8)
        if r.status_code != 200:
            return None
        val = r.json().get("result")
        if not val:
            return []
        data = json.loads(val)
        return [str(t).upper() for t in data if t] if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return None


def save_added(tickers) -> bool:
    """Persist the added-ticker list. No-op (False) if unconfigured; best-effort."""
    url, token = _cfg()
    if not url:
        return False
    try:
        import requests
        r = requests.post(f"{url}/set/{_KEY}", data=json.dumps(list(tickers)),
                          headers={"Authorization": f"Bearer {token}"}, timeout=8)
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False
