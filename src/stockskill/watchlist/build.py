"""Build the watchlist dashboard HTML from a ticker spec.

Shared by the CLI (`watchlist` writes it to a file for cron/Pages) and the
Flask server (`serve` renders it live). All numbers come from tested Python;
this module only orchestrates fetch -> rows -> render.
"""

from __future__ import annotations

from datetime import datetime

# last good Sector / Markets / Macro panel data, so a rate-limited fetch reuses
# the previous values instead of showing "unavailable". Held in memory and, when
# a cache dir is configured, persisted to disk so it also survives a restart.
_LAST_GOOD: dict = {}
_PANEL_KEYS = ("sectors", "markets", "macro")


def _keep_good(key: str, value, is_good):
    """Return ``value`` if it looks good and remember it; else the last good one."""
    try:
        ok = value is not None and is_good(value)
    except Exception:  # noqa: BLE001
        ok = False
    if ok:
        _LAST_GOOD[key] = value
        return value
    return _LAST_GOOD.get(key, value)


def _panel_cache_file(cache_dir: str) -> str:
    import os
    return os.path.join(cache_dir, "_panels.pkl")


def _panels_load(cache_dir: str | None) -> None:
    """Seed the in-memory panel cache from disk once (survives a restart)."""
    if not cache_dir or _LAST_GOOD.get("_loaded"):
        return
    _LAST_GOOD["_loaded"] = True
    import os
    import pickle
    p = _panel_cache_file(cache_dir)
    if os.path.exists(p):
        try:
            with open(p, "rb") as f:
                data = pickle.load(f)
            for k in _PANEL_KEYS:
                if k in data and k not in _LAST_GOOD:
                    _LAST_GOOD[k] = data[k]
        except Exception:  # noqa: BLE001
            pass


def _panels_save(cache_dir: str | None) -> None:
    if not cache_dir:
        return
    import os
    import pickle
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(_panel_cache_file(cache_dir), "wb") as f:
            pickle.dump({k: _LAST_GOOD[k] for k in _PANEL_KEYS if k in _LAST_GOOD}, f)
    except Exception:  # noqa: BLE001
        pass


# rate / volatility gauges shown in the Macro panel
_MACRO_INDICATORS = [("^VIX", "VIX (CBOE)"), ("^VVIX", "VVIX (vol of vol)"),
                     ("^TNX", "10Y Yield"), ("DX-Y.NYB", "Dollar (DXY)")]


def _fmt_macro(ticker: str, value: float | None) -> str:
    if value is None:
        return "n/a"
    if ticker == "^TNX":                       # CBOE 10Y yield index (yield×10)
        return f"{(value / 10 if value > 20 else value):.2f}%"
    return f"{value:,.1f}"


def _macro_panel() -> dict:
    """Macro trends for the dedicated panel: rate/vol gauges, the next Fed
    decision, and scanned market-event headlines. Best-effort — never fatal.
    """
    from ..data.macro import next_fomc, scan_headlines
    from ..data.news import fetch_news
    from ..technicals.changes import pct_change

    indicators = []
    try:
        from ..data.prices import price_map
        pm = price_map([t for t, _ in _MACRO_INDICATORS], period="5d")
        for tk, name in _MACRO_INDICATORS:
            cl = pm.get(tk) or []
            last = cl[-1] if cl else None
            indicators.append({"name": name, "display": _fmt_macro(tk, last),
                               "change": pct_change(cl, 1)})
    except Exception:  # noqa: BLE001
        indicators = []

    items = []
    for tk in ("^GSPC", "SPY"):
        try:
            items = fetch_news(tk, limit=20)
        except Exception:  # noqa: BLE001
            items = []
        if items:
            break
    url_by_title = {i["title"].strip(): i.get("url", "") for i in items}
    events = []
    for a in scan_headlines([i["title"] for i in items], limit=6):
        events.append({"kind": a.kind, "emoji": a.emoji, "title": a.message,
                       "url": url_by_title.get(a.message.strip(), "")})

    fear_greed = None
    try:
        from ..pulse import fetch_fear_greed
        fg = fetch_fear_greed()
        if fg:
            fear_greed = {"score": fg.score, "rating": fg.rating}
    except Exception:  # noqa: BLE001
        fear_greed = None

    return {"indicators": indicators, "fomc": next_fomc(), "events": events,
            "fear_greed": fear_greed}


def _attach_factors(rows, data) -> None:
    """Compute cross-sectional factor scores (value/quality/momentum/…) for the
    board and hang a compact read on each row. Network-free (uses the cached
    snapshot + price history), so it runs on the fast cold-start build too. Never
    raises into the build."""
    from ..factors.model import (factor_metrics, momentum_12_1, annualized_vol,
                                 score_factors, weights_from_env)
    try:
        metric_rows = []
        for r in rows:
            td = data.get(r.ticker)
            if not (td and td.snapshot):
                continue
            closes = (td.ohlcv or {}).get("close", [])
            metric_rows.append(factor_metrics(td.snapshot, momentum_12_1(closes),
                                              annualized_vol(closes)))
        if not metric_rows:
            return
        scores = {s.ticker: s for s in score_factors(
            metric_rows, weights=weights_from_env(), sector_neutral=True)}
        for r in rows:
            s = scores.get(r.ticker)
            if s:
                r.factor = {"label": s.label, "composite": s.composite_pct,
                            "value": s.factor_pct.get("value"),
                            "quality": s.factor_pct.get("quality"),
                            "momentum": s.factor_pct.get("momentum")}
    except Exception:  # noqa: BLE001 - factors are a nice-to-have, never break the board
        return


def _attach_risk(rows, data, benches) -> None:
    """Beta/alpha/Sharpe/drawdown vs SPY and QQQ on each row (pure math over the
    cached price history). Beta shown on the board is the Welch estimate vs SPY,
    falling back to the vendor's when there's no benchmark. Never raises."""
    if not benches:
        return
    from ..performance.benchmarks import risk_vs_benchmarks
    for r in rows:
        td = data.get(r.ticker)
        if not td:
            continue
        try:
            r.risk = risk_vs_benchmarks(td, benches)
        except Exception:  # noqa: BLE001
            continue
        spy = r.risk.get("SPY") or {}
        if spy.get("beta") is not None:
            r.beta = spy["beta"]


# Last live quote per ticker: {TICKER: (fetched_at, quote)}. Lets a rebuild that
# was triggered by ADDING tickers fetch only the new names instead of re-pulling
# the whole board through the rate-limited quote API (which took minutes and
# starved every other request of quota). Also a stale-while-error fallback: a
# ticker whose quote fails keeps its last live price rather than the snapshot's.
_QUOTES: dict[str, tuple[float, dict]] = {}


def _overlay_live_prices(rows, status, max_age: float = 0.0) -> None:
    """Patch rows' price + 1d change from a live quote source in EVERY session.

    Finnhub returns the live price while the market is open and the *last regular
    close* when it is shut, so overlaying in all sessions keeps the card price
    current (today's or yesterday's close) instead of falling back to the
    days-old committed snapshot overnight/on weekends. Prefers Finnhub (free
    real-time US quotes, whole board); falls back to FMP's multi-symbol batch
    (paid FMP plan).

    ``max_age`` (seconds): reuse a cached quote younger than this and fetch only
    the rest. 0 (the scheduled refresh) re-fetches every ticker."""
    import time
    from ..data import finnhub, fmp

    now = time.time()
    need = []
    for r in rows:
        hit = _QUOTES.get(r.ticker.upper())
        if hit is None or now - hit[0] >= max_age:
            need.append(r.ticker.upper())
    fetched: dict = {}
    if need:
        try:
            if finnhub.has_finnhub():
                fetched = finnhub.batch_quotes(need)
            elif fmp.has_fmp():
                fetched = fmp.batch_quotes(need)
        except Exception:  # noqa: BLE001
            fetched = {}
    for t, q in (fetched or {}).items():
        if q and q.get("price"):
            _QUOTES[t.upper()] = (now, q)
    for r in rows:
        hit = _QUOTES.get(r.ticker.upper())
        q = hit[1] if hit else None
        if q and q.get("price"):
            r.price = q["price"]
            if q.get("change_pct") is not None:
                r.changes["1d"] = q["change_pct"]


def _apply_ext_prices(rows, status, live: bool = True) -> None:
    """Extended-hours (pre/post-market) price on the hosted board.

    Finnhub free returns the regular close during extended hours, so during a
    pre/after-hours session we source a FRESH ext price from Yahoo (which carries
    it) — best-effort, since Yahoo may rate-limit the host. Any name without a
    fresh ext price has it cleared, so a stale snapshot value never shows. Only
    fetched on the live build (never the network-free cold-start). Local yfinance
    (no API keys) keeps the snapshot's freshly-fetched ext price."""
    from ..data import finnhub, fmp
    if not (finnhub.has_finnhub() or fmp.has_fmp()):
        return                                    # local: keep the snapshot's fresh ext
    fresh: dict = {}
    # Fetch whenever the regular session is NOT open (pre-market, after-hours,
    # overnight/weekend "closed"): Yahoo's marketState decides whether there's a
    # pre/post price to show, so the most recent extended-hours price keeps showing
    # after 8pm ET and over the weekend. Never on the network-free fast build.
    if live and status.label != "open":
        try:
            from ..data import yahoo_ext
            fresh = yahoo_ext.ext_quotes([r.ticker for r in rows])
        except Exception:  # noqa: BLE001
            fresh = {}
    for r in rows:
        q = fresh.get(r.ticker.upper())
        if q and q.get("ext_price"):
            r.ext_price = q["ext_price"]
            r.ext_change = q.get("ext_change")
            r.market_state = q.get("market_state")
        else:
            r.ext_price = None
            r.ext_change = None


def build_watchlist_html(tickers_spec, *, period: str = "5y", workers: int = 5,
                         cache_dir: str | None = None, alerts_path: str | None = None,
                         interval: float | None = None, served: bool = False,
                         title: str = "Watchlist", public: bool = False,
                         bmc_url: str | None = None, ttl: float = 1800.0,
                         live: bool = True, quote_max_age: float = 0.0,
                         panels: bool = True) -> tuple[str, dict]:
    """Return ``(html, meta)`` for the watchlist board.

    ``tickers_spec`` is anything :func:`parse_tickers` accepts (a path or a
    string of sectioned tickers). ``served=True`` turns on the live add-ticker
    box (needs the Flask API behind it).

    ``live=False`` renders a fast, network-free board straight from the cached
    snapshot: it skips the Yahoo panel fetches and the Finnhub price overlay, so
    a waking host can paint the board instantly and refresh live in the
    background (avoids the cold-start warming spinner).

    ``quote_max_age`` / ``panels=False`` make a cheap *incremental* live build
    (used after adding tickers): reuse live quotes younger than ``quote_max_age``
    and the last Sector/Markets/Macro panels, fetching only what's new.
    """
    import os
    import time
    from ..marketclock import market_status, refresh_seconds_for, ET
    from ..signals import SignalConfig
    from . import fetch_all, build_row, render_watchlist
    from .tickers import parse_tickers, parse_tickers_text
    from ..alerts import all_alerts, load_custom_alerts
    from ..pulse import (SECTOR_ETFS, sector_table, market_quotes,
                         all_market_tickers)
    from ..data.prices import price_map

    if isinstance(tickers_spec, str) and "\n" not in tickers_spec and os.path.isfile(tickers_spec):
        parsed = parse_tickers(tickers_spec)
    else:
        parsed = parse_tickers_text(tickers_spec)
    tickers = parsed["all"]
    tag_map: dict[str, set] = {}
    for sec, tks in parsed["sections"].items():
        for t in tks:
            tag_map.setdefault(t, set()).add(sec)

    data = fetch_all(tickers, period=period, workers=workers, cache_dir=cache_dir, ttl=ttl)
    cfg = SignalConfig.from_env()
    # Build rows, yielding the CPU periodically on the served board: the first
    # (uncached) build runs the heavy per-ticker models, and on a small shared-CPU
    # host that must not monopolise the core or the health check times out and the
    # worker is killed. Cached rebuilds are cheap, so the sleeps are negligible.
    rows = []
    for i, t in enumerate(tickers):
        if t not in data:
            continue
        rows.append(build_row(data[t], cfg, tag_map.get(t)))
        if served and i % 6 == 5:
            time.sleep(0.01)
    _attach_factors(rows, data)
    custom = load_custom_alerts(alerts_path) if alerts_path else []
    alerts = all_alerts(rows, custom)

    if live and panels:
        sec_pm = price_map(list(SECTOR_ETFS), period="3mo")
        sectors = [(r.name, r.ticker, r.returns.get("1m")) for r in sector_table(sec_pm, "1m")]
        mkt_pm = price_map(all_market_tickers(), period="5d")
        markets = market_quotes(mkt_pm)
        macro = _macro_panel()
    else:
        # Fast path: don't touch Yahoo; fall through to the cached panels below.
        sectors, markets, macro = [], [], {}

    # Benchmarks for beta/alpha: refreshed with the panels on a full live build,
    # read from the cache otherwise (the fast and incremental builds stay offline).
    from ..performance.benchmarks import load_benchmarks
    _attach_risk(rows, data, load_benchmarks(cache_dir, period, ttl,
                                             fetch=live and panels, have=data))

    # Keep the last good panel data so a failed/rate-limited fetch doesn't blank
    # the Sector / Markets / Macro panels (in memory + on disk when cached).
    _panels_load(cache_dir)
    sectors = _keep_good("sectors", sectors, lambda s: any(r is not None for _, _, r in s))
    markets = _keep_good("markets", markets, lambda m: any(q.last is not None for q in m))
    macro = _keep_good("macro", macro, lambda mc: bool(mc.get("indicators") or mc.get("events")))
    _panels_save(cache_dir)

    status = market_status()
    refresh = refresh_seconds_for(status, interval)

    # Live-price overlay (served board only): patch the cached rows with one
    # FMP batch-quote call so prices/day-change update on the 15/30-min cadence
    # without a full per-ticker refetch. The heavy data (valuation, history,
    # signals) stays from the snapshot; only price and 1d change go live.
    if served and live:
        _overlay_live_prices(rows, status, max_age=quote_max_age)
    if served:
        _apply_ext_prices(rows, status, live=live)   # Yahoo ext during extended sessions

    now = datetime.now(ET)
    html_out = render_watchlist(
        rows, title=title, updated=now.strftime("%a %b %d, %I:%M %p") + " ET",
        updated_ts=int(now.timestamp() * 1000),
        status_badge=status.badge, status_label=status.label, alerts=alerts,
        sectors=sectors, markets=markets, macro=macro,
        refresh_seconds=refresh, served=served, public=public, bmc_url=bmc_url)
    ok = sum(1 for r in rows if r.price is not None)
    meta = {"status": status, "refresh": refresh, "ok": ok, "n": len(rows),
            "line": f"[{status.badge}] ({ok}/{len(rows)} tickers), reload {refresh}s"}
    return html_out, meta
