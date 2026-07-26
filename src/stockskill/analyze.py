"""Full single-stock analysis payload for the interactive server.

Assembles the tested pieces (valuation, scenarios, options data, reported
analyst consensus) into one JSON-serializable dict. Every number traces to a
tested function or is clearly labeled reported third-party data.

IMPORTANT boundary: this produces *analysis* -- a valuation signal (where price
sits vs. our computed fair value) and reported analyst consensus. It does NOT
emit a personalized buy/sell/hold instruction. The decision is the user's.
"""

from __future__ import annotations

from .data.fundamentals import fetch_snapshot, FundamentalSnapshot
from .data.options import fetch_options_snapshot
from .valuation.service import Assumptions, value_snapshot
from .valuation.scenarios import three_scenarios


def pick_growth(snap: FundamentalSnapshot, fallback: float = 0.08,
                lo: float = 0.03, hi: float = 0.30) -> tuple[float, str]:
    """Data-driven base-case growth: reported revenue (or earnings) growth,
    clamped to a sane band. Deterministic; returns (growth, source-label)."""
    g = snap.revenue_growth if snap.revenue_growth is not None else snap.earnings_growth
    if g is None:
        return fallback, "default (no reported growth)"
    src = "revenue growth" if snap.revenue_growth is not None else "earnings growth"
    clamped = max(lo, min(hi, g))
    tag = src if clamped == g else f"{src}, clamped to {hi:.0%}"
    return clamped, tag


def _reco_label(mean: float | None, key: str | None) -> str:
    if key:
        return key.replace("_", " ").title()
    if mean is None:
        return "n/a"
    if mean <= 1.5:
        return "Strong Buy"
    if mean <= 2.5:
        return "Buy"
    if mean <= 3.5:
        return "Hold"
    if mean <= 4.5:
        return "Sell"
    return "Strong Sell"


def analyze_ticker(ticker: str, growth: float | None = None,
                   snapshot: FundamentalSnapshot | None = None,
                   with_options: bool = True) -> dict:
    snap = snapshot or fetch_snapshot(ticker)
    if growth is not None:
        growth_used, growth_source = growth, "user-specified"
    else:
        growth_used, growth_source = pick_growth(snap)
    a = Assumptions(stage1_growth=growth_used)

    base_out = value_snapshot(snap, a)
    rep = base_out.report
    rng = rep.range()
    scen = three_scenarios(snap, a)
    fv = scen.fair_values()

    price = snap.price
    target = snap.target_mean
    valuation = {
        "price": price,
        "fair_value_base": rep.weighted_base(),
        "fair_value_low": rng[0] if rng else None,
        "fair_value_high": rng[2] if rng else None,
        "bear": fv["bear"], "base": fv["base"], "bull": fv["bull"],
        "margin_of_safety": rep.margin_of_safety(),
        "signal": rep.verdict(),
        "discount_rate": base_out.discount_rate,
        "implied_market_growth": base_out.implied_market_growth,
        "methods": [
            {"method": e.method, "fair_value": e.fair_value, "note": e.note}
            for e in rep.estimates
        ],
        "warnings": base_out.warnings,
        "assumptions": {
            "stage1_growth": a.stage1_growth,
            "stage1_years": a.stage1_years,
            "terminal_growth": a.terminal_growth,
            "growth_source": growth_source,
        },
    }

    consensus = {
        "reco": _reco_label(snap.analyst_mean, snap.analyst_reco),
        "mean": snap.analyst_mean,
        "count": snap.analyst_count,
        "target_mean": target,
        "target_vs_price": ((target / price - 1.0) if (target and price) else None),
    }

    options = None
    if with_options:
        opt = fetch_options_snapshot(snap.ticker, spot=price)
        if opt.available:
            options = {
                "expiry": opt.expiry,
                "atm_call": _quote(opt.atm_call),
                "atm_put": _quote(opt.atm_put),
                "put_call_iv_skew": opt.put_call_iv_skew,
            }
        else:
            options = {"available": False, "note": opt.note}

    return {
        "ticker": snap.ticker,
        "name": snap.name or snap.ticker,
        "currency": snap.currency,
        "as_of": snap.as_of,
        "price": price,
        "beta": snap.beta,
        "dividend_yield": (snap.dividend_annual / price) if (snap.dividend_annual and price) else None,
        "valuation": valuation,
        "consensus": consensus,
        "options": options,
        "disclaimer": ("Analysis, not investment advice. The valuation signal "
                       "reflects price vs. this tool's DCF-based fair value; the "
                       "consensus is reported third-party data. The buy/sell/hold "
                       "decision is yours."),
    }


def _quote(q) -> dict | None:
    if q is None:
        return None
    return {"strike": q.strike, "last_price": q.last_price, "implied_vol": q.implied_vol}
