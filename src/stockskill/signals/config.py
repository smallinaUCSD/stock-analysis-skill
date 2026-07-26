"""Signal configuration: thresholds, weights, and the active strategy.

Defaults mirror Dad's `smi`. All overridable via environment variables so the
dashboard can be tuned without code changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# signal states
BUY = "BUY"
SELL = "SELL"
SHORT = "SHORT"
HOLD = "HOLD"


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


@dataclass
class SignalConfig:
    strategy: str = "bb_ichimoku"       # bb|rsi|macd|ichimoku|combined|bb_ichimoku
    # Bollinger Bands
    bb_buy: float = 10.0                 # BUY at/below this BB position %
    bb_short: float = 90.0               # SHORT at/above
    bb_sell: float = 85.0                # SELL (exit longs) at/above + reversing down
    # RSI
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    # combined weighted vote
    w_ichimoku: float = 1.5
    w_macd: float = 1.2
    w_bb: float = 1.0
    w_rsi: float = 0.8
    combined_threshold: float = 2.0
    # bb+ichimoku
    bb_ichimoku_mode: str = "CONFIRM"    # CONFIRM|AND|OR
    # trend
    trend_momentum_threshold: float = 2.0   # daily % move that counts as momentum

    @classmethod
    def from_env(cls) -> "SignalConfig":
        return cls(
            strategy=os.environ.get("TRADING_STRATEGY", "bb_ichimoku"),
            bb_buy=_f("BB_BUY_THRESHOLD", 10.0),
            bb_short=_f("BB_SHORT_THRESHOLD", 90.0),
            bb_sell=_f("BB_SELL_THRESHOLD", 85.0),
            rsi_oversold=_f("RSI_OVERSOLD", 30.0),
            rsi_overbought=_f("RSI_OVERBOUGHT", 70.0),
            w_ichimoku=_f("WEIGHT_ICHIMOKU", 1.5),
            w_macd=_f("WEIGHT_MACD", 1.2),
            w_bb=_f("WEIGHT_BB", 1.0),
            w_rsi=_f("WEIGHT_RSI", 0.8),
            combined_threshold=_f("COMBINED_THRESHOLD", 2.0),
            bb_ichimoku_mode=os.environ.get("BB_ICHIMOKU_MODE", "CONFIRM").upper(),
            trend_momentum_threshold=_f("TREND_MOMENTUM_THRESHOLD", 2.0),
        )
