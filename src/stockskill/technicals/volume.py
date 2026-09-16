"""Volume indicators: OBV, volume ROC, up/down bias, volume spike."""

from __future__ import annotations

import pandas as pd


def _series(x) -> pd.Series:
    return pd.Series(list(x), dtype="float64")


def obv(closes, volumes) -> float | None:
    """On-Balance Volume (latest running total). Direction matters, not level."""
    c, v = _series(closes), _series(volumes)
    if len(c) < 2 or len(v) != len(c):
        return None
    sign = c.diff().apply(lambda d: 1.0 if d > 0 else (-1.0 if d < 0 else 0.0))
    return float((sign * v).sum())


def volume_roc(volumes, period: int = 1) -> float | None:
    """Percent change in volume over ``period`` bars (0.5 == +50%)."""
    v = _series(volumes)
    if len(v) <= period or v.iloc[-1 - period] == 0:
        return None
    return float(v.iloc[-1] / v.iloc[-1 - period] - 1.0)


def volume_bias(closes, volumes, period: int = 20) -> float | None:
    """Share of recent volume on up days minus down days, -1..1.

    Positive = accumulation (more volume on up days); negative = distribution.
    """
    c, v = _series(closes), _series(volumes)
    if len(c) < period + 1:
        return None
    d = c.diff().iloc[-period:]
    vol = v.iloc[-period:]
    up = vol[d > 0].sum()
    down = vol[d < 0].sum()
    total = up + down
    if total == 0:
        return 0.0
    return float((up - down) / total)


def volume_spike(volumes, period: int = 20, threshold: float = 1.5) -> tuple[bool, float | None]:
    """Is the latest volume >= ``threshold`` x its trailing average?

    Returns (is_spike, ratio). Ratio is latest / average.
    """
    v = _series(volumes)
    if len(v) < period + 1:
        return (False, None)
    avg = v.iloc[-period - 1:-1].mean()
    if avg == 0:
        return (False, None)
    ratio = float(v.iloc[-1] / avg)
    return (ratio >= threshold, ratio)


def relative_volume(volumes, period: int = 20) -> float | None:
    """Latest volume / trailing average (1.0 == average, 2.0 == double). Like
    ``volume_spike``'s ratio but always returned, for an at-a-glance activity read."""
    v = _series(volumes)
    if len(v) < period + 1:
        return None
    avg = v.iloc[-period - 1:-1].mean()
    return float(v.iloc[-1] / avg) if avg else None


def obv_slope(closes, volumes, period: int = 20) -> float | None:
    """Normalized On-Balance-Volume trend over ``period`` bars.

    OBV's absolute level is arbitrary, so we report its net change scaled by the
    average daily volume: roughly the fraction of one day's volume, per day,
    flowing in (>0 accumulation) or out (<0 distribution). Comparable across names.
    """
    c, v = _series(closes), _series(volumes)
    if len(c) < period + 1 or len(v) != len(c):
        return None
    sign = c.diff().apply(lambda d: 1.0 if d > 0 else (-1.0 if d < 0 else 0.0))
    obv_s = (sign * v).cumsum()
    net = float(obv_s.iloc[-1] - obv_s.iloc[-1 - period])
    avgv = float(v.iloc[-period:].mean())
    return net / (avgv * period) if avgv else 0.0


def price_volume_divergence(closes, volumes, period: int = 20,
                            price_thr: float = 0.03, obv_thr: float = 0.05) -> str | None:
    """Price/volume divergence over ``period`` bars -- a classic early-reversal tell.

    'bearish': price rose but OBV fell (buyers not backing the move);
    'bullish': price fell but OBV rose (accumulation into weakness); else None.
    """
    c = _series(closes)
    if len(c) < period + 1:
        return None
    price_chg = float(c.iloc[-1] / c.iloc[-1 - period] - 1.0)
    sl = obv_slope(closes, volumes, period)
    if sl is None:
        return None
    if price_chg > price_thr and sl < -obv_thr:
        return "bearish"
    if price_chg < -price_thr and sl > obv_thr:
        return "bullish"
    return None
