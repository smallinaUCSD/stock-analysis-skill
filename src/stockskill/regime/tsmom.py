"""Time-series (absolute) momentum — Moskowitz, Ooi & Pedersen (2012).

The **sign of a name's own trailing ~12-month return** predicts the next month:
up-trending names keep trending up, down-trending down. Unlike cross-sectional
momentum (rank vs peers), this is each name vs *itself*. Position size is scaled
by inverse volatility so a calm and a jumpy name contribute comparable risk.

Pure and tested. A trend read, not advice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_YEAR = 252


@dataclass(frozen=True)
class TSMom:
    signal: int                 # +1 long / -1 short / 0 flat
    trailing_return: float      # trailing lookback return (decimal)
    ann_vol: float | None       # annualized volatility
    position_scale: float | None  # signal * target_vol / ann_vol (inverse-vol sizing)
    label: str


def annualized_vol(closes: list[float], lookback: int = 60) -> float | None:
    window = (closes or [])[-(lookback + 1):]
    rets = [b / a - 1.0 for a, b in zip(window[:-1], window[1:]) if a]
    if len(rets) < 20:
        return None
    m = sum(rets) / len(rets)
    var = sum((x - m) ** 2 for x in rets) / (len(rets) - 1)
    return (var ** 0.5) * math.sqrt(_YEAR)


def tsmom(closes: list[float], lookback: int = _YEAR, target_vol: float = 0.15) -> TSMom | None:
    """Time-series momentum over ``lookback`` trading days. None if too short."""
    if not closes or len(closes) <= lookback:
        return None
    past = closes[-lookback - 1]
    if not past:
        return None
    trailing = closes[-1] / past - 1.0
    signal = 1 if trailing > 0 else (-1 if trailing < 0 else 0)
    vol = annualized_vol(closes)
    scale = (signal * target_vol / vol) if (vol and vol > 0) else None
    months = round(lookback / 21)
    if signal > 0:
        label = f"uptrend ({months}m {trailing*100:+.0f}%)"
    elif signal < 0:
        label = f"downtrend ({months}m {trailing*100:+.0f}%)"
    else:
        label = "flat"
    return TSMom(signal=signal, trailing_return=trailing, ann_vol=vol,
                position_scale=scale, label=label)
