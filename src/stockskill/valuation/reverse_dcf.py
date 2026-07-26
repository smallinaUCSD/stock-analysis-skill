"""Reverse DCF: what growth is the market already pricing in?

Instead of guessing growth to produce a value, we take the *current price*
as truth and solve for the stage-1 growth rate that the DCF would need to
justify it. If the market-implied growth looks heroic versus history, the
stock is priced for perfection; if it's modest, expectations are low.
"""

from __future__ import annotations

from .dcf import DCFInputs, two_stage_dcf


def implied_stage1_growth(
    price: float,
    inp: DCFInputs,
    lo: float = -0.50,
    hi: float = 1.00,
    tol: float = 1e-4,
    max_iter: int = 200,
) -> float | None:
    """Solve for the stage-1 growth that makes DCF fair value == ``price``.

    Bisection over stage-1 growth in ``[lo, hi]`` (decimals). Everything else
    in ``inp`` (discount rate, terminal growth, years, net debt, shares) is
    held fixed. Returns the implied annual growth, or None if ``price`` is
    outside the achievable range on this bracket.
    """
    if price <= 0:
        raise ValueError("price must be positive")

    def value_at(g: float) -> float:
        trial = DCFInputs(
            fcf0=inp.fcf0,
            shares=inp.shares,
            net_debt=inp.net_debt,
            discount_rate=inp.discount_rate,
            stage1_growth=g,
            stage1_years=inp.stage1_years,
            terminal_growth=inp.terminal_growth,
            fade=inp.fade,
            fade_to=inp.fade_to,
        )
        return two_stage_dcf(trial).fair_value_per_share

    v_lo = value_at(lo)
    v_hi = value_at(hi)
    # value is monotonically increasing in growth; price must be bracketed
    if not (min(v_lo, v_hi) <= price <= max(v_lo, v_hi)):
        return None

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        v_mid = value_at(mid)
        if abs(v_mid - price) < tol:
            return mid
        if (v_mid < price) == (v_lo < price):
            lo, v_lo = mid, v_mid
        else:
            hi, v_hi = mid, v_mid
    return 0.5 * (lo + hi)
