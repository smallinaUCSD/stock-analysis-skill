"""Look-through exposure: collapse leveraged holdings into true underlying $.

$10k in AAPU (2x AAPL) is $20k of economic AAPL exposure. $10k in FNGU (3x a
10-name basket) is $30k spread across those names. This module expands every
holding into notional dollar exposure per underlying, so hidden overlap
(AAPL living inside AAPU *and* FNGU *and* BULZ) becomes visible.

Pure arithmetic over the registry snapshot. Refresh basket constituents via
``registry.override_constituents`` before calling if you need live weights.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..leverage import registry


@dataclass(frozen=True)
class Holding:
    ticker: str
    market_value: float             # current $ value of the position
    account: str = ""               # e.g. "brokerage", "roth", "401k"


@dataclass
class LookThrough:
    total_equity: float                      # sum of position market values
    notional_by_underlying: dict[str, float] # underlying -> economic $ exposure
    total_notional: float                    # sum of all notional exposure
    contributions: list[tuple[str, str, float]] = field(default_factory=list)
    # contributions: (holding_ticker, underlying, notional_dollars)

    @property
    def effective_leverage(self) -> float:
        """Total economic exposure / equity. 1.0 == unlevered."""
        return self.total_notional / self.total_equity if self.total_equity else float("nan")

    def exposure_weights(self) -> dict[str, float]:
        """Underlying -> share of total notional exposure (sums to 1.0)."""
        if self.total_notional <= 0:
            return {}
        return {k: v / self.total_notional for k, v in self.notional_by_underlying.items()}

    def top(self, n: int = 10) -> list[tuple[str, float]]:
        ranked = sorted(self.notional_by_underlying.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:n]


def expand(holdings: list[Holding]) -> LookThrough:
    """Expand holdings into look-through notional exposure per underlying.

    * Leveraged single-stock: notional = market_value * multiplier on the one
      underlying.
    * Leveraged basket: notional = market_value * multiplier, split by
      normalized constituent weights.
    * Everything else (plain stock/ETF): notional = market_value on its own
      ticker (treated as 1x exposure to itself).
    """
    notional: dict[str, float] = {}
    contributions: list[tuple[str, str, float]] = []
    total_equity = 0.0

    for h in holdings:
        total_equity += h.market_value
        prod = registry.get(h.ticker)
        if prod is None:
            notional[h.ticker] = notional.get(h.ticker, 0.0) + h.market_value
            contributions.append((h.ticker, h.ticker, h.market_value))
            continue
        gross = h.market_value * prod.multiplier
        for underlying, weight in prod.normalized_constituents().items():
            amt = gross * weight
            notional[underlying] = notional.get(underlying, 0.0) + amt
            contributions.append((h.ticker, underlying, amt))

    total_notional = sum(notional.values())
    return LookThrough(
        total_equity=total_equity,
        notional_by_underlying=notional,
        total_notional=total_notional,
        contributions=contributions,
    )
