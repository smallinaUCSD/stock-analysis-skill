"""ATR-based trade setup and position sizing -- an INFORMATIONAL risk framework.

Given a price, ATR, and a direction, compute a volatility-adjusted stop and a
2:1 target, plus a position size that risks a fixed % of the account (capped).
This is deterministic risk arithmetic, not a recommendation to trade -- it
answers "if you took this trade, here's a disciplined stop/target/size", the
decision stays the user's.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TradeSetup:
    direction: str        # LONG | SHORT
    entry: float
    stop: float
    target: float
    risk_pct: float       # |entry-stop|/entry
    reward_pct: float     # |target-entry|/entry
    rr_ratio: float       # reward:risk (e.g. 2.0)


def atr_trade_setup(price: float, atr: float, direction: str = "LONG",
                    atr_mult: float = 2.0, rr: float = 2.0) -> TradeSetup | None:
    """Stop = entry -/+ atr_mult*ATR; target = entry +/- atr_mult*ATR*rr."""
    if price <= 0 or atr is None or atr <= 0:
        return None
    d = direction.upper()
    risk = atr_mult * atr
    if d == "LONG":
        stop, target = price - risk, price + risk * rr
    elif d == "SHORT":
        stop, target = price + risk, price - risk * rr
    else:
        return None
    return TradeSetup(
        direction=d, entry=price, stop=stop, target=target,
        risk_pct=abs(price - stop) / price,
        reward_pct=abs(target - price) / price,
        rr_ratio=rr,
    )


@dataclass
class PositionSize:
    shares: float
    dollars: float
    pct_of_account: float
    capped: bool          # True if the max-position cap bound the size


def position_size(account: float, entry: float, stop: float,
                  risk_per_trade: float = 0.02, max_pct: float = 0.25) -> PositionSize | None:
    """Size so a stop-out loses ``risk_per_trade`` of the account, capped at
    ``max_pct`` of the account to avoid over-concentration."""
    if account <= 0 or entry <= 0:
        return None
    per_share_risk = abs(entry - stop)
    if per_share_risk <= 0:
        return None
    shares = (account * risk_per_trade) / per_share_risk
    dollars = shares * entry
    capped = False
    max_dollars = account * max_pct
    if dollars > max_dollars:
        dollars, shares, capped = max_dollars, max_dollars / entry, True
    return PositionSize(shares, dollars, dollars / account, capped)
