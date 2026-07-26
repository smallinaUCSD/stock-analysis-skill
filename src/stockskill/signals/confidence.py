"""Signal confidence via inter-strategy agreement.

How many of the base strategies (BB, RSI, MACD, Ichimoku) agree with the active
signal? High agreement -> a clean read. This is scored for EVERY signal,
including HOLD: a strong HOLD means the strategies clearly agree there's no
trade; a weak HOLD means they're contested (some see a BUY/SHORT the
conservative active strategy is holding through) -- which is itself a useful tell.
"""

from __future__ import annotations

from dataclasses import dataclass

_BASE = ("BB", "RSI", "MACD", "Ichimoku")


@dataclass
class Confidence:
    level: str      # STRONG | MODERATE | WEAK
    pct: float      # fraction of base strategies agreeing (0..1)
    agree: int
    total: int


def signal_confidence(all_signals: dict[str, str], active: str) -> Confidence | None:
    """Agreement of the base strategies with the ``active`` signal (0..1)."""
    base = [all_signals.get(k) for k in _BASE if all_signals.get(k) is not None]
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
