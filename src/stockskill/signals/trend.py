"""Multi-factor trend score and arrow.

Aggregates several indicator biases into one score, then maps to an arrow. This
is a *descriptive* trend read (where the weight of evidence points), not a
forecast or a recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import SignalConfig, BUY, SELL, SHORT
from .snapshot import IndicatorSnapshot


@dataclass
class Trend:
    score: float
    arrow: str      # ↑ ↗ → ↘ ↓
    label: str


def trend_score(s: IndicatorSnapshot, active: str, cfg: SignalConfig) -> float:
    score = 0.0

    # MACD (+-2)
    if s.macd_state in ("bull_cross", "bullish"):
        score += 2.0
    elif s.macd_state in ("bear_cross", "bearish"):
        score -= 2.0

    # RSI momentum (+-0.5 / +-1.0)
    if s.rsi is not None:
        if s.rsi >= 60:
            score += 1.0
        elif s.rsi > 50:
            score += 0.5
        elif s.rsi <= 40:
            score -= 1.0
        elif s.rsi < 50:
            score -= 0.5

    # BB position (+-0.5 / +-1.0)
    if s.bb_position is not None:
        if s.bb_position >= 80:
            score += 1.0
        elif s.bb_position > 60:
            score += 0.5
        elif s.bb_position <= 20:
            score -= 1.0
        elif s.bb_position < 40:
            score -= 0.5

    # Ichimoku (+-2.0 / +-2.5 with TK confirmation)
    if s.ich_price_vs_cloud == "above":
        score += 2.5 if s.ich_tk == "bull" else 2.0
    elif s.ich_price_vs_cloud == "below":
        score -= 2.5 if s.ich_tk == "bear" else 2.0

    # Active signal (+-1.5 / -1.0)
    if active == BUY:
        score += 1.5
    elif active == SHORT:
        score -= 1.5
    elif active == SELL:
        score -= 1.0

    # Price momentum (+-1.0)
    if s.change_pct is not None:
        if s.change_pct >= cfg.trend_momentum_threshold:
            score += 1.0
        elif s.change_pct <= -cfg.trend_momentum_threshold:
            score -= 1.0

    return score


def trend_arrow(score: float) -> tuple[str, str]:
    """(arrow, label) from the trend score."""
    if score >= 4.0:
        return ("↑", "strong uptrend")
    if score >= 1.5:
        return ("↗", "uptrend")
    if score <= -4.0:
        return ("↓", "strong downtrend")
    if score <= -1.5:
        return ("↘", "downtrend")
    return ("→", "neutral")


def trend(s: IndicatorSnapshot, active: str, cfg: SignalConfig) -> Trend:
    score = trend_score(s, active, cfg)
    arrow, label = trend_arrow(score)
    return Trend(score, arrow, label)
