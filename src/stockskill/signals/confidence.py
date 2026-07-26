"""Signal confidence via inter-strategy agreement.

How many of the base strategies (BB, RSI, MACD, Ichimoku) agree with the active
signal? High agreement -> higher-quality setup. HOLD signals aren't scored.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import HOLD

_BASE = ("BB", "RSI", "MACD", "Ichimoku")


@dataclass
class Confidence:
    level: str      # STRONG | MODERATE | WEAK
    pct: float      # fraction of base strategies agreeing (0..1)
    agree: int
    total: int


def signal_confidence(all_signals: dict[str, str], active: str) -> Confidence | None:
    """Agreement of the base strategies with ``active`` (BUY/SELL/SHORT).

    Returns None for HOLD (neutral positions don't get a confidence score).
    """
    if active == HOLD:
        return None
    base = [all_signals.get(k) for k in _BASE if k in all_signals]
    total = len(base)
    if total == 0:
        return None
    agree = sum(1 for sig in base if sig == active)
    pct = agree / total
    if pct >= 0.75:
        level = "STRONG"
    elif pct >= 0.50:
        level = "MODERATE"
    else:
        level = "WEAK"
    return Confidence(level, pct, agree, total)
