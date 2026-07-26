"""Monte Carlo simulation: fit drift/vol from history, simulate outcome
distributions. The project's modeling ("ML") step -- probabilities, not predictions.
"""

from .simulate import (
    MCResult, montecarlo, estimate_params, summarize, daily_returns, TRADING_DAYS,
)

__all__ = [
    "MCResult", "montecarlo", "estimate_params", "summarize",
    "daily_returns", "TRADING_DAYS",
]
