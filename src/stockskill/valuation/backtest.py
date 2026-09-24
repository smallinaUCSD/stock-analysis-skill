"""Point-in-time test of the DCF: did stocks it called cheap beat the ones it
called expensive over the next year?

For every stock and every annual report inside the price history, rebuild the
fair value using ONLY what had been filed by that report's first public date
(SEC ``filed``), then record the value gap (fair value vs the market value on
the next trading day) and the following 12-month return. Within each year's
cross-section, measure the rank correlation between gap and return (the
information coefficient, IC) and the return spread between the cheapest and
the priciest third.

Two input recipes are compared:
* "one year": last year's operating cash flow - capex, last year's revenue
  growth, the stock's own beta (what the model did before SEC data), and
* "normalized": 3-year average of operating cash flow - capex - stock pay,
  3-year revenue CAGR (the SEC-based inputs).

Pure given its inputs. Prices are adjusted closes; share counts come from the
latest filings, which restate history for splits, and ``split_factor``
corrects any split since the last filing.
"""

from __future__ import annotations

import math
from bisect import bisect_left

from ..performance.metrics import align_closes, simple_returns, welch_beta
from .dcf import DCFInputs, two_stage_dcf
from .normalize import latest, normalized_cash_flow, owner_cash_flow, revenue_cagr

RF, ERP, FLOOR = 0.043, 0.05, 0.08
G_LO, G_HI = 0.03, 0.30


def _clamp(g):
    return None if g is None else max(G_LO, min(G_HI, g))


def fair_equity(years, asof, beta, recipe: str) -> tuple[float | None, dict]:
    """Fair equity value (dollars) from filings public by ``asof``."""
    ys = [y for y in years if (y.get("filed") or "9999") <= asof]
    if len(ys) < 2:
        return None, {}
    if recipe == "normalized":
        n = normalized_cash_flow(ys, 3)
        cf = n["value"] if n else None
        g = _clamp(revenue_cagr(ys, 3))
    else:
        cf = owner_cash_flow({**ys[-1], "sbc": 0.0})
        r0, r1 = ys[-2].get("revenue"), ys[-1].get("revenue")
        g = _clamp((r1 / r0 - 1.0) if (r0 and r1 and r0 > 0) else None)
    if cf is None or cf <= 0:                          # same fallback as the live model
        cf = ys[-1].get("net_income")
    if not cf or cf <= 0 or g is None or beta is None:
        return None, {}
    r = max(RF + beta * ERP, FLOOR)
    net_debt = (latest(ys, "long_term_debt") or 0.0) - (latest(ys, "cash") or 0.0)
    try:
        res = two_stage_dcf(DCFInputs(fcf0=cf, shares=1.0, net_debt=net_debt, discount_rate=r,
                                      stage1_growth=g, stage1_years=10, terminal_growth=0.025))
    except ValueError:
        return None, {}
    return res.fair_value_per_share, {"cf": cf, "g": g, "r": r}


def _spearman(x, y):
    n = len(x)
    if n < 5:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        rk = [0.0] * n
        for pos, i in enumerate(order):
            rk[i] = pos
        return rk
    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / n, sum(ry) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / (sx * sy) if sx and sy else None


def observations(universe: dict, bench: dict, recipe: str, horizon: int = 252) -> list[dict]:
    """[{ticker, cohort, gap, fwd}] for every (stock, annual report) pair.

    ``universe``: {ticker: {"years": [...], "dates": [...], "closes": [...],
    "split_factor": float}}; ``bench``: {"dates", "closes"} (SPY)."""
    out = []
    for t, u in universe.items():
        dates = [d.isoformat() if hasattr(d, "isoformat") else str(d) for d in u["dates"]]
        closes = u["closes"]
        sf = u.get("split_factor") or 1.0
        for y in u["years"]:
            f = y.get("filed")
            if not f:
                continue
            i = bisect_left(dates, f) + 1                  # first trading day after the filing
            if i < 253 or i + horizon >= len(closes):
                continue
            d_, a, b = align_closes(dates[i - 253:i], closes[i - 253:i], bench["dates"], bench["closes"])
            beta = welch_beta(simple_returns(a), simple_returns(b)) if len(a) > 60 else None
            fv, _ = fair_equity(u["years"], f, beta, recipe)
            shares = latest([z for z in u["years"] if (z.get("filed") or "9999") <= f], "shares")
            if fv is None or not shares:
                continue
            mcap = closes[i] * shares * sf
            out.append({"ticker": t, "cohort": dates[i][:4], "gap": fv / mcap - 1.0,
                        "fwd": closes[i + horizon] / closes[i] - 1.0})
    return out


def evaluate(obs: list[dict]) -> dict | None:
    """Average yearly IC and cheapest-minus-priciest third spread."""
    cohorts: dict[str, list[dict]] = {}
    for o in obs:
        cohorts.setdefault(o["cohort"], []).append(o)
    ics, spreads, per = [], [], []
    for c, rows in sorted(cohorts.items()):
        if len(rows) < 9:
            continue
        ic = _spearman([r["gap"] for r in rows], [r["fwd"] for r in rows])
        srt = sorted(rows, key=lambda r: r["gap"])
        k = len(srt) // 3
        cheap = sum(r["fwd"] for r in srt[-k:]) / k
        rich = sum(r["fwd"] for r in srt[:k]) / k
        ics.append(ic)
        spreads.append(cheap - rich)
        per.append({"year": c, "n": len(rows), "ic": ic, "cheap": cheap, "rich": rich})
    if not per:
        return None
    return {"years": per, "n_obs": sum(p["n"] for p in per),
            "ic": sum(ics) / len(ics), "spread": sum(spreads) / len(spreads),
            "hit": sum(1 for s in spreads if s > 0) / len(spreads)}
