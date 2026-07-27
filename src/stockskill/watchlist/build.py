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
        return "—"
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


def build_watchlist_html(tickers_spec, *, period: str = "5y", workers: int = 5,
                         cache_dir: str | None = None, alerts_path: str | None = None,
                         interval: float | None = None, served: bool = False,
                         title: str = "Watchlist") -> tuple[str, dict]:
    """Return ``(html, meta)`` for the watchlist board.

    ``tickers_spec`` is anything :func:`parse_tickers` accepts (a path or a
    string of sectioned tickers). ``served=True`` turns on the live add-ticker
    box (needs the Flask API behind it).
    """
    import os
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

    data = fetch_all(tickers, period=period, workers=workers, cache_dir=cache_dir)
    cfg = SignalConfig.from_env()
    rows = [build_row(data[t], cfg, tag_map.get(t)) for t in tickers if t in data]
    custom = load_custom_alerts(alerts_path) if alerts_path else []
    alerts = all_alerts(rows, custom)

    sec_pm = price_map(list(SECTOR_ETFS), period="3mo")
    sectors = [(r.name, r.ticker, r.returns.get("1m")) for r in sector_table(sec_pm, "1m")]
    mkt_pm = price_map(all_market_tickers(), period="5d")
    markets = market_quotes(mkt_pm)
    macro = _macro_panel()

    # Keep the last good panel data so a failed/rate-limited fetch doesn't blank
    # the Sector / Markets / Macro panels (in memory + on disk when cached).
    _panels_load(cache_dir)
    sectors = _keep_good("sectors", sectors, lambda s: any(r is not None for _, _, r in s))
    markets = _keep_good("markets", markets, lambda m: any(q.last is not None for q in m))
    macro = _keep_good("macro", macro, lambda mc: bool(mc.get("indicators") or mc.get("events")))
    _panels_save(cache_dir)

    status = market_status()
    refresh = refresh_seconds_for(status, interval)
    now = datetime.now(ET)
    html_out = render_watchlist(
        rows, title=title, updated=now.strftime("%a %b %d, %I:%M %p") + " ET",
        updated_ts=int(now.timestamp() * 1000),
        status_badge=status.badge, status_label=status.label, alerts=alerts,
        sectors=sectors, markets=markets, macro=macro,
        refresh_seconds=refresh, served=served)
    ok = sum(1 for r in rows if r.price is not None)
    meta = {"status": status, "refresh": refresh, "ok": ok, "n": len(rows),
            "line": f"[{status.badge}] ({ok}/{len(rows)} tickers), reload {refresh}s"}
    return html_out, meta
