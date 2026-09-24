"""OHLCV shaping for candlestick charts: trim to a period and resample daily
bars to weekly ones when there are too many to draw legibly."""

from __future__ import annotations

from datetime import date

PERIOD_BARS = {"1mo": 21, "3mo": 63, "6mo": 126, "1y": 252, "2y": 504, "5y": 1260}


def _iso(d) -> str:
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def slice_period(o: dict, period: str) -> dict:
    """The last ``period`` of bars from an OHLCV dict (all keys trimmed alike)."""
    n = PERIOD_BARS.get(period)
    keys = ("dates", "open", "high", "low", "close", "volume")
    if not n:
        return {k: list(o.get(k) or []) for k in keys}
    return {k: list((o.get(k) or [])[-(n + 1):]) for k in keys}


def weekly(o: dict) -> dict:
    """Resample daily OHLCV to ISO weeks: first open, max high, min low, last
    close, summed volume. Each bar is dated by its last trading day."""
    out = {k: [] for k in ("dates", "open", "high", "low", "close", "volume")}
    dates = o.get("dates") or []
    cur = None
    for i, d in enumerate(dates):
        iso = _iso(d)
        y, m, dd = (int(x) for x in iso[:10].split("-"))
        wk = date(y, m, dd).isocalendar()[:2]
        op, hi, lo, cl = o["open"][i], o["high"][i], o["low"][i], o["close"][i]
        vol = (o.get("volume") or [0] * len(dates))[i] or 0
        if wk != cur:
            cur = wk
            out["dates"].append(iso)
            out["open"].append(op)
            out["high"].append(hi)
            out["low"].append(lo)
            out["close"].append(cl)
            out["volume"].append(vol)
        else:
            out["dates"][-1] = iso
            out["high"][-1] = max(out["high"][-1], hi)
            out["low"][-1] = min(out["low"][-1], lo)
            out["close"][-1] = cl
            out["volume"][-1] += vol
    return out


def chart_bars(o: dict, period: str, max_daily: int = 300) -> dict:
    """OHLCV for a candlestick chart: the period's bars, weekly when there are
    more than ``max_daily`` of them. Adds ``interval`` ("1d" or "1wk")."""
    s = slice_period(o, period)
    if len(s["dates"]) > max_daily:
        s = weekly(s)
        s["interval"] = "1wk"
    else:
        s["dates"] = [_iso(d) for d in s["dates"]]
        s["interval"] = "1d"
    return s
