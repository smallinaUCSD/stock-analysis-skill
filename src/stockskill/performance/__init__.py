"""Risk/return statistics against a benchmark (beta, alpha, Sharpe, drawdown...)
and the multi-ticker comparison built on them. Pure functions over price series."""

from .metrics import (RiskStats, align_closes, capture_ratios, drawdown_series,
                      jensen_alpha, max_drawdown, ols_fit, risk_stats, sharpe,
                      simple_returns, sortino, welch_beta)

__all__ = ["RiskStats", "align_closes", "capture_ratios", "drawdown_series",
           "jensen_alpha", "max_drawdown", "ols_fit", "risk_stats", "sharpe",
           "simple_returns", "sortino", "welch_beta"]
