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
_SPLIT_RE = re.compile(r"[\s,;]+")
MAX_BULK = 50          # tickers per add request
_MAX_JOBS = 20         # finished add-jobs kept for status polling


def parse_ticker_list(value) -> list[str]:
    """'NET, okta  CHKP\\nS' (or a list) -> ['NET', 'OKTA', 'CHKP', 'S'], deduped
    in order. Commas, semicolons, whitespace and newlines all separate."""
    parts = value if isinstance(value, (list, tuple)) else _SPLIT_RE.split(value or "")
    out: list[str] = []
    for p in parts:
        t = str(p or "").strip().upper()
        if t and t not in out:
            out.append(t)
    return out


_WARMING_HTML = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<meta http-equiv='refresh' content='6'><title>Loading…</title>"
    "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500"
    "&family=Source+Serif+4:opsz,wght@8..60,400..500&display=swap'>"
    "<style>body{font-family:'Source Serif 4',Georgia,serif;background:#faf9f5;"
    "color:#141413;text-align:center;padding-top:22vh;margin:0}"
    "@media(prefers-color-scheme:dark){body{background:#181715;color:#faf9f5}p{color:#a09d96!important}}"
    "h2{font-family:'Cormorant Garamond',Georgia,serif;font-weight:500;font-size:36px;letter-spacing:-.02em}"
    ".s{width:34px;height:34px;border:3px solid #e6dfd8;border-top-color:#cc785c;"
    "border-radius:50%;margin:0 auto 18px;animation:sp 1s linear infinite}"
    "@keyframes sp{to{transform:rotate(360deg)}}p{color:#66645e}</style></head>"
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
        self._loaded = False                 # persisted adds restored yet?
        self._html: str | None = None
        self._ts = 0.0
        self._refresh = 1800
        self._building = False
        self._lock = threading.Lock()
        self._fast_lock = threading.Lock()
        # Board generation: bumped on every add/remove. A build records the gen it
        # started from and never replaces a board built from a NEWER gen, so a slow
        # scheduled rebuild can't land after an add and drop the new tickers.
        self._gen = 0
        self._html_gen = -1
        self._jobs: dict[str, dict] = {}     # background add jobs, for status polling
        self._jobs_lock = threading.Lock()

    # --- persistence ---------------------------------------------------
    def _ensure_loaded(self) -> None:
        """Restore adds from the external store ONCE, off the boot path.

        The host's disk is ephemeral, so persisted adds must be reloaded on every
        start - but never inside __init__/create_app: a slow store would block
        worker boot and 502 the health check. This runs in the background build
        (and on the first mutation) instead, and is a no-op when no store is set.
        A transient failure leaves it unloaded so the next build retries."""
        if self._loaded:
            return
        from . import added_store
        if not added_store.enabled():
            self._loaded = True
            return
        persisted = added_store.load_added()
        if persisted is None:                # transient failure - retry next build
            return
        with self._lock:
            merged = list(persisted)
            for t in self._added:            # keep anything added before the load
                if t not in merged:
                    merged.append(t)
            self._added = merged
        self._loaded = True

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
    def _rebuild(self, live: bool = True, interval: float | None = None,
                 quote_max_age: float = 0.0, panels: bool = True,
                 touch_ts: bool = True) -> str:
        with self._lock:
            gen = self._gen
        html, meta = build_watchlist_html(
            self._spec(), period=self._period, cache_dir=self._cache_dir, served=True,
            public=self._public, bmc_url=self._bmc_url, ttl=self._cache_ttl, live=live,
            interval=interval, quote_max_age=quote_max_age, panels=panels)
        with self._lock:
            if gen < self._html_gen:         # a newer board already landed; keep it
                return self._html or html
            self._html = html
            self._html_gen = gen
            self._refresh = meta["refresh"]
            if touch_ts:
                self._ts = time.time()
        return html

    def _quick_rebuild(self) -> str:
        """Incremental rebuild after an add/remove: reuses the cached rows, the
        last Sector/Markets/Macro panels and the live quotes already fetched this
        cadence, so only the NEW tickers hit the network - seconds, not the
        minutes a full re-quote of the board takes through the rate limiter. It
        leaves the refresh clock alone, so the next scheduled full refresh (which
        re-quotes everything) still happens on time."""
        return self._rebuild(live=True, quote_max_age=max(float(self._refresh or 0), 60.0),
                             panels=False, touch_ts=False)

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
                self._ensure_loaded()   # restore persisted adds off the boot path
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
    def _verify(self, t: str) -> bool:
        """Fetch ONE ticker fully (OHLCV + fundamentals) into the cache, so the new
        card lands with its valuation instead of being starved by rate limits
        later. True if it has a price series."""
        from ..watchlist.pipeline import fetch_one
        try:
            td = fetch_one(t, period="5y", cache_dir=self._cache_dir, ttl=0.0)
        except Exception:  # noqa: BLE001
            td = None
        return bool(td and (td.ohlcv or {}).get("close"))

    def add(self, ticker: str) -> dict:
        """Add one ticker and wait for it (verify + incremental rebuild: seconds).
        The board UI uses :meth:`add_bulk`, which returns immediately instead."""
        t = (ticker or "").strip().upper()
        if not _TICKER_RE.match(t):
            return {"ok": False, "error": f"invalid ticker '{ticker}'"}
        self._ensure_loaded()            # merge with persisted before checking dupes
        if t in self._current_tickers():
            return {"ok": True, "already": True, "ticker": t}
        if not self._verify(t):
            info = _explain_failures([t])[0]
            res = {"ok": False, "error": f"{t}: {info['error']}"}
            if info["suggest"]:
                res["suggest"] = info["suggest"]
            if info["retry"]:
                res["retry"] = True
            return res
        self._commit_added([t])
        return {"ok": True, "ticker": t}

    def _commit_added(self, tickers: list[str]) -> None:
        """Append verified tickers, persist once, and rebuild incrementally. The
        current board keeps serving meanwhile (no blank / cold-build window)."""
        with self._lock:
            for t in tickers:
                if t not in self._added:
                    self._added.append(t)
            self._gen += 1
        self._persist()
        try:
            self._quick_rebuild()
        except Exception:  # noqa: BLE001 - the next scheduled build will catch up
            with self._lock:
                self._ts = 0.0

    def add_bulk(self, tickers) -> dict:
        """Queue one or many tickers ('NET, OKTA CHKP') and return immediately.

        Invalid symbols and ones already on the board are reported as skipped;
        the rest are verified in parallel on a background thread (so the board,
        analysis pages and tools stay usable), then added together with a single
        incremental rebuild. Poll :meth:`job_status` for progress."""
        items = parse_ticker_list(tickers)
        if not items:
            return {"ok": False, "error": "no tickers given"}
        if len(items) > MAX_BULK:
            return {"ok": False, "error": f"too many tickers ({len(items)}); max {MAX_BULK} per add"}
        self._ensure_loaded()
        current = self._current_tickers()
        queued, skipped = [], []
        for t in items:
            if not _TICKER_RE.match(t):
                skipped.append({"ticker": t, "reason": "not a valid symbol"})
            elif t in current:
                skipped.append({"ticker": t, "reason": "already on the board"})
            else:
                queued.append(t)
        import uuid
        job = {"id": uuid.uuid4().hex[:10], "state": "running" if queued else "done",
               "total": len(queued), "done": 0, "added": [], "failed": [],
               "skipped": skipped, "started": time.time()}
        with self._jobs_lock:
            self._jobs[job["id"]] = job
            if len(self._jobs) > _MAX_JOBS:    # drop the oldest finished jobs
                old = sorted((j for j in self._jobs.values() if j["state"] == "done"),
                             key=lambda j: j["started"])
                for j in old[:len(self._jobs) - _MAX_JOBS]:
                    self._jobs.pop(j["id"], None)
        if queued:
            threading.Thread(target=self._run_add_job, args=(job["id"], queued),
                             daemon=True).start()
        return {"ok": True, "job": job["id"], "queued": queued, "skipped": skipped}

    def _run_add_job(self, job_id: str, tickers: list[str]) -> None:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        good: list[str] = []
        bad: list[str] = []
        with ThreadPoolExecutor(max_workers=min(4, len(tickers))) as ex:
            futs = {ex.submit(self._verify, t): t for t in tickers}
            for f in as_completed(futs):
                t = futs[f]
                try:
                    ok = bool(f.result())
                except Exception:  # noqa: BLE001
                    ok = False
                with self._jobs_lock:
                    job = self._jobs.get(job_id)
                    if job is not None:
                        job["done"] += 1
                        if ok:
                            job["added"].append(t)
                (good if ok else bad).append(t)
        if bad:                                # explain misses: typo vs provider outage
            failed = _explain_failures(sorted(bad, key=tickers.index))
            with self._jobs_lock:
                if job_id in self._jobs:
                    self._jobs[job_id]["failed"] = failed
        if good:
            with self._jobs_lock:
                if job_id in self._jobs:
                    self._jobs[job_id]["state"] = "building"
            good.sort(key=tickers.index)       # keep the order the user typed
            self._commit_added(good)
        with self._jobs_lock:
            if job_id in self._jobs:
                self._jobs[job_id]["state"] = "done"

    def job_status(self, job_id: str) -> dict | None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {**job, "added": list(job["added"]), "failed": list(job["failed"]),
                    "skipped": list(job["skipped"])}

    def remove(self, ticker: str) -> dict:
        t = (ticker or "").strip().upper()
        self._ensure_loaded()
        with self._lock:
            if t not in self._added:
                return {"ok": False, "error": f"{t} is not a user-added ticker"}
            self._added.remove(t)
            self._gen += 1
        self._persist()
        try:
            self._quick_rebuild()
        except Exception:  # noqa: BLE001
            with self._lock:
                self._ts = 0.0
        return {"ok": True, "ticker": t}

    def _persist(self) -> None:
        """Best-effort write of the added list to the external store so it
        survives restarts. A no-op when no store is configured."""
        from . import added_store
        with self._lock:
            snapshot = list(self._added)
        added_store.save_added(snapshot)

    def added(self) -> list[str]:
        with self._lock:
            return list(self._added)


_UNAVAILABLE = ("couldn't verify right now - the data providers are rate-limited; "
                "try again later")


def _providers_up() -> bool:
    """Can we fetch ANY price right now? Separates 'no such ticker' from 'the data
    providers are rate-limited or down', so real tickers aren't reported as not
    found during an outage. One cheap call, made only when something failed."""
    try:
        from ..data import ohlcv
        return bool((ohlcv("SPY", "5d") or {}).get("close"))
    except Exception:  # noqa: BLE001
        return False


def _explain_failures(tickers: list[str]) -> list[dict]:
    """Per-ticker failure info: a retryable 'providers unavailable' during an
    outage, else 'no data' with a 'did you mean' suggestion."""
    if not tickers:
        return []
    if not _providers_up():
        return [{"ticker": t, "error": _UNAVAILABLE, "suggest": None, "retry": True}
                for t in tickers]
    return [{"ticker": t, "error": "no data (unknown ticker?)", "suggest": _suggest(t),
             "retry": False} for t in tickers]


def _suggest(t: str) -> dict | None:
    """Best-effort 'did you mean' for a ticker that returned no data: the top US
    symbol-search hit that differs from what was typed (FTNET -> FTNT,
    SPACEX -> SPCX). None if search is unavailable or finds nothing better."""
    try:
        from ..data.search import search_symbols
        for r in search_symbols(t) or []:
            sym = (r.get("symbol") or "").upper()
            if sym and sym != t and "." not in sym:      # skip foreign listings (.TO, .SA)
                return {"symbol": sym, "name": (r.get("name") or "")[:60]}
    except Exception:  # noqa: BLE001
        pass
    return None
