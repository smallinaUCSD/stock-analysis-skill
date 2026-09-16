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


def volume_read(s: IndicatorSnapshot) -> tuple[str | None, float, str]:
    """How volume relates to the price move: (state, trend-score adjustment, label).

    Volume *confirms* a trend when money-flow agrees with price, and *diverges*
    (a warning) when it doesn't -- a breakout on heavy volume is real; the same
    move on thin/declining volume is often a fakeout. Divergences dominate; then
    OBV direction; then a thin-volume caveat. Returns (None, 0.0, "") when there
    is no volume data (so a price-only snapshot is unaffected)."""
    rv = s.rvol
    rvtxt = f", {rv:.1f}x avg" if rv else ""
    if s.vol_divergence == "bearish":
        return ("bearish-divergence", -1.0,
                "bearish divergence: price up but volume isn't confirming")
    if s.vol_divergence == "bullish":
        return ("bullish-divergence", 1.0,
                "bullish divergence: price down but volume is accumulating")
    if s.obv_dir == "rising":
        return ("accumulation", 0.5, f"volume confirms: OBV rising{rvtxt}")
    if s.obv_dir == "falling":
        return ("distribution", -0.5, f"volume confirms selling: OBV falling{rvtxt}")
    if rv is not None and rv < 0.7:
        return ("thin", 0.0, f"thin volume ({rv:.1f}x avg): move unconfirmed")
    if s.obv_dir is None and rv is None:
        return (None, 0.0, "")
    return ("neutral", 0.0, "volume roughly neutral")


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

    # Volume confirmation (+-0.5 for OBV agreement, +-1.0 on a divergence). Zero
    # when there is no volume data, so price-only snapshots are unaffected.
    score += volume_read(s)[1]

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
