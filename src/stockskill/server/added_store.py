"""Persistent store for user-added tickers.

Two backends, picked automatically:

* **Local file** (``STOCKSKILL_ADDED_FILE``) - for running on a real machine
  (local dev / ngrok), where the disk is persistent. A plain JSON file.
* **Upstash Redis** (``UPSTASH_REDIS_REST_URL`` + ``UPSTASH_REDIS_REST_TOKEN``) -
  for an ephemeral host (e.g. a free cloud tier) whose filesystem resets on every
  restart, so the list must live OUTSIDE the instance.

The local file wins when set (no network needed). With neither configured every
function degrades gracefully - returns None / no-ops - and adds are in-memory only.
"""

from __future__ import annotations

import json
import os

_KEY = "stockskill:added"


def _file_path():
    return os.environ.get("STOCKSKILL_ADDED_FILE") or None


def _load_file(path: str) -> list[str] | None:
    try:
        if not os.path.exists(path):
            return []
        with open(path) as f:
            data = json.load(f)
        return [str(t).upper() for t in data if t] if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return None


def _save_file(path: str, tickers) -> bool:
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w") as f:
            json.dump(list(tickers), f)
        return True
    except Exception:  # noqa: BLE001
        return False


def _cfg():
    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    return (url.rstrip("/"), token) if (url and token) else (None, None)


def enabled() -> bool:
    return _file_path() is not None or _cfg()[0] is not None


def load_added() -> list[str] | None:
    """Persisted added tickers (upper-cased), [] if none, None if unavailable."""
    path = _file_path()
    if path:
        return _load_file(path)
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
    path = _file_path()
    if path:
        return _save_file(path, tickers)
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
