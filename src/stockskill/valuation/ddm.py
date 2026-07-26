"""Dividend discount models, for the income / dividend-growth sleeve.

Gordon growth (single stage) and a two-stage variant for names whose payout
is growing fast now but will mature. Pure arithmetic.
"""

from __future__ import annotations


def gordon_growth_value(dividend_next: float, cost_of_equity: float,
                        growth: float) -> float:
    """Value = D1 / (k - g). Requires k > g."""
    if cost_of_equity <= growth:
        raise ValueError("cost_of_equity must exceed growth for Gordon growth")
    if dividend_next < 0:
        raise ValueError("dividend cannot be negative")
    return dividend_next / (cost_of_equity - growth)


def two_stage_ddm(
    dividend0: float,
    cost_of_equity: float,
    high_growth: float,
    high_years: int,
    terminal_growth: float,
) -> float:
    """High-growth dividends for ``high_years``, then Gordon perpetuity."""
    if cost_of_equity <= terminal_growth:
        raise ValueError("cost_of_equity must exceed terminal_growth")
    k = cost_of_equity
    pv = 0.0
    d = dividend0
    for year in range(1, high_years + 1):
        d = d * (1.0 + high_growth)
        pv += d / (1.0 + k) ** year
    terminal_div = d * (1.0 + terminal_growth)
    terminal_value = terminal_div / (k - terminal_growth)
    pv += terminal_value / (1.0 + k) ** high_years
    return pv


def implied_dividend_yield(price: float, dividend_annual: float) -> float:
    if price <= 0:
        raise ValueError("price must be positive")
    return dividend_annual / price
