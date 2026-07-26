"""Momentum oscillators: RSI, Stochastic, Williams %R, ROC, CCI, MFI.

Pure functions over price/volume series (oldest -> newest). Each returns the
latest value (a float) or None when there isn't enough data. No network, no
state -- feed from the data layer. Fully unit-tested.
"""

from __future__ import annotations

import pandas as pd


def _series(x) -> pd.Series:
    return pd.Series(list(x), dtype="float64")


def rsi(closes, period: int = 14) -> float | None:
    """Wilder's RSI via EWM. 0-100; >70 overbought, <30 oversold.

    Strictly rising series -> 100; strictly falling -> 0.
    """
    s = _series(closes)
    if len(s) <= period:
        return None
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    ag, al = avg_gain.iloc[-1], avg_loss.iloc[-1]
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    rs = ag / al
    return float(100.0 - 100.0 / (1.0 + rs))


def stochastic(highs, lows, closes, k_period: int = 14, d_period: int = 3):
    """Stochastic oscillator. Returns (%K, %D), each 0-100, or (None, None)."""
    h, l, c = _series(highs), _series(lows), _series(closes)
    if len(c) < k_period:
        return (None, None)
    hh = h.rolling(k_period).max()
    ll = l.rolling(k_period).min()
    rng = (hh - ll).replace(0.0, float("nan"))
    k = 100.0 * (c - ll) / rng
    d = k.rolling(d_period).mean()
    kv = k.iloc[-1]
    dv = d.iloc[-1]
    return (None if pd.isna(kv) else float(kv),
            None if pd.isna(dv) else float(dv))


def williams_r(highs, lows, closes, period: int = 14) -> float | None:
    """Williams %R. -100 (most oversold) .. 0 (most overbought)."""
    h, l, c = _series(highs), _series(lows), _series(closes)
    if len(c) < period:
        return None
    hh = h.rolling(period).max().iloc[-1]
    ll = l.rolling(period).min().iloc[-1]
    if hh == ll:
        return None
    return float(-100.0 * (hh - c.iloc[-1]) / (hh - ll))


def roc(closes, period: int = 12) -> float | None:
    """Rate of change: percent return over ``period`` bars (0.05 == +5%)."""
    s = _series(closes)
    if len(s) <= period or s.iloc[-1 - period] == 0:
        return None
    return float(s.iloc[-1] / s.iloc[-1 - period] - 1.0)


def cci(highs, lows, closes, period: int = 20) -> float | None:
    """Commodity Channel Index. Typically +-100 is the notable band."""
    h, l, c = _series(highs), _series(lows), _series(closes)
    if len(c) < period:
        return None
    tp = (h + l + c) / 3.0
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda w: (w - w.mean()).abs().mean(), raw=False)
    denom = 0.015 * mad.iloc[-1]
    if denom == 0 or pd.isna(denom):
        return None
    return float((tp.iloc[-1] - sma.iloc[-1]) / denom)


def mfi(highs, lows, closes, volumes, period: int = 14) -> float | None:
    """Money Flow Index -- a volume-weighted RSI. 0-100."""
    h, l, c, v = _series(highs), _series(lows), _series(closes), _series(volumes)
    if len(c) <= period:
        return None
    tp = (h + l + c) / 3.0
    mf = tp * v
    direction = tp.diff()
    pos = mf.where(direction > 0, 0.0).rolling(period).sum()
    neg = mf.where(direction < 0, 0.0).rolling(period).sum()
    p, n = pos.iloc[-1], neg.iloc[-1]
    if pd.isna(p) or pd.isna(n):
        return None
    if n == 0:
        return 100.0 if p > 0 else 50.0
    return float(100.0 - 100.0 / (1.0 + p / n))
