"""Trend indicators: moving averages, golden/death cross, MACD, ADX."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def _series(x) -> pd.Series:
    return pd.Series(list(x), dtype="float64")


def sma(closes, period: int) -> float | None:
    s = _series(closes)
    if len(s) < period:
        return None
    return float(s.iloc[-period:].mean())


def ema(closes, period: int) -> float | None:
    s = _series(closes)
    if len(s) < period:
        return None
    return float(s.ewm(span=period, adjust=False).mean().iloc[-1])


def golden_death_cross(closes, fast: int = 50, slow: int = 200,
                       lookback: int = 3) -> str | None:
    """Detect a recent SMA(fast) x SMA(slow) crossover.

    Returns "golden" if fast crossed **above** slow within ``lookback`` bars,
    "death" if it crossed below, else None. Needs > slow bars of data.
    """
    s = _series(closes)
    if len(s) < slow + lookback + 1:
        return None
    f = s.rolling(fast).mean()
    sl = s.rolling(slow).mean()
    diff = (f - sl)
    recent = diff.iloc[-(lookback + 1):].reset_index(drop=True)
    crossed_up = (recent.iloc[0] <= 0) and (recent.iloc[-1] > 0)
    crossed_down = (recent.iloc[0] >= 0) and (recent.iloc[-1] < 0)
    if crossed_up:
        return "golden"
    if crossed_down:
        return "death"
    return None


@dataclass
class MACDResult:
    macd: float
    signal: float
    histogram: float
    state: str   # "bullish" | "bearish" | "bull_cross" | "bear_cross"


def macd(closes, fast: int = 12, slow: int = 26, signal: int = 9) -> MACDResult | None:
    """MACD line, signal line, histogram, and crossover state."""
    s = _series(closes)
    if len(s) < slow + signal:
        return None
    macd_line = s.ewm(span=fast, adjust=False).mean() - s.ewm(span=slow, adjust=False).mean()
    sig = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - sig
    h_now, h_prev = hist.iloc[-1], hist.iloc[-2]
    if h_prev <= 0 < h_now:
        state = "bull_cross"
    elif h_prev >= 0 > h_now:
        state = "bear_cross"
    else:
        state = "bullish" if h_now > 0 else "bearish"
    return MACDResult(float(macd_line.iloc[-1]), float(sig.iloc[-1]),
                      float(h_now), state)


def adx(highs, lows, closes, period: int = 14) -> float | None:
    """Average Directional Index (trend strength, 0-100). >25 = trending."""
    h, l, c = _series(highs), _series(lows), _series(closes)
    if len(c) < 2 * period + 1:
        return None
    up = h.diff()
    down = -l.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr = pd.concat([(h - l).abs(), (h - c.shift()).abs(), (l - c.shift()).abs()],
                   axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, float("nan"))
    adx_series = dx.ewm(alpha=1.0 / period, adjust=False).mean()
    v = adx_series.iloc[-1]
    return None if pd.isna(v) else float(v)
