"""Factor investing: score a universe on value / quality / momentum.

Cross-sectional factor scoring, grounded in the factor-investing literature
(Fama-French value & size, Jegadeesh-Titman momentum, Novy-Marx / AQR quality).
The value factor is built from the same fundamentals the valuation engine uses
(earnings yield, FCF yield, EV/EBITDA, sales yield); momentum from price history.

Design contract (same as the rest of the tool): the math is tested pure Python;
data is fetched separately. Factors are *relative* reads across the universe, not
buy/sell advice -- a name ranks "cheap vs its peers here", never "cheap, buy it".
"""

from .model import (
    FACTORS, FactorScore, DEFAULT_WEIGHTS,
    factor_metrics, momentum_12_1, annualized_vol, score_factors, weights_from_env,
)

__all__ = [
    "FACTORS", "FactorScore", "DEFAULT_WEIGHTS",
    "factor_metrics", "momentum_12_1", "annualized_vol", "score_factors",
    "weights_from_env",
]
