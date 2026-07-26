"""Discounted cash flow valuation.

Pure functions only: every input is an explicit number, every output is
deterministic. No network, no global state, no LLM estimation. Feed these
from the data layer (``stockskill.data``) or from hand-entered assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DCFInputs:
    """Inputs to a two-stage free-cash-flow-to-firm DCF.

    All rates are decimals (0.10 == 10%). Money units must be consistent
    (all dollars, or all millions) -- the model does not care which as long
    as ``fcf0``, ``net_debt`` are in the same units and ``shares`` is a raw
    count in that scale.
    """

    fcf0: float                    # most recent trailing free cash flow to firm
    shares: float                  # diluted shares outstanding
    net_debt: float = 0.0          # total debt minus cash & equivalents
    discount_rate: float = 0.09    # WACC
    stage1_growth: float = 0.10    # annual FCF growth during the explicit window
    stage1_years: int = 10         # length of the explicit forecast window
    terminal_growth: float = 0.025 # perpetual growth after the window

    def validate(self) -> None:
        if self.shares <= 0:
            raise ValueError("shares must be positive")
        if self.stage1_years < 1:
            raise ValueError("stage1_years must be >= 1")
        if self.discount_rate <= self.terminal_growth:
            raise ValueError(
                "discount_rate must exceed terminal_growth for a finite "
                f"terminal value (got r={self.discount_rate}, g={self.terminal_growth})"
            )


@dataclass(frozen=True)
class DCFResult:
    fair_value_per_share: float
    enterprise_value: float
    equity_value: float
    pv_explicit: float
    pv_terminal: float
    terminal_value_pct: float      # share of EV coming from the terminal value
    projected_fcf: tuple[float, ...] = field(default_factory=tuple)


def two_stage_dcf(inp: DCFInputs) -> DCFResult:
    """Two-stage FCFF DCF.

    Stage 1: ``stage1_years`` of explicit FCF growing at ``stage1_growth``,
    each year discounted at ``discount_rate``.
    Terminal: Gordon-growth perpetuity on year-N+1 FCF, discounted back.
    Equity value = enterprise value - net debt. Per share = equity / shares.
    """
    inp.validate()
    r = inp.discount_rate
    g1 = inp.stage1_growth
    gt = inp.terminal_growth

    pv_explicit = 0.0
    projected: list[float] = []
    fcf = inp.fcf0
    last_fcf = inp.fcf0
    for year in range(1, inp.stage1_years + 1):
        fcf = fcf * (1.0 + g1)
        projected.append(fcf)
        pv_explicit += fcf / (1.0 + r) ** year
        last_fcf = fcf

    terminal_fcf = last_fcf * (1.0 + gt)
    terminal_value = terminal_fcf / (r - gt)
    pv_terminal = terminal_value / (1.0 + r) ** inp.stage1_years

    enterprise_value = pv_explicit + pv_terminal
    equity_value = enterprise_value - inp.net_debt
    per_share = equity_value / inp.shares

    return DCFResult(
        fair_value_per_share=per_share,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        pv_explicit=pv_explicit,
        pv_terminal=pv_terminal,
        terminal_value_pct=pv_terminal / enterprise_value if enterprise_value else float("nan"),
        projected_fcf=tuple(projected),
    )


def sensitivity_grid(
    inp: DCFInputs,
    discount_rates: list[float],
    terminal_growths: list[float],
) -> list[list[float]]:
    """Fair-value-per-share grid across discount-rate x terminal-growth.

    Returns rows indexed by ``discount_rates`` and columns by
    ``terminal_growths``. NaN where the (r <= g) constraint is violated.
    """
    grid: list[list[float]] = []
    for r in discount_rates:
        row: list[float] = []
        for gt in terminal_growths:
            try:
                trial = DCFInputs(
                    fcf0=inp.fcf0,
                    shares=inp.shares,
                    net_debt=inp.net_debt,
                    discount_rate=r,
                    stage1_growth=inp.stage1_growth,
                    stage1_years=inp.stage1_years,
                    terminal_growth=gt,
                )
                row.append(two_stage_dcf(trial).fair_value_per_share)
            except ValueError:
                row.append(float("nan"))
        grid.append(row)
    return grid
