"""Volatility indicators: Bollinger Bands, ATR, historical volatility."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


def _series(x) -> pd.Series:
    return pd.Series(list(x), dtype="float64")


@dataclass
class BollingerBands:
    upper: float
    middle: float
    lower: float
    position_pct: float   # where price sits in the band: 0 = lower, 100 = upper
    width_pct: float      # (upper-lower)/middle * 100
    squeeze: bool         # width at/near a recent low


def bollinger(closes, period: int = 20, num_std: float = 2.0,
              squeeze_lookback: int = 120, squeeze_quantile: float = 0.25) -> BollingerBands | None:
    """Bollinger Bands + position%, width%, and squeeze detection.

    Squeeze = current band width in the bottom ``squeeze_quantile`` of the last
    ``squeeze_lookback`` bars (a volatility contraction that often precedes a move).
    """
    s = _series(closes)
    if len(s) < period:
        return None
    mid = s.rolling(period).mean()
    sd = s.rolling(period).std(ddof=0)
    upper = mid + num_std * sd
    lower = mid - num_std * sd
    u, m, lo = upper.iloc[-1], mid.iloc[-1], lower.iloc[-1]
    price = s.iloc[-1]
    band = u - lo
    position = 50.0 if band == 0 else float((price - lo) / band * 100.0)
    width = (upper - lower) / mid.replace(0.0, float("nan")) * 100.0
    w_now = width.iloc[-1]
    recent = width.dropna().iloc[-squeeze_lookback:]
    squeeze = bool(len(recent) > 5 and w_now <= recent.quantile(squeeze_quantile))
    return BollingerBands(float(u), float(m), float(lo), position,
                          float(w_now), squeeze)


def atr(highs, lows, closes, period: int = 14) -> float | None:
    """Average True Range (Wilder) -- absolute volatility in price units."""
    h, l, c = _series(highs), _series(lows), _series(closes)
    if len(c) <= period:
        return None
    tr = pd.concat([(h - l).abs(), (h - c.shift()).abs(), (l - c.shift()).abs()],
                   axis=1).max(axis=1)
    a = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean().iloc[-1]
    return None if pd.isna(a) else float(a)


def historical_volatility(closes, period: int = 30, annualize: int = 252) -> float | None:
    """Annualized stdev of daily log returns over ``period`` bars (decimal)."""
    s = _series(closes)
    if len(s) <= period:
        return None
    log_ret = (s / s.shift(1)).apply(lambda x: math.log(x) if x > 0 else float("nan"))
    vol = log_ret.iloc[-period:].std(ddof=1)
    if pd.isna(vol):
        return None
    return float(vol * math.sqrt(annualize))
