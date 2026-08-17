"""Finnhub adapter — real-time US quotes for the live board overlay.

FMP's free tier blocks the multi-symbol batch quote, so the whole-board price
refresh runs on Finnhub instead (free tier: real-time US quotes, 60 calls/min,
no daily cap). One call per symbol, rate-limited to stay under the cap; fetching
116 names takes ~2 min, which is fine for a background rebuild. FMP still powers
fundamentals. Enabled when ``FINNHUB_API_KEY`` is set; returns {}/None on any
failure so callers fall back to the cached snapshot price.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque

_BASE = "https://finnhub.io/api/v1"


def _key() -> str | None:
    return os.environ.get("FINNHUB_API_KEY") or None


def has_finnhub() -> bool:
    return bool(_key())


class _RateLimiter:
    """Allow at most ``max_calls`` per ``period`` seconds across threads."""

    def __init__(self, max_calls: int, period: float = 60.0):
        self.max = max_calls
        self.period = period
        self.calls: deque[float] = deque()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                while self.calls and now - self.calls[0] >= self.period:
                    self.calls.popleft()
                if len(self.calls) < self.max:
                    self.calls.append(now)
                    return
                wait = self.period - (now - self.calls[0])
            time.sleep(min(max(wait, 0.0), 1.0) + 0.01)


_LIMITER = _RateLimiter(55, 60.0)      # headroom under the 60/min free-tier cap


def _get(path: str, **params):
    key = _key()
    if not key:
        return None
    params["token"] = key
    try:
        import requests
        r = requests.get(_BASE + path, params=params, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:  # noqa: BLE001
        return None


def probe(path: str, **params):
    """Diagnostic: (status_code, short_body); the key never appears in the body."""
    key = _key()
    if not key:
        return (None, "FINNHUB_API_KEY not set")
    params["token"] = key
    try:
        import requests
        r = requests.get(_BASE + path, params=params, timeout=15)
        return (r.status_code, (r.text or "")[:300])
    except Exception as e:  # noqa: BLE001
        return (None, f"request failed: {e}")


def quote(symbol: str) -> dict | None:
    """Real-time quote for one symbol -> {price, change_pct}. None if no data.

    Finnhub returns c=0 for unknown symbols, so a zero price reads as no data.
    """
    j = _get("/quote", symbol=symbol)
    if not isinstance(j, dict):
        return None
    c = j.get("c")
    if not c:                                   # 0 / None -> unknown symbol
        return None
    dp = j.get("dp")                            # daily percent change (e.g. -0.72)
    return {"price": c, "change_pct": (dp / 100.0) if dp is not None else None}


def batch_quotes(tickers: list[str], workers: int = 4) -> dict[str, dict]:
    """Quotes for many symbols (one call each, rate-limited). {} on total failure."""
    from concurrent.futures import ThreadPoolExecutor

    syms = [t.upper() for t in (tickers or []) if t]
    if not syms:
        return {}

    def one(sym: str):
        _LIMITER.acquire()
        try:
            return sym, quote(sym)
        except Exception:  # noqa: BLE001
            return sym, None

    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for sym, q in ex.map(one, syms):
            if q:
                out[sym] = q
    return out
