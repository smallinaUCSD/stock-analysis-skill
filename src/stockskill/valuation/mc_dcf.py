"""Monte Carlo DCF — a fair-value *distribution*, not a single number.

Damodaran's probabilistic valuation: put distributions on the uncertain DCF
inputs (starting cash flow, growth, discount rate, terminal growth), run the
*same tested* two-stage DCF on each draw, and summarize the spread of fair
values — expected value, percentile bands, and P(undervalued) at today's price.

Deterministic given a seed. It samples the existing :func:`two_stage_dcf`, so it
can never diverge from the point model (with zero spread it reproduces it
exactly). This quantifies *assumed* input uncertainty — the bands are only as
honest as the spreads fed in.
"""

from __future__ import annotations

from dataclasses import dataclass

from .dcf import DCFInputs, two_stage_dcf


@dataclass(frozen=True)
class MCDCFSpec:
    base: DCFInputs                # the point-estimate inputs (the distribution centers)
    growth_sd: float = 0.04        # sd on stage-1 growth (decimal, e.g. 0.04 = ±4%)
    discount_sd: float = 0.010     # sd on the discount rate
    terminal_sd: float = 0.005     # sd on terminal growth
    fcf_cv: float = 0.10           # coeff. of variation on starting cash flow (margin/est. risk)
    growth_cap: float = 0.40       # clamp stage-1 growth draws
    rate_floor: float = 0.06       # clamp discount-rate draws
    rate_cap: float = 0.20


@dataclass(frozen=True)
class MCDCFResult:
    n_paths: int
    mean: float
    median: float
    std: float
    pctiles: dict                  # p5, p25, p50, p75, p95 of fair value / share
    spot: float | None
    prob_undervalued: float | None     # P(fair value > price)
    prob_upside_25: float | None       # P(fair value > 1.25 x price)
    prob_downside_25: float | None     # P(fair value < 0.75 x price)


def monte_carlo_dcf(spec: MCDCFSpec, price: float | None = None,
                    n_paths: int = 5000, seed: int = 7) -> MCDCFResult:
    """Sample fair value over distributions of the DCF inputs."""
    import numpy as np

    rng = np.random.default_rng(seed)
    b = spec.base
    n = int(n_paths)

    g1 = rng.normal(b.stage1_growth, spec.growth_sd, n)
    r = np.clip(rng.normal(b.discount_rate, spec.discount_sd, n), spec.rate_floor, spec.rate_cap)
    gt = rng.normal(b.terminal_growth, spec.terminal_sd, n)
    fcf_mult = rng.normal(1.0, spec.fcf_cv, n) if spec.fcf_cv > 0 else np.ones(n)

    # Enforce the model's constraints per draw: 0 <= terminal < discount, and
    # terminal <= stage-1 growth <= cap; keep starting cash flow positive.
    gt = np.clip(gt, 0.0, r - 0.005)
    g1 = np.clip(g1, gt, spec.growth_cap)
    fcf0 = b.fcf0 * np.clip(fcf_mult, 0.05, None)

    fvs = np.empty(n)
    for i in range(n):
        inp = DCFInputs(
            fcf0=float(fcf0[i]), shares=b.shares, net_debt=b.net_debt,
            discount_rate=float(r[i]), stage1_growth=float(g1[i]),
            stage1_years=b.stage1_years, terminal_growth=float(gt[i]),
            fade=b.fade, fade_to=b.fade_to)
        fvs[i] = two_stage_dcf(inp).fair_value_per_share

    pctiles = {k: float(np.percentile(fvs, q))
               for k, q in (("p5", 5), ("p25", 25), ("p50", 50), ("p75", 75), ("p95", 95))}
    has_p = price is not None and price > 0
    return MCDCFResult(
        n_paths=n, mean=float(fvs.mean()), median=float(np.median(fvs)),
        std=float(fvs.std()), pctiles=pctiles, spot=price,
        prob_undervalued=float(np.mean(fvs > price)) if has_p else None,
        prob_upside_25=float(np.mean(fvs > 1.25 * price)) if has_p else None,
        prob_downside_25=float(np.mean(fvs < 0.75 * price)) if has_p else None,
    )
