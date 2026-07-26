"""Trading strategies: rule-based signal STATES over an IndicatorSnapshot.

Each returns BUY / SELL / SHORT / HOLD. These are indicator states (like a
charting tool's "RSI is oversold"), not personalized advice -- the decision
stays the user's. Deterministic and unit-tested.
"""

from __future__ import annotations

from .config import SignalConfig, BUY, SELL, SHORT, HOLD
from .snapshot import IndicatorSnapshot


def bb_signal(s: IndicatorSnapshot, cfg: SignalConfig) -> str:
    p = s.bb_position
    if p is None:
        return HOLD
    if p <= cfg.bb_buy:
        return BUY
    if p >= cfg.bb_short:
        return SHORT
    if p >= cfg.bb_sell and s.bb_position_prev is not None and p < s.bb_position_prev:
        return SELL          # near the top and rolling over -> exit longs
    return HOLD


def rsi_signal(s: IndicatorSnapshot, cfg: SignalConfig) -> str:
    r = s.rsi
    if r is None:
        return HOLD
    if r <= cfg.rsi_oversold:
        return BUY
    if r >= cfg.rsi_overbought:
        return SHORT
    if s.rsi_prev is not None and s.rsi_prev >= cfg.rsi_overbought and r < s.rsi_prev:
        return SELL          # dropping back out of overbought -> exit
    return HOLD


def macd_signal(s: IndicatorSnapshot, cfg: SignalConfig) -> str:
    if s.macd_state == "bull_cross":
        return BUY
    if s.macd_state == "bear_cross":
        return SHORT
    return HOLD


def ichimoku_signal(s: IndicatorSnapshot, cfg: SignalConfig) -> str:
    if s.ich_price_vs_cloud == "above" and s.ich_tk == "bull":
        return BUY
    if s.ich_price_vs_cloud == "below" and s.ich_tk == "bear":
        return SHORT
    return HOLD


def combined_signal(s: IndicatorSnapshot, cfg: SignalConfig) -> str:
    """Weighted vote across BB/RSI/MACD/Ichimoku with conflict resolution."""
    pairs = [
        (bb_signal(s, cfg), cfg.w_bb),
        (rsi_signal(s, cfg), cfg.w_rsi),
        (macd_signal(s, cfg), cfg.w_macd),
        (ichimoku_signal(s, cfg), cfg.w_ichimoku),
    ]
    buy_score = sum(w for sig, w in pairs if sig == BUY)
    short_score = sum(w for sig, w in pairs if sig == SHORT)
    any_sell = any(sig == SELL for sig, _ in pairs)
    t = cfg.combined_threshold
    if buy_score >= t and short_score < t:
        return BUY
    if short_score >= t and buy_score < t:
        return SHORT
    if any_sell and buy_score < t:
        return SELL
    return HOLD


def bb_ichimoku_signal(s: IndicatorSnapshot, cfg: SignalConfig) -> str:
    """BB + Ichimoku confirmation, per mode (CONFIRM | AND | OR)."""
    b = bb_signal(s, cfg)
    i = ichimoku_signal(s, cfg)
    mode = cfg.bb_ichimoku_mode
    if mode == "AND":
        return b if (b == i and b in (BUY, SHORT, SELL)) else HOLD
    if mode == "OR":
        pair = {b, i}
        if BUY in pair and SHORT not in pair:
            return BUY
        if SHORT in pair and BUY not in pair:
            return SHORT
        if SELL in pair:
            return SELL
        return HOLD
    # CONFIRM (default): entries need agreement; exits (SELL) can trigger from either
    if b == BUY and i == BUY:
        return BUY
    if b == SHORT and i == SHORT:
        return SHORT
    if b == SELL or i == SELL:
        return SELL
    return HOLD


_DISPATCH = {
    "bb": bb_signal, "rsi": rsi_signal, "macd": macd_signal,
    "ichimoku": ichimoku_signal, "combined": combined_signal,
    "bb_ichimoku": bb_ichimoku_signal,
}


def active_signal(s: IndicatorSnapshot, cfg: SignalConfig) -> str:
    """The signal from the configured active strategy."""
    return _DISPATCH.get(cfg.strategy, bb_ichimoku_signal)(s, cfg)


def all_strategy_signals(s: IndicatorSnapshot, cfg: SignalConfig) -> dict[str, str]:
    """Every strategy's signal, for the confidence / agreement calculation."""
    return {
        "BB": bb_signal(s, cfg),
        "RSI": rsi_signal(s, cfg),
        "MACD": macd_signal(s, cfg),
        "Ichimoku": ichimoku_signal(s, cfg),
        "Combined": combined_signal(s, cfg),
        "BB+Ichimoku": bb_ichimoku_signal(s, cfg),
    }
