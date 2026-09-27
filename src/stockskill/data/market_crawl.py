"""Slowly cache the whole US stock market (price history and snapshot for
every company in the screener), biggest first, so any stock opens or joins a
watchlist instantly instead of waiting on Yahoo.

Runs in the background when STOCKSKILL_CRAWL=1: one stock every ``pace``
seconds (twice as slow while the market is open), skipping any cached in the
last ``stale_days``; a full first pass takes about ten hours. After a run of
failures (Yahoo throttling) it backs off for 30 minutes. Progress is kept in
<cache>/_crawl.json for the admin page. SEC financials still load on a stock's
first view: fetching every company's filings would be tens of gigabytes a pass.
"""

from __future__ import annotations

import json
import os
import threading
import time

FAILS_BEFORE_BACKOFF = 8
BACKOFF = 1800.0
REST_BETWEEN_PASSES = 6 * 3600.0


def state_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "_crawl.json")


def status(cache_dir: str | None) -> dict | None:
    try:
        return json.load(open(state_path(cache_dir or "data/cache")))
    except (OSError, ValueError):
        return None


def _save(cache_dir: str, st: dict) -> None:
    tmp = state_path(cache_dir) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f)
    os.replace(tmp, state_path(cache_dir))


def order(rows: list[dict]) -> list[str]:
    """Every listed ticker once, largest market value first."""
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: -(r.get("mcap") or 0)):
        t = (r.get("ticker") or "").upper()
        if t and t not in seen and r.get("price"):
            seen.add(t)
            out.append(t)
    return out


def fresh(cache_dir: str, ticker: str, stale_days: float) -> bool:
    from ..watchlist.pipeline import _cache_path
    try:
        return time.time() - os.path.getmtime(_cache_path(cache_dir, ticker)) < stale_days * 86400
    except OSError:
        return False


def one_pass(cache_dir: str, tickers: list[str], period: str, pace: float = 6.0, stale_days: float = 7.0,
             fetch=None, sleep=time.sleep, is_open=None, stop: threading.Event | None = None) -> dict:
    """Fetch every ticker that isn't fresh in the cache. Returns the pass's counts."""
    from ..watchlist.pipeline import _is_good, fetch_one
    fetch = fetch or (lambda t: fetch_one(t, period=period, cache_dir=cache_dir, ttl=stale_days * 86400))
    st = {"started": time.time(), "total": len(tickers), "done": 0, "fetched": 0, "cached": 0, "failed": 0,
          "last": None, "state": "running"}
    fails = 0
    for i, t in enumerate(tickers):
        if stop is not None and stop.is_set():
            break
        st["done"] = i + 1
        if fresh(cache_dir, t, stale_days):
            st["cached"] += 1
            continue
        try:
            ok = _is_good(fetch(t))
        except Exception:  # noqa: BLE001
            ok = False
        st["last"] = t
        if ok:
            st["fetched"] += 1
            fails = 0
        else:
            st["failed"] += 1
            fails += 1
        if st["done"] % 25 == 0 or not ok:
            _save(cache_dir, st)
        if fails >= FAILS_BEFORE_BACKOFF:               # probably throttled: let the provider cool off
            st["state"] = "backing off"
            _save(cache_dir, st)
            sleep(BACKOFF)
            fails, st["state"] = 0, "running"
        sleep(pace * (2 if (is_open and is_open()) else 1))
    st["state"] = "resting"
    st["finished"] = time.time()
    _save(cache_dir, st)
    return st


def run_forever(cache_dir: str, period: str, pace: float = 6.0) -> None:
    """Background loop: wait for the screener's list, crawl it, rest, repeat."""
    from ..marketclock import market_status
    from . import market_screen

    def loop():
        time.sleep(120)                                # let the server finish starting up
        while True:
            try:
                u = market_screen.universe(cache_dir, lambda: {})
                if u.get("warming") or not u.get("rows"):
                    time.sleep(120)
                    continue
                one_pass(cache_dir, order(u["rows"]), period, pace, is_open=lambda: market_status().is_open)
                time.sleep(REST_BETWEEN_PASSES)
            except Exception as e:  # noqa: BLE001
                import sys
                print(f"market crawl: {e!r}", file=sys.stderr, flush=True)
                time.sleep(600)
    threading.Thread(target=loop, daemon=True, name="market-crawl").start()
