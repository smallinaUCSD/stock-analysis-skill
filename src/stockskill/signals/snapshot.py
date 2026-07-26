"""IndicatorSnapshot: the handful of indicator values the strategies need,
computed once from OHLCV via the technicals library.

Separating this from the signal rules keeps the rules pure and unit-testable
(tests build a snapshot directly) and avoids recomputing indicators per strategy.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import technicals as ta


@dataclass
class IndicatorSnapshot:
    rsi: float | None = None
    rsi_prev: float | None = None
    bb_position: float | None = None       # BB position % (0 lower band .. 100 upper)
    bb_position_prev: float | None = None
    bb_squeeze: bool = False
    macd_state: str | None = None          # bull_cross|bear_cross|bullish|bearish
    ich_price_vs_cloud: str | None = None  # above|below|in_cloud
    ich_tk: str | None = None              # bull|bear
    change_pct: float | None = None        # latest daily % change (as %, e.g. 2.5)


def build_snapshot(highs, lows, closes, volumes=None) -> IndicatorSnapshot:
    """Compute the strategy-relevant indicators from OHLC(V) series."""
    closes = list(closes)
    snap = IndicatorSnapshot()

    snap.rsi = ta.rsi(closes)
    if len(closes) > 1:
        snap.rsi_prev = ta.rsi(closes[:-1])

    bb = ta.bollinger(closes)
    if bb is not None:
        snap.bb_position = bb.position_pct
        snap.bb_squeeze = bb.squeeze
    if len(closes) > 1:
        bb_prev = ta.bollinger(closes[:-1])
        if bb_prev is not None:
            snap.bb_position_prev = bb_prev.position_pct

    m = ta.macd(closes)
    if m is not None:
        snap.macd_state = m.state

    ich = ta.ichimoku(highs, lows, closes)
    if ich is not None:
        snap.ich_price_vs_cloud = ich.price_vs_cloud
        snap.ich_tk = ich.tk_state

    ch = ta.pct_change(closes, 1)
    snap.change_pct = None if ch is None else ch * 100.0
    return snap
