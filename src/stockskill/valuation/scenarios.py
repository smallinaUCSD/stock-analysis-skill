"""Bear / base / bull valuation scenarios.

Same DCF machinery, three assumption sets. The bear case lowers growth and
raises the discount rate (higher risk premium); the bull case does the reverse.
This turns one fair-value point into an honest range that shows how sensitive
the answer is to the story you believe. Deterministic given the snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..data.fundamentals import FundamentalSnapshot
from .service import Assumptions, value_snapshot, ValuationOutput


@dataclass
class ScenarioSet:
    bear: ValuationOutput
    base: ValuationOutput
    bull: ValuationOutput

    def fair_values(self) -> dict[str, float | None]:
        return {
            "bear": self.bear.report.weighted_base(),
            "base": self.base.report.weighted_base(),
            "bull": self.bull.report.weighted_base(),
        }


def three_scenarios(
    snap: FundamentalSnapshot,
    base_assumptions: Assumptions | None = None,
    growth_delta: float = 0.04,
    erp_delta: float = 0.01,
    terminal_delta: float = 0.005,
) -> ScenarioSet:
    """Value the snapshot under bear / base / bull assumption sets.

    ``growth_delta`` shifts stage-1 growth, ``erp_delta`` shifts the equity risk
    premium (and thus the discount rate), ``terminal_delta`` shifts terminal
    growth. Bear = -growth, +risk, -terminal; bull = the mirror image.
    """
    base_a = base_assumptions or Assumptions()

    bear_a = replace(
        base_a,
        stage1_growth=max(0.0, base_a.stage1_growth - growth_delta),
        equity_premium=base_a.equity_premium + erp_delta,
        terminal_growth=max(0.0, base_a.terminal_growth - terminal_delta),
    )
    bull_a = replace(
        base_a,
        stage1_growth=base_a.stage1_growth + growth_delta,
        equity_premium=max(0.0, base_a.equity_premium - erp_delta),
        terminal_growth=base_a.terminal_growth + terminal_delta,
    )
    return ScenarioSet(
        bear=value_snapshot(snap, bear_a),
        base=value_snapshot(snap, base_a),
        bull=value_snapshot(snap, bull_a),
    )
