"""Accounting-quality checks from two years of financial statements.

* Piotroski (2000), "Value Investing: The Use of Historical Financial
  Statement Information" (Journal of Accounting Research): nine pass/fail tests
  on profitability, funding and efficiency. High scores (8-9) flag improving,
  financially sound firms; low scores (0-2) flag deteriorating ones.
* Sloan (1996), "Do Stock Prices Fully Reflect Information in Accruals and
  Cash Flows about Future Earnings?" (The Accounting Review): earnings well
  above operating cash flow (high accruals) tend to be followed by weaker
  earnings and returns.

Inputs are plain dicts per fiscal year with keys: net_income, total_assets,
cfo, long_term_debt, current_assets, current_liabilities, shares, revenue,
gross_profit. Missing items make their check None (skipped), never guessed.
"""

from __future__ import annotations


def _ratio(a, b):
    try:
        return a / b if (a is not None and b) else None
    except (TypeError, ZeroDivisionError):
        return None


def _gt(a, b):
    return None if (a is None or b is None) else a > b


def piotroski(cur: dict, prev: dict) -> dict:
    """F-score over the checks the data allows: {score, max, checks}.

    ``checks`` is [(name, passed True/False/None, detail)]."""
    roa, roa0 = _ratio(cur.get("net_income"), cur.get("total_assets")), \
        _ratio(prev.get("net_income"), prev.get("total_assets"))
    cfo_a = _ratio(cur.get("cfo"), cur.get("total_assets"))
    lev, lev0 = _ratio(cur.get("long_term_debt"), cur.get("total_assets")), \
        _ratio(prev.get("long_term_debt"), prev.get("total_assets"))
    cr, cr0 = _ratio(cur.get("current_assets"), cur.get("current_liabilities")), \
        _ratio(prev.get("current_assets"), prev.get("current_liabilities"))
    gm, gm0 = _ratio(cur.get("gross_profit"), cur.get("revenue")), \
        _ratio(prev.get("gross_profit"), prev.get("revenue"))
    at, at0 = _ratio(cur.get("revenue"), cur.get("total_assets")), \
        _ratio(prev.get("revenue"), prev.get("total_assets"))
    sh, sh0 = cur.get("shares"), prev.get("shares")

    def pct(x):
        return "n/a" if x is None else f"{x * 100:.1f}%"
    checks = [
        ("Profitable (return on assets above 0)", None if roa is None else roa > 0, pct(roa)),
        ("Positive operating cash flow", None if cur.get("cfo") is None else cur["cfo"] > 0,
         pct(cfo_a) + " of assets"),
        ("Return on assets improved", _gt(roa, roa0), f"{pct(roa0)} to {pct(roa)}"),
        ("Cash flow exceeds earnings", _gt(cfo_a, roa), "low accruals" if _gt(cfo_a, roa) else "earnings > cash flow"),
        ("Less long-term debt (vs assets)", None if (lev is None or lev0 is None) else lev <= lev0,
         f"{pct(lev0)} to {pct(lev)}"),
        ("Current ratio improved", _gt(cr, cr0),
         "n/a" if cr is None or cr0 is None else f"{cr0:.2f} to {cr:.2f}"),
        ("No new shares issued", None if (sh is None or sh0 is None) else sh <= sh0 * 1.005,
         "n/a" if sh is None or sh0 is None else f"{(sh / sh0 - 1) * 100:+.1f}% shares"),
        ("Gross margin improved", _gt(gm, gm0), f"{pct(gm0)} to {pct(gm)}"),
        ("Asset turnover improved", _gt(at, at0),
         "n/a" if at is None or at0 is None else f"{at0:.2f} to {at:.2f}"),
    ]
    known = [c for c in checks if c[1] is not None]
    return {"score": sum(1 for c in known if c[1]), "max": len(known), "checks": checks}


def accruals_ratio(cur: dict, prev: dict | None = None) -> float | None:
    """Sloan accruals: (net income - operating cash flow) / average total assets.
    Negative = earnings backed by more cash than reported; high positive = a flag."""
    ni, cfo = cur.get("net_income"), cur.get("cfo")
    ta = cur.get("total_assets")
    if ni is None or cfo is None or not ta:
        return None
    ta0 = (prev or {}).get("total_assets")
    avg = (ta + ta0) / 2.0 if ta0 else ta
    return (ni - cfo) / avg


def quality_read(cur: dict, prev: dict) -> dict:
    """F-score + accruals with a one-line plain-English read."""
    f = piotroski(cur, prev)
    acc = accruals_ratio(cur, prev)
    if f["max"] < 6:
        label, tone = "Not enough statement data to score", "muted"
    else:
        frac = f["score"] / f["max"]
        if frac >= 0.75:
            label, tone = "Strong and improving fundamentals", "up"
        elif frac <= 0.34:
            label, tone = "Weak or deteriorating fundamentals", "down"
        else:
            label, tone = "Mixed fundamentals", "muted"
    if acc is not None and acc > 0.10:
        label += "; earnings run well ahead of cash flow"
        tone = "down" if tone != "up" else "muted"
    return {**f, "accruals": acc, "label": label, "tone": tone}
