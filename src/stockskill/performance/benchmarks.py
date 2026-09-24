"""Benchmark price series (SPY, QQQ) for beta/alpha, shared through the same
on-disk cache as every other ticker."""

from __future__ import annotations

BENCHMARKS = {"SPY": "S&P 500", "QQQ": "Nasdaq-100"}


def load_benchmarks(cache_dir: str | None, period: str = "5y", ttl: float = 1800.0,
                    fetch: bool = False, have: dict | None = None) -> dict:
    """{symbol: TickerData} for the benchmarks that have prices.

    ``have`` (e.g. the board's own fetched data) is used first. Otherwise
    ``fetch=True`` goes through the cached fetcher (network only when the cache is
    stale); ``fetch=False`` reads the cache and never touches the network."""
    from ..watchlist.pipeline import _load_cached, fetch_one
    out = {}
    for sym in BENCHMARKS:
        td = (have or {}).get(sym)
        if td is None:
            try:
                if fetch:
                    td = fetch_one(sym, period=period, cache_dir=cache_dir, ttl=ttl)
                elif cache_dir:
                    td = _load_cached(cache_dir, sym)
            except Exception:  # noqa: BLE001 - a benchmark is a nice-to-have
                td = None
        if td is not None and (td.ohlcv or {}).get("close"):
            out[sym] = td
    return out


def risk_vs_benchmarks(td, benches: dict) -> dict:
    """{benchmark: RiskStats.to_dict()} for one ticker's TickerData."""
    from .metrics import risk_stats
    o = td.ohlcv or {}
    out = {}
    for sym, b in benches.items():
        if sym == td.ticker:
            continue
        ob = b.ohlcv or {}
        rs = risk_stats(o.get("dates"), o.get("close"), ob.get("dates"), ob.get("close"),
                        benchmark=sym)
        if rs:
            out[sym] = rs.to_dict()
    return out
