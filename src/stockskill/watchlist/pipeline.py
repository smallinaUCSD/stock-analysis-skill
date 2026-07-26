"""Parallel fetch of OHLCV + fundamentals for a watchlist, with optional cache.

ThreadPoolExecutor because the work is I/O-bound (network). An optional on-disk
pickle cache with a TTL avoids re-fetching every run; a failed ticker never
breaks the batch.
"""

from __future__ import annotations

import os
import pickle
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from ..data import ohlcv, fetch_snapshot
from ..data.fundamentals import FundamentalSnapshot


@dataclass
class TickerData:
    ticker: str
    ohlcv: dict
    snapshot: FundamentalSnapshot | None
    error: str | None = None
    fetched_at: float = 0.0


def _cache_path(cache_dir: str, ticker: str) -> str:
    return os.path.join(cache_dir, f"{ticker}.pkl")


def fetch_one(ticker: str, period: str = "1y",
              cache_dir: str | None = None, ttl: float = 1800.0) -> TickerData:
    if cache_dir:
        p = _cache_path(cache_dir, ticker)
        if os.path.exists(p) and (time.time() - os.path.getmtime(p)) < ttl:
            try:
                with open(p, "rb") as f:
                    return pickle.load(f)
            except Exception:
                pass
    try:
        td = TickerData(ticker, ohlcv(ticker, period), fetch_snapshot(ticker),
                        fetched_at=time.time())
    except Exception as e:  # noqa: BLE001
        td = TickerData(ticker, {k: [] for k in
                                 ("dates", "open", "high", "low", "close", "volume")},
                        None, error=str(e), fetched_at=time.time())
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        try:
            with open(_cache_path(cache_dir, ticker), "wb") as f:
                pickle.dump(td, f)
        except Exception:
            pass
    return td


def fetch_all(tickers: list[str], period: str = "1y", workers: int = 5,
              cache_dir: str | None = None, ttl: float = 1800.0) -> dict[str, TickerData]:
    """Fetch every ticker in parallel. Returns {ticker: TickerData}."""
    out: dict[str, TickerData] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_one, t, period, cache_dir, ttl): t for t in tickers}
        for fut in as_completed(futs):
            td = fut.result()
            out[td.ticker] = td
    # preserve input order
    return {t: out[t] for t in tickers if t in out}
