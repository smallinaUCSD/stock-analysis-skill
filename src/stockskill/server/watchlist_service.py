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


class WatchlistService:
    def __init__(self, tickers_path: str = "data/tickers.csv", cache_dir: str | None = None):
        self._path = tickers_path
        self._cache_dir = cache_dir
        self._added: list[str] = []          # user-added, in order
        self._html: str | None = None
        self._ts = 0.0
        self._refresh = 1800
        self._lock = threading.Lock()

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
    def _rebuild(self) -> str:
        html, meta = build_watchlist_html(
            self._spec(), cache_dir=self._cache_dir, served=True)
        with self._lock:
            self._html = html
            self._ts = time.time()
            self._refresh = meta["refresh"]
        return html

    def html(self, force: bool = False) -> str:
        with self._lock:
            fresh = (self._html is not None
                     and (time.time() - self._ts) < self._refresh)
            cached = self._html
        if fresh and not force:
            return cached
        return self._rebuild()

    # --- mutations -----------------------------------------------------
    def add(self, ticker: str) -> dict:
        t = (ticker or "").strip().upper()
        if not _TICKER_RE.match(t):
            return {"ok": False, "error": f"invalid ticker '{ticker}'"}
        if t in self._current_tickers():
            return {"ok": True, "already": True, "ticker": t}
        # verify it actually has data before committing it to the board
        from ..data.prices import closing_prices
        try:
            closes = closing_prices(t, "1mo")
        except Exception:  # noqa: BLE001
            closes = []
        if not closes:
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
