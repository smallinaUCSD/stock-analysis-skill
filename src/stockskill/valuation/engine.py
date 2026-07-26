"""Valuation engine: blend methods into a fair-value range + margin of safety.

This is the object the ``value TICKER`` command produces. It runs every
applicable method, records each estimate, and reports a low/base/high range
plus how far the current price sits from base (the margin of safety). Every
number here is arithmetic over inputs -- nothing is invented.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def capm_cost_of_equity(risk_free: float, beta: float, equity_premium: float = 0.05) -> float:
    """k_e = r_f + beta * equity risk premium."""
    return risk_free + beta * equity_premium


@dataclass
class ValuationEstimate:
    method: str
    fair_value: float
    weight: float = 1.0
    note: str = ""


@dataclass
class ValuationReport:
    ticker: str
    price: float
    estimates: list[ValuationEstimate] = field(default_factory=list)

    def add(self, method: str, fair_value: float, weight: float = 1.0, note: str = "") -> None:
        if fair_value is None or fair_value != fair_value:  # None or NaN
            return
        self.estimates.append(ValuationEstimate(method, fair_value, weight, note))

    @property
    def values(self) -> list[float]:
        return [e.fair_value for e in self.estimates]

    def weighted_base(self) -> float | None:
        """Weighted-average fair value across methods."""
        if not self.estimates:
            return None
        total_w = sum(e.weight for e in self.estimates)
        if total_w == 0:
            return None
        return sum(e.fair_value * e.weight for e in self.estimates) / total_w

    def range(self) -> tuple[float, float, float] | None:
        """(low, base, high) = (min estimate, weighted base, max estimate)."""
        if not self.estimates:
            return None
        vals = self.values
        return (min(vals), self.weighted_base(), max(vals))

    def margin_of_safety(self) -> float | None:
        """(base_fair_value - price) / base_fair_value.

        Positive => trading below estimated intrinsic value (a discount);
        negative => trading above it (a premium / priced for perfection).
        """
        base = self.weighted_base()
        if base is None or base == 0:
            return None
        return (base - self.price) / base

    def verdict(self) -> str:
        mos = self.margin_of_safety()
        if mos is None:
            return "insufficient data"
        if mos >= 0.30:
            return "deep discount (>30% below base)"
        if mos >= 0.10:
            return "undervalued (10-30% below base)"
        if mos > -0.10:
            return "roughly fair (within +-10%)"
        if mos > -0.30:
            return "expensive (10-30% above base)"
        return "priced for perfection (>30% above base)"
