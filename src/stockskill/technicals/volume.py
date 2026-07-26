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
