"""Turn several years of filed financials into steadier valuation inputs.

One trailing year of free cash flow swings with capital-spending cycles, tax
timing and working capital, and one reported growth rate can be a single hot
quarter. Following standard practice (Damodaran, "Investment Valuation";
Greenwald on normalized earnings), the DCF instead starts from:

* cash flow = the average over the last few years of operating cash flow,
  minus capital spending, minus stock-based pay (a real cost to shareholders
  that operating cash flow adds back), and
* growth = the compound annual growth of revenue over the last few years.

Pure functions over the rows from ``data.sec.extract_annual``.
"""

from __future__ import annotations


def _last(years: list[dict], n: int, asof: str | None = None) -> list[dict]:
    """The last ``n`` fiscal years (optionally only those public by ``asof``)."""
    ys = [y for y in years if asof is None or (y.get("filed") or "9999") <= asof]
    return ys[-n:]


def owner_cash_flow(y: dict) -> float | None:
    """Operating cash flow - capital spending - stock-based pay for one year."""
    ocf, capex = y.get("ocf"), y.get("capex")
    if ocf is None or capex is None:
        return None
    return ocf - abs(capex) - abs(y.get("sbc") or 0.0)


def normalized_cash_flow(years: list[dict], n: int = 3, asof: str | None = None) -> dict | None:
    """Average owner cash flow over the last ``n`` years (needs at least 2).

    Returns {value, years: [(end, value)], sbc_included} or None."""
    rows = [(y["end"], owner_cash_flow(y), y.get("sbc") is not None) for y in _last(years, n, asof)]
    rows = [r for r in rows if r[1] is not None]
    if len(rows) < 2:
        return None
    return {"value": sum(v for _, v, _ in rows) / len(rows),
            "years": [(e, v) for e, v, _ in rows],
            "sbc_included": all(s for _, _, s in rows)}


def revenue_cagr(years: list[dict], n: int = 3, asof: str | None = None) -> float | None:
    """Compound annual revenue growth over the last ``n`` years (n+1 data points)."""
    rows = [y for y in _last(years, n + 1, asof) if y.get("revenue")]
    if len(rows) < 2 or rows[0]["revenue"] <= 0 or rows[-1]["revenue"] <= 0:
        return None
    span = len(rows) - 1
    return (rows[-1]["revenue"] / rows[0]["revenue"]) ** (1.0 / span) - 1.0


def latest(years: list[dict], key: str, asof: str | None = None):
    for y in reversed(_last(years, 99, asof)):
        if y.get(key) is not None:
            return y[key]
    return None
