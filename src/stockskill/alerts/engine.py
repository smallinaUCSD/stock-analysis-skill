"""Alert engine: derive alerts from watchlist rows + custom alerts.json.

Auto alerts come straight off the already-computed TickerRow flags/signal.
Custom alerts are user-defined threshold conditions. Everything is pure over
the rows -- no network, no recomputation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Alert:
    ticker: str
    kind: str       # e.g. "52w_high", "surge", "signal_buy", "custom:price_above"
    message: str
    emoji: str


# ---- auto alerts from row flags / signal ---- #
def auto_alerts(rows) -> list[Alert]:
    out: list[Alert] = []
    for r in rows:
        if r.price is None:
            continue
        day = r.changes.get("1d")
        if "near_52w_high" in r.flags:
            out.append(Alert(r.ticker, "52w_high", f"{r.ticker} near 52-week high", "🔥"))
        if "near_52w_low" in r.flags:
            out.append(Alert(r.ticker, "52w_low", f"{r.ticker} near 52-week low", "📉"))
        if "surge" in r.flags and day is not None:
            out.append(Alert(r.ticker, "surge", f"{r.ticker} surging {day:+.1%}", "🚀"))
        if "crash" in r.flags and day is not None:
            out.append(Alert(r.ticker, "crash", f"{r.ticker} down {day:+.1%}", "⚠️"))
        if "vol_spike" in r.flags:
            out.append(Alert(r.ticker, "vol_spike", f"{r.ticker} volume spike", "📊"))
        if "squeeze" in r.flags:
            out.append(Alert(r.ticker, "squeeze", f"{r.ticker} BB squeeze", "🎯"))
        if r.signal == "BUY":
            out.append(Alert(r.ticker, "signal_buy", f"{r.ticker}: BUY signal", "💚"))
        elif r.signal == "SELL":
            out.append(Alert(r.ticker, "signal_sell", f"{r.ticker}: SELL signal", "🧡"))
        elif r.signal == "SHORT":
            out.append(Alert(r.ticker, "signal_short", f"{r.ticker}: SHORT signal", "❤️"))
    return out


# ---- custom alerts from alerts.json ---- #
def load_custom_alerts(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _custom_met(row, cond: str, value) -> str | None:
    """Return a message if the condition is met, else None."""
    price = row.price
    day = row.changes.get("1d")
    day_pct = None if day is None else day * 100.0
    checks = {
        "price_above": (price is not None and value is not None and price > value,
                        f"{row.ticker} above ${value}"),
        "price_below": (price is not None and value is not None and price < value,
                        f"{row.ticker} below ${value}"),
        "day_change_above": (day_pct is not None and value is not None and day_pct > value,
                             f"{row.ticker} up {day_pct:+.1f}% (> {value}%)"),
        "day_change_below": (day_pct is not None and value is not None and day_pct < value,
                             f"{row.ticker} down {day_pct:+.1f}% (< {value}%)"),
        "rsi_oversold": (row.rsi is not None and row.rsi <= 30, f"{row.ticker} RSI oversold"),
        "rsi_overbought": (row.rsi is not None and row.rsi >= 70, f"{row.ticker} RSI overbought"),
        "volume_spike": (row.vol_spike, f"{row.ticker} volume spike"),
        "buy": (row.signal == "BUY", f"{row.ticker}: BUY signal"),
        "sell": (row.signal == "SELL", f"{row.ticker}: SELL signal"),
        "short": (row.signal == "SHORT", f"{row.ticker}: SHORT signal"),
    }
    met, msg = checks.get(cond, (False, ""))
    return msg if met else None


def custom_alerts(rows, defs: list[dict]) -> list[Alert]:
    by_ticker = {r.ticker: r for r in rows}
    out: list[Alert] = []
    for d in defs:
        tk = str(d.get("ticker", "")).upper()
        cond = d.get("condition", "")
        row = by_ticker.get(tk)
        if row is None or row.price is None:
            continue
        msg = _custom_met(row, cond, d.get("value"))
        if msg:
            out.append(Alert(tk, f"custom:{cond}", msg, "🔔"))
    return out


def all_alerts(rows, custom_defs: list[dict] | None = None) -> list[Alert]:
    """Custom alerts first (user-prioritized), then auto alerts."""
    return custom_alerts(rows, custom_defs or []) + auto_alerts(rows)
