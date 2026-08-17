"""Cross-sectional factor scoring engine.

Each factor (value / quality / momentum) is a small basket of metrics. Every
metric is percentile-ranked across the universe (reusing the screener's tested
``percentile_ranks`` -- robust to outliers and mixed scales), inverted when
lower-is-better, and averaged into a factor score in [0,1]. Factor scores blend
into a composite, and each is re-ranked to a 0-100 percentile for display, so
"value 82" means literally *cheaper than 82% of the names in this universe*.

Missing inputs are excluded from that name's average and reflected in coverage --
never guessed. Deterministic: same rows -> same ranking.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..data.fundamentals import FundamentalSnapshot
from ..screener.criteria import MetricSpec, percentile_ranks

# ~21 trading days per month; 12-1 momentum skips the most recent month
# (Jegadeesh & Titman 1993) to avoid short-term reversal.
_MONTH = 21
_YEAR = 252


def _safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


# Each factor: (metric_name, weight, higher_is_better).
FACTORS: dict[str, list[MetricSpec]] = {
    "value": [
        MetricSpec("earnings_yield", 1.0, True),   # E/P  (inverse P/E)
        MetricSpec("fcf_yield", 1.0, True),        # FCF / market cap
        MetricSpec("ev_ebitda", 1.0, False),       # EV / EBITDA (cheaper = lower)
        MetricSpec("sales_yield", 1.0, True),      # revenue / market cap (inverse P/S)
        MetricSpec("dividend_yield", 0.5, True),
    ],
    "quality": [
        MetricSpec("roe", 1.0, True),
        MetricSpec("profit_margin", 1.0, True),
        MetricSpec("fcf_margin", 1.0, True),       # FCF / revenue
        MetricSpec("net_debt_to_ebitda", 1.0, False),  # less leverage = better
    ],
    "momentum": [
        MetricSpec("momentum", 1.0, True),         # 12-1 month return
    ],
    "growth": [
        MetricSpec("revenue_growth", 1.0, True),
        MetricSpec("earnings_growth", 1.0, True),
    ],
    "low_vol": [                                    # Frazzini-Pedersen "Betting Against Beta"
        MetricSpec("volatility", 1.0, False),       # trailing 1y realized vol (lower = better)
        MetricSpec("beta", 0.5, False),
    ],
}

# The composite blend. Value/quality/momentum are the core (the friend's ask);
# growth and low-vol tilt in at lower weight. Override with STOCKSKILL_FACTOR_WEIGHTS
# (e.g. "value:2,momentum:1,quality:1,growth:0,low_vol:0" for a value-heavy sleeve).
DEFAULT_WEIGHTS: dict[str, float] = {
    "value": 1.0, "quality": 1.0, "momentum": 1.0, "growth": 0.75, "low_vol": 0.75,
}


def weights_from_env() -> dict[str, float]:
    """Composite weights, overridable via STOCKSKILL_FACTOR_WEIGHTS='value:2,growth:0'."""
    import os
    w = dict(DEFAULT_WEIGHTS)
    raw = os.environ.get("STOCKSKILL_FACTOR_WEIGHTS", "")
    for part in raw.split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            try:
                w[k.strip()] = float(v)
            except ValueError:
                pass
    return w


@dataclass
class FactorScore:
    ticker: str
    factors: dict[str, float | None]        # raw factor composite in [0,1]
    factor_pct: dict[str, int | None]       # 0-100 percentile per factor (universe)
    composite: float | None                 # blended factor score in [0,1]
    composite_pct: int | None               # 0-100 percentile of the composite
    coverage: float                         # share of metrics present
    label: str
    raw: dict = field(default_factory=dict)


def momentum_12_1(closes: list[float]) -> float | None:
    """12-1 month price momentum: return from ~12mo ago to ~1mo ago.

    Skips the most recent month (short-term reversal). Needs ~1y of history;
    returns None otherwise so a young ticker isn't scored on noise.
    """
    n = len(closes or [])
    if n < 200:
        return None
    recent = closes[-_MONTH]                       # ~1 month ago
    old = closes[-min(_YEAR, n - 1)]               # ~12 months ago (or earliest)
    if not old:
        return None
    return recent / old - 1.0


def annualized_vol(closes: list[float]) -> float | None:
    """Trailing ~1y annualized realized volatility of daily returns. None if thin."""
    import math
    window = (closes or [])[-(_YEAR + 1):]
    rets = [b / a - 1.0 for a, b in zip(window[:-1], window[1:]) if a]
    if len(rets) < 20:
        return None
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return (var ** 0.5) * math.sqrt(_YEAR)


def factor_metrics(snap: FundamentalSnapshot, momentum: float | None = None,
                   volatility: float | None = None) -> dict:
    """Raw factor metrics for one name from its fundamentals. Missing -> None."""
    mcap = snap.market_cap
    ev = (mcap + snap.net_debt) if (mcap is not None and snap.net_debt is not None) else None
    return {
        "ticker": snap.ticker,
        "sector": snap.sector,
        # value
        "earnings_yield": _safe_div(snap.eps, snap.price),
        "fcf_yield": _safe_div(snap.fcf, mcap),
        "ev_ebitda": _safe_div(ev, snap.ebitda),
        "sales_yield": _safe_div(snap.revenue, mcap),
        "dividend_yield": _safe_div(snap.dividend_annual, snap.price),
        # quality
        "roe": snap.roe,
        "profit_margin": snap.profit_margin,
        "fcf_margin": _safe_div(snap.fcf, snap.revenue),
        "net_debt_to_ebitda": _safe_div(snap.net_debt, snap.ebitda),
        # momentum / growth / low-vol
        "momentum": momentum,
        "revenue_growth": snap.revenue_growth,
        "earnings_growth": snap.earnings_growth,
        "volatility": volatility,
        "beta": snap.beta,
    }


def _grouped_percentiles(values: list, groups: list, min_group: int = 4) -> list:
    """Percentile-rank ``values`` *within* each group in ``groups``.

    A group needs >= ``min_group`` present values to rank internally; smaller
    groups (and names with no group) fall back to the universe-wide rank, so a
    thin sector can't hand a lone name a spurious 0 or 100.
    """
    from collections import defaultdict

    global_ranks = percentile_ranks(values)
    out: list = [None] * len(values)
    members: dict = defaultdict(list)
    for i, g in enumerate(groups):
        members[g].append(i)
    for g, idxs in members.items():
        present = [i for i in idxs if values[i] is not None and values[i] == values[i]]
        if g is None or len(present) < min_group:
            for i in idxs:
                out[i] = global_ranks[i]
        else:
            sub = percentile_ranks([values[i] for i in idxs])
            for j, i in enumerate(idxs):
                out[i] = sub[j]
    return out


def _factor_composite(rows: list[dict], specs: list[MetricSpec],
                      groups: list | None = None, min_group: int = 4) -> list[tuple]:
    """Per-name (score in [0,1] or None, coverage in [0,1]) for one factor basket."""
    normalized: dict[str, list] = {}
    for spec in specs:
        col = [r.get(spec.name) for r in rows]
        pr = (_grouped_percentiles(col, groups, min_group) if groups is not None
              else percentile_ranks(col))
        if not spec.higher_is_better:
            pr = [None if x is None else (1.0 - x) for x in pr]
        normalized[spec.name] = pr

    total = sum(s.weight for s in specs) or 1.0
    out = []
    for i in range(len(rows)):
        num = den = 0.0
        for spec in specs:
            x = normalized[spec.name][i]
            if x is None:
                continue
            num += spec.weight * x
            den += spec.weight
        out.append((num / den if den > 0 else None, den / total))
    return out


def _pcts(vals: list) -> list:
    return [None if x is None else round(x * 100) for x in percentile_ranks(vals)]


def _label(fpct: dict, hi: int = 70, lo: int = 30) -> str:
    parts = []
    v, q, m = fpct.get("value"), fpct.get("quality"), fpct.get("momentum")
    if v is not None:
        parts.append("cheap" if v >= hi else "expensive" if v <= lo else None)
    if q is not None:
        parts.append("high quality" if q >= hi else "low quality" if q <= lo else None)
    if m is not None:
        parts.append("strong momentum" if m >= hi else "weak momentum" if m <= lo else None)
    parts = [p for p in parts if p]
    return " · ".join(parts) if parts else "in-line with peers"


def score_factors(rows: list[dict], weights: dict | None = None,
                  factors: dict | None = None, min_coverage: float = 0.5,
                  sector_neutral: bool = False, min_group: int = 4) -> list[FactorScore]:
    """Score a universe of metric rows. Returns FactorScores, best composite first.

    ``coverage`` is the weight-share of the composite's factors that a name
    actually has data for. Names below ``min_coverage`` (e.g. leveraged ETFs with
    only price-based factors) keep their individual factor scores but are withheld
    from the composite rank, so a one-factor name can't spuriously top the board.

    ``sector_neutral`` ranks each metric *within* the name's sector (from the
    "sector" key), so "cheap" means cheap-vs-peers rather than a bet on cheap
    sectors. Sectors thinner than ``min_group`` fall back to universe ranks.
    """
    factors = factors or FACTORS
    weights = weights or DEFAULT_WEIGHTS
    groups = [r.get("sector") for r in rows] if sector_neutral else None

    per_factor = {name: _factor_composite(rows, specs, groups, min_group)
                  for name, specs in factors.items()}
    active = [n for n in factors if weights.get(n, 0.0) > 0]
    total_w = sum(weights[n] for n in active) or 1.0

    blended = []
    for i, r in enumerate(rows):
        fdict = {name: per_factor[name][i][0] for name in factors}
        num = den = 0.0
        for name in active:
            s = per_factor[name][i][0]
            if s is not None:
                num += weights[name] * s
                den += weights[name]
        coverage = den / total_w
        composite = num / den if (den > 0 and coverage >= min_coverage) else None
        blended.append((r, fdict, composite, coverage))

    comp_pct = _pcts([c for _, _, c, _ in blended])
    fac_pct = {name: _pcts([fd[name] for _, fd, _, _ in blended]) for name in factors}

    out = []
    for i, (r, fdict, composite, cov) in enumerate(blended):
        fpct = {name: fac_pct[name][i] for name in factors}
        out.append(FactorScore(
            ticker=r.get("ticker", "?"), factors=fdict, factor_pct=fpct,
            composite=composite, composite_pct=comp_pct[i], coverage=cov,
            label=_label(fpct), raw=r,
        ))
    out.sort(key=lambda s: (s.composite_pct if s.composite_pct is not None else -1),
             reverse=True)
    return out
