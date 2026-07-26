"""Rule-based options-strategy suggestions from technical state + events.

Informational only: these are "if you trade options, the technicals/vol line up
for X" observations, not advice. Deterministic and unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OptionIdea:
    label: str
    direction: str     # bullish | bearish | earnings
    rationale: str


def implied_move(atm_call_price, atm_put_price, spot) -> float | None:
    """Straddle-based implied move: (ATM call + ATM put) / spot (decimal)."""
    if spot is None or spot <= 0 or atm_call_price is None or atm_put_price is None:
        return None
    return (atm_call_price + atm_put_price) / spot


def suggest_options(trend_score: float | None = None, rsi: float | None = None,
                    change_pct: float | None = None, golden_death: str | None = None,
                    imp_move: float | None = None,
                    days_to_earnings: int | None = None) -> list[OptionIdea]:
    """Suggest option ideas. ``change_pct`` is a percent (e.g. 2.5 == +2.5%)."""
    out: list[OptionIdea] = []
    ch = change_pct if change_pct is not None else 0.0

    # earnings-driven volatility plays
    if days_to_earnings is not None and 0 <= days_to_earnings <= 7 and imp_move is not None:
        if imp_move >= 0.08:
            out.append(OptionIdea("Earnings straddle/strangle", "earnings",
                       f"Earnings in {days_to_earnings}d, {imp_move:.0%} implied move (high-vol event)"))
        elif imp_move >= 0.05:
            out.append(OptionIdea("Pre-earnings directional", "earnings",
                       f"Earnings in {days_to_earnings}d, {imp_move:.0%} implied move"))

    # directional (bullish)
    if trend_score is not None and trend_score >= 4.0 and ch >= 2.0:
        out.append(OptionIdea("Buy calls", "bullish",
                   f"Strong uptrend (trend {trend_score:.0f}) + momentum {ch:+.1f}%"))
    elif rsi is not None and rsi >= 70 and ch >= 1.0:
        out.append(OptionIdea("Buy calls", "bullish",
                   f"Overbought with momentum (RSI {rsi:.0f}, {ch:+.1f}%)"))

    # directional (bearish)
    if golden_death == "death" or (trend_score is not None and trend_score <= -4.0):
        out.append(OptionIdea("Buy puts", "bearish", "Death cross / strong downtrend"))
    elif rsi is not None and rsi <= 30 and ch <= -1.0:
        out.append(OptionIdea("Buy puts", "bearish",
                   f"Oversold with weakness (RSI {rsi:.0f}, {ch:+.1f}%)"))

    return out
