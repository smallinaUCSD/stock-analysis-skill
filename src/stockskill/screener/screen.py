"""Screener: turn fundamentals snapshots into ranked shortlists.

Two lanes, matching the user's two sleeves:

* **core** -- quality + value + growth. Rewards cash generation, cheap
  enterprise multiples, strong margins/ROE, healthy balance sheet, some growth.
* **aggressive** -- growth + momentum + beta, for the high-octane satellite.
  Rewards revenue/earnings growth and price momentum; light on value.

Metric extraction and lane weights are the only judgement, and both are
explicit here. The ranking math is in ``criteria`` and fully tested.
"""

from __future__ import annotations

from ..data.fundamentals import FundamentalSnapshot
from .criteria import MetricSpec, ScoredName, score_universe


def _safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def extract_metrics(snap: FundamentalSnapshot, momentum: float | None = None) -> dict:
    """Compute the screenable metrics for one name. Missing inputs -> None."""
    mcap = snap.market_cap
    ev = (mcap + snap.net_debt) if (mcap is not None and snap.net_debt is not None) else None
    return {
        "ticker": snap.ticker,
        "fcf_yield": _safe_div(snap.fcf, mcap),
        "earnings_yield": _safe_div(snap.eps, snap.price),
        "ev_ebitda": _safe_div(ev, snap.ebitda),
        "net_debt_to_ebitda": _safe_div(snap.net_debt, snap.ebitda),
        "revenue_growth": snap.revenue_growth,
        "earnings_growth": snap.earnings_growth,
        "profit_margin": snap.profit_margin,
        "roe": snap.roe,
        "dividend_yield": _safe_div(snap.dividend_annual, snap.price),
        "beta": snap.beta,
        "momentum": momentum,
    }


LANES: dict[str, list[MetricSpec]] = {
    "core": [
        MetricSpec("fcf_yield", 2.0, True),
        MetricSpec("earnings_yield", 1.0, True),
        MetricSpec("ev_ebitda", 2.0, False),
        MetricSpec("profit_margin", 1.5, True),
        MetricSpec("roe", 1.5, True),
        MetricSpec("revenue_growth", 1.0, True),
        MetricSpec("net_debt_to_ebitda", 1.0, False),
        MetricSpec("dividend_yield", 0.5, True),
    ],
    "aggressive": [
        MetricSpec("revenue_growth", 2.5, True),
        MetricSpec("earnings_growth", 1.5, True),
        MetricSpec("momentum", 2.0, True),
        MetricSpec("beta", 1.0, True),
        MetricSpec("profit_margin", 0.5, True),
        MetricSpec("fcf_yield", 0.5, True),
    ],
}


def run_screen(
    snapshots: list[FundamentalSnapshot],
    lane: str = "core",
    momentum: dict[str, float] | None = None,
) -> list[ScoredName]:
    """Score a universe of snapshots under a lane preset.

    ``momentum`` optionally maps ticker -> trailing return; used by the
    aggressive lane. Names without it simply lose that component.
    """
    if lane not in LANES:
        raise ValueError(f"unknown lane '{lane}'; choose from {sorted(LANES)}")
    momentum = momentum or {}
    rows = [extract_metrics(s, momentum.get(s.ticker)) for s in snapshots]
    return score_universe(rows, LANES[lane])
