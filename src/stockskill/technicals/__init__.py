"""Technical-indicator library: pure, tested functions over price/volume series.

Foundation for the trading-signal and dashboard layers. Every function takes
plain sequences (oldest -> newest) and returns the latest value (or None when
there isn't enough data). No network, no state -- the LLM never computes these.
"""

from .momentum import rsi, stochastic, williams_r, roc, cci, mfi
from .trend import sma, ema, golden_death_cross, macd, MACDResult, adx
from .volatility import bollinger, BollingerBands, atr, historical_volatility
from .volume import obv, volume_roc, volume_bias, volume_spike
from .ichimoku import ichimoku, Ichimoku
from .changes import (
    CHANGE_WINDOWS, pct_change, change_metrics, ytd_change, sparkline,
)
from .pe import pe_relative_to_avg, pe_volatility

__all__ = [
    # momentum
    "rsi", "stochastic", "williams_r", "roc", "cci", "mfi",
    # trend
    "sma", "ema", "golden_death_cross", "macd", "MACDResult", "adx",
    # volatility
    "bollinger", "BollingerBands", "atr", "historical_volatility",
    # volume
    "obv", "volume_roc", "volume_bias", "volume_spike",
    # ichimoku
    "ichimoku", "Ichimoku",
    # changes
    "CHANGE_WINDOWS", "pct_change", "change_metrics", "ytd_change", "sparkline",
    # pe
    "pe_relative_to_avg", "pe_volatility",
]
