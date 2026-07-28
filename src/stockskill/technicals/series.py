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


def _true_range(h, l, c):
    return pd.concat([(h - l).abs(), (h - c.shift()).abs(), (l - c.shift()).abs()],
                     axis=1).max(axis=1)


def atr_series(highs, lows, closes, period: int = 14) -> list:
    """Average True Range series (Wilder) — matches technicals.volatility.atr."""
    h, l, c = _series(highs), _series(lows), _series(closes)
    tr = _true_range(h, l, c)
    return _tolist(tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean())


def stochastic_series(highs, lows, closes, k_period: int = 14, d_period: int = 3):
    """(%K, %D) series — matches technicals.momentum.stochastic."""
    h, l, c = _series(highs), _series(lows), _series(closes)
    hh = h.rolling(k_period).max()
    ll = l.rolling(k_period).min()
    rng = (hh - ll).replace(0.0, float("nan"))
    k = 100.0 * (c - ll) / rng
    d = k.rolling(d_period).mean()
    return _tolist(k), _tolist(d)


def adx_series(highs, lows, closes, period: int = 14):
    """(ADX, +DI, -DI) series — matches technicals.trend.adx."""
    h, l, c = _series(highs), _series(lows), _series(closes)
    up = h.diff()
    down = -l.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    atr = _true_range(h, l, c).ewm(alpha=1.0 / period, adjust=False).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, float("nan"))
    adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()
    return _tolist(adx), _tolist(plus_di), _tolist(minus_di)


def obv_series(closes, volumes) -> list:
    """Running On-Balance Volume series — matches technicals.volume.obv (cumsum)."""
    c, v = _series(closes), _series(volumes)
    sign = c.diff().apply(lambda d: 1.0 if d > 0 else (-1.0 if d < 0 else 0.0))
    return _tolist((sign * v).cumsum())


def ichimoku_series(highs, lows, closes, tenkan_p: int = 9, kijun_p: int = 26,
                    senkou_b_p: int = 52) -> dict:
    """Ichimoku lines aligned to each bar (matches technicals.ichimoku): conversion
    (tenkan), base (kijun), and the leading spans (cloud edges) at the current bar."""
    h, l, c = _series(highs), _series(lows), _series(closes)

    def mid(p):
        return (h.rolling(p).max() + l.rolling(p).min()) / 2.0

    conv = mid(tenkan_p)
    base = mid(kijun_p)
    span_a = ((conv + base) / 2.0).shift(kijun_p)
    span_b = mid(senkou_b_p).shift(kijun_p)
    return {"tenkan": _tolist(conv), "kijun": _tolist(base),
            "span_a": _tolist(span_a), "span_b": _tolist(span_b)}
