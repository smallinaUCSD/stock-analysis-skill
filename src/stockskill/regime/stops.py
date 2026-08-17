"""Evidence-based stops — Kaminski & Lo (2014), *When Do Stop-Loss Rules Stop Losses?*

Their result: a stop-loss **adds value under momentum but subtracts it under a
random walk / mean reversion** (it just locks in noise and misses the rebound).
So rather than apply a fixed stop blindly, backtest a stop-loss *overlay* on
buy-and-hold for the name and report whether it would have helped — return, vol,
and risk-adjusted (Sharpe).

Overlay: hold the asset until its trailing-``window`` return falls to
``exit_thresh`` → go to cash (earn the risk-free rate); re-enter once the trailing
return recovers to ``reenter_thresh``. No look-ahead — the state for each day is
decided by information available the day before. Pure and tested.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_YEAR = 252


@dataclass(frozen=True)
class StopStudy:
    exit_thresh: float
    buyhold_return: float       # annualized
    stopped_return: float
    stopping_premium: float     # stopped − buyhold (annualized)
    buyhold_vol: float
    stopped_vol: float
    buyhold_sharpe: float
    stopped_sharpe: float
    pct_in_market: float
    n_stops: int
    helps: bool                 # stop improved the risk-adjusted return


def _stats(rets: list[float], rf_daily: float) -> tuple[float, float, float]:
    n = len(rets)
    if n < 2:
        return (0.0, 0.0, 0.0)
    mean = sum(rets) / n
    var = sum((x - mean) ** 2 for x in rets) / (n - 1)
    sd = var ** 0.5
    ann_vol = sd * math.sqrt(_YEAR)
    sharpe = ((mean - rf_daily) * _YEAR) / ann_vol if ann_vol > 0 else 0.0
    return mean * _YEAR, ann_vol, sharpe


def stop_study(closes: list[float], exit_thresh: float = -0.10,
               reenter_thresh: float = 0.0, window: int = 50,
               rf_annual: float = 0.02) -> StopStudy | None:
    """Backtest a stop-loss overlay on buy-and-hold. None if history is too short."""
    if not closes or len(closes) < window + 30:
        return None
    rf_daily = rf_annual / _YEAR
    buyhold: list[float] = []
    stopped: list[float] = []
    in_market = True
    n_stops = 0
    days_in = 0
    for t in range(1, len(closes)):
        if not closes[t - 1]:
            continue
        r = closes[t] / closes[t - 1] - 1.0
        buyhold.append(r)
        # State for earning r is decided by the trailing return AS OF t-1 (no look-ahead).
        if t - 1 >= window and closes[t - 1 - window]:
            trail = closes[t - 1] / closes[t - 1 - window] - 1.0
            if in_market and trail <= exit_thresh:
                in_market, n_stops = False, n_stops + 1
            elif not in_market and trail >= reenter_thresh:
                in_market = True
        stopped.append(r if in_market else rf_daily)
        days_in += 1 if in_market else 0

    bh_r, bh_v, bh_s = _stats(buyhold, rf_daily)
    st_r, st_v, st_s = _stats(stopped, rf_daily)
    return StopStudy(
        exit_thresh=exit_thresh, buyhold_return=bh_r, stopped_return=st_r,
        stopping_premium=st_r - bh_r, buyhold_vol=bh_v, stopped_vol=st_v,
        buyhold_sharpe=bh_s, stopped_sharpe=st_s,
        pct_in_market=days_in / len(stopped) if stopped else 1.0,
        n_stops=n_stops, helps=st_s > bh_s + 1e-9)
