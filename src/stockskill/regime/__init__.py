"""Trend & regime models: time-series momentum and a 2-state bull/bear filter.

These are *research-grounded* trend reads (Moskowitz-Ooi-Pedersen time-series
momentum; Dai-Zhang-Zhu regime-switching), distinct from the chart-indicator
states in ``signals/``. Pure, tested functions; outputs are model reads, not
advice.
"""

from .tsmom import TSMom, tsmom
from .dzz import DZZ, RegimeParams, dzz_rule, estimate_regimes, filter_p_bull

__all__ = ["TSMom", "tsmom", "DZZ", "RegimeParams", "dzz_rule",
           "estimate_regimes", "filter_p_bull"]

from .stops import StopStudy, stop_study  # noqa: E402

__all__ += ["StopStudy", "stop_study"]
