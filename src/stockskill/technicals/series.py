"""Full indicator SERIES (not just the latest value) for charting.

Mirrors the formulas in momentum/trend/volatility, but returns the whole series
(NaN -> None) so the technical-indicators page can plot them over time.
"""

from __future__ import annotations

import pandas as pd


def _series(x) -> pd.Series:
    return pd.Series(list(x), dtype="float64")


def _tolist(s: pd.Series) -> list:
    return [None if pd.isna(v) else float(v) for v in s]


def sma_series(closes, period: int) -> list:
    return _tolist(_series(closes).rolling(period).mean())


def ema_series(closes, span: int) -> list:
    return _tolist(_series(closes).ewm(span=span, adjust=False).mean())


def bollinger_series(closes, period: int = 20, num_std: float = 2.0):
    """(middle, upper, lower) Bollinger band series."""
    s = _series(closes)
    mid = s.rolling(period).mean()
    sd = s.rolling(period).std(ddof=0)
    return _tolist(mid), _tolist(mid + num_std * sd), _tolist(mid - num_std * sd)


def rsi_series(closes, period: int = 14) -> list:
    """Wilder's RSI series (matches technicals.momentum.rsi)."""
    s = _series(closes)
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    ag = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    al = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = ag / al
    rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = rsi.where(al != 0, 100.0)
    return _tolist(rsi)


def macd_series(closes, fast: int = 12, slow: int = 26, signal: int = 9):
    """(macd_line, signal_line, histogram) series (matches technicals.trend.macd)."""
    s = _series(closes)
    macd_line = s.ewm(span=fast, adjust=False).mean() - s.ewm(span=slow, adjust=False).mean()
    sig = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - sig
    return _tolist(macd_line), _tolist(sig), _tolist(hist)
