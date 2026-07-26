"""Trading-signal layer: rule-based strategy states, trend score, confidence.

All deterministic over an IndicatorSnapshot (built from the technicals library).
Signals are indicator STATES, not personalized buy/sell advice.
"""

from .config import SignalConfig, BUY, SELL, SHORT, HOLD
from .snapshot import IndicatorSnapshot, build_snapshot
from .strategies import (
    bb_signal, rsi_signal, macd_signal, ichimoku_signal,
    combined_signal, bb_ichimoku_signal, active_signal, all_strategy_signals,
)
from .trend import Trend, trend, trend_score, trend_arrow
from .confidence import Confidence, signal_confidence

__all__ = [
    "SignalConfig", "BUY", "SELL", "SHORT", "HOLD",
    "IndicatorSnapshot", "build_snapshot",
    "bb_signal", "rsi_signal", "macd_signal", "ichimoku_signal",
    "combined_signal", "bb_ichimoku_signal", "active_signal", "all_strategy_signals",
    "Trend", "trend", "trend_score", "trend_arrow",
    "Confidence", "signal_confidence",
]
