"""Live watchlist state for the served dashboard.

Holds the base ticker file plus any tickers the user adds through the UI, and
caches the rendered HTML with a market-aware TTL so the polling page is cheap.
All numbers still come from the tested build pipeline; this only manages state.
"""

from __future__ import annotations

import os
import re
import threading
import time

from ..watchlist import build_watchlist_html

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-\^]{1,12}$")


_WARMING_HTML = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<meta http-equiv='refresh' content='6'><title>Loading…</title>"
    "<style>body{font-family:system-ui,-apple-system,sans-serif;background:#0b0e13;"
    "color:#e6e8eb;text-align:center;padding-top:22vh;margin:0}"
    ".s{width:34px;height:34px;border:3px solid #2a2f3a;border-top-color:#3b82f6;"
    "border-radius:50%;margin:0 auto 18px;animation:sp 1s linear infinite}"
    "@keyframes sp{to{transform:rotate(360deg)}}p{color:#8a93a2}</style></head>"
    "<body><div class='s'></div><h2>Loading the market board…</h2>"
    "<p>Fetching live data. This can take a moment on first load.<br>"
    "The page refreshes automatically.</p></body></html>"
)


class WatchlistService:
    def __init__(self, tickers_path: str = "data/tickers.csv", cache_dir: str | None = None,
                 public: bool = False, bmc_url: str | None = None, period: str = "5y",
                 cache_ttl: float = 1800.0):
        self._path = tickers_path
        self._cache_dir = cache_dir
        self._public = public
        self._bmc_url = bmc_url
        self._period = period
        self._cache_ttl = cache_ttl
        self._added: list[str] = []          # user-added, in order
        self._html: str | None = None
        self._ts = 0.0
        self._refresh = 1800
        self._building = False
        self._lock = threading.Lock()
        self._fast_lock = threading.Lock()

    # --- spec assembly -------------------------------------------------
    def _base_text(self) -> str:
        try:
            with open(self._path) as f:
                return f.read()
        except OSError:
            return "[TICKERS]\nAAPL, MSFT, NVDA\n"

    def _spec(self) -> str:
        text = self._base_text()
        if self._added:
            text += "\n\n[ADDED]\n" + ", ".join(self._added) + "\n"
        return text

    def _current_tickers(self) -> set[str]:
        from ..watchlist import parse_tickers_text
        return {t.upper() for t in parse_tickers_text(self._spec())["all"]}

    # --- build / cache -------------------------------------------------
    def _rebuild(self, live: bool = True, interval: float | None = None) -> str:
        html, meta = build_watchlist_html(
            self._spec(), period=self._period, cache_dir=self._cache_dir, served=True,
            public=self._public, bmc_url=self._bmc_url, ttl=self._cache_ttl, live=live,
            interval=interval)
        with self._lock:
            self._html = html
            self._ts = time.time()
            self._refresh = meta["refresh"]
        return html

    def _cold_paint(self) -> str | None:
        """Synchronous, network-free build so a cold/waking host paints the
        cached-snapshot board instantly instead of the warming spinner. It embeds
        a SHORT (1-min) poll interval so the client auto-upgrades to the live
        Finnhub/Yahoo prices within a cycle — no manual reload — then the live
        build's normal cadence takes over."""
        with self._fast_lock:
            if self._html is not None:      # another request already painted it
                return self._html
            try:
                html = self._rebuild(live=False, interval=1.0)   # 60s poll for a fast handoff
            except Exception:  # noqa: BLE001
                return None
            self._ts = 0.0                  # mark stale so the live bg build runs now
            return html

    def _start_bg_build(self) -> None:
        with self._lock:
            if self._building:
                return
            self._building = True

        def run():
            try:
                self._rebuild()
            except Exception:  # noqa: BLE001
                pass
            finally:
                with self._lock:
                    self._building = False
        threading.Thread(target=run, daemon=True).start()

    def html(self, force: bool = False) -> str:
        """Never block the request on a full fetch: return the (stale) board and
        rebuild in the background, or a lightweight 'loading' page until the first
        build finishes. This keeps the hosted app from 502-ing on a slow build."""
        with self._lock:
            fresh = (self._html is not None
                     and (time.time() - self._ts) < self._refresh)
            cached = self._html
        if fresh and not force:
            return cached
        if cached is None:              # cold start / just woke: paint instantly
            cached = self._cold_paint()
        self._start_bg_build()          # live refresh (or first build) in the background
        return cached if cached is not None else _WARMING_HTML

    def wait_ready(self, timeout: float = 0.0) -> bool:
        """Block up to ``timeout`` s for the first board (used at startup)."""
        import time as _t
        self._start_bg_build()
        end = _t.time() + timeout
        while self._html is None and _t.time() < end:
            _t.sleep(0.25)
        return self._html is not None

    # --- mutations -----------------------------------------------------
    def add(self, ticker: str) -> dict:
        t = (ticker or "").strip().upper()
        if not _TICKER_RE.match(t):
            return {"ok": False, "error": f"invalid ticker '{ticker}'"}
        if t in self._current_tickers():
            return {"ok": True, "already": True, "ticker": t}
        # verify it actually has data before committing it to the board
        # Pre-fetch this ONE ticker fully (OHLCV + fundamentals) and cache it, so
        # it isn't starved of fundamentals by rate-limiting during the full-board
        # rebuild — otherwise the new card can land with no valuation (bear/bull).
        from ..watchlist.pipeline import fetch_one
        try:
            td = fetch_one(t, period="5y", cache_dir=self._cache_dir, ttl=0.0)
        except Exception:  # noqa: BLE001
            td = None
        if not (td and (td.ohlcv or {}).get("close")):
            return {"ok": False, "error": f"no data for {t} (unknown ticker?)"}
        with self._lock:
            if t not in self._added:
                self._added.append(t)
            self._html = None            # force a rebuild on next fetch
        self._rebuild()
        return {"ok": True, "ticker": t}

    def remove(self, ticker: str) -> dict:
        t = (ticker or "").strip().upper()
        with self._lock:
            if t in self._added:
                self._added.remove(t)
                self._html = None
            else:
                return {"ok": False, "error": f"{t} is not a user-added ticker"}
        self._rebuild()
        return {"ok": True, "ticker": t}

    def added(self) -> list[str]:
        with self._lock:
            return list(self._added)
