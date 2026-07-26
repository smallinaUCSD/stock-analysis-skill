"""Relative (multiples-based) valuation.

Values a company off comparable multiples applied to its own fundamentals.
Deterministic arithmetic -- the judgement (which peers, which multiple) is
an input, not something guessed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True)
class MultiplesInputs:
    shares: float
    net_debt: float = 0.0
    eps: float | None = None        # trailing or forward EPS
    ebitda: float | None = None
    revenue: float | None = None
    fcf: float | None = None


def _per_share_from_equity_multiple(metric_per_share: float, multiple: float) -> float:
    return metric_per_share * multiple


def _per_share_from_ev_multiple(metric_total: float, multiple: float,
                                net_debt: float, shares: float) -> float:
    ev = metric_total * multiple
    equity = ev - net_debt
    return equity / shares


def value_from_multiples(
    inp: MultiplesInputs,
    pe: float | None = None,
    ev_ebitda: float | None = None,
    ps: float | None = None,
    p_fcf: float | None = None,
) -> dict[str, float]:
    """Implied fair value per share for each provided peer multiple.

    ``pe`` and ``ps`` (P/FCF too) are equity multiples applied to per-share
    metrics; ``ev_ebitda`` is an enterprise multiple net of debt. Only the
    methods whose inputs are present are returned.
    """
    out: dict[str, float] = {}
    if pe is not None and inp.eps is not None:
        out["P/E"] = _per_share_from_equity_multiple(inp.eps, pe)
    if ps is not None and inp.revenue is not None:
        out["P/S"] = _per_share_from_equity_multiple(inp.revenue / inp.shares, ps)
    if p_fcf is not None and inp.fcf is not None:
        out["P/FCF"] = _per_share_from_equity_multiple(inp.fcf / inp.shares, p_fcf)
    if ev_ebitda is not None and inp.ebitda is not None:
        out["EV/EBITDA"] = _per_share_from_ev_multiple(
            inp.ebitda, ev_ebitda, inp.net_debt, inp.shares
        )
    return out


def blended_multiples_value(values: dict[str, float]) -> float | None:
    """Median across the per-method implied values (robust to one outlier)."""
    vals = [v for v in values.values() if v == v]  # drop NaN
    return median(vals) if vals else None
