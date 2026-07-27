"""Build the watchlist dashboard HTML from a ticker spec.

Shared by the CLI (`watchlist` writes it to a file for cron/Pages) and the
Flask server (`serve` renders it live). All numbers come from tested Python;
this module only orchestrates fetch -> rows -> render.
"""

from __future__ import annotations

from datetime import datetime


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

    status = market_status()
    refresh = refresh_seconds_for(status, interval)
    now = datetime.now(ET)
    html_out = render_watchlist(
        rows, title=title, updated=now.strftime("%a %b %d, %I:%M %p") + " ET",
        updated_ts=int(now.timestamp() * 1000),
        status_badge=status.badge, status_label=status.label, alerts=alerts,
        sectors=sectors, markets=markets, refresh_seconds=refresh, served=served)
    ok = sum(1 for r in rows if r.price is not None)
    meta = {"status": status, "refresh": refresh, "ok": ok, "n": len(rows),
            "line": f"[{status.badge}] ({ok}/{len(rows)} tickers), reload {refresh}s"}
    return html_out, meta
