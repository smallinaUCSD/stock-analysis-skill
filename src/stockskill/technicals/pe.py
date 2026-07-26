"""Denoised P/E features: level vs history, not just the raw ratio.

Raw P/E is noisy and not comparable across companies. These express P/E
relative to a company's own history, which is far more informative:
* how far current P/E sits from its multi-year average (a re-rating signal), and
* how volatile P/E has been (uncertainty in how the market prices earnings).

Pure functions over a series of historical P/E values (oldest -> newest).
"""

from __future__ import annotations

import pandas as pd


def pe_relative_to_avg(pe_history, current_pe: float | None = None) -> float | None:
    """current_pe / average(pe_history) - 1 (0.20 == 20% above its own average).

    ``current_pe`` defaults to the last value in the history.
    """
    s = pd.Series(list(pe_history), dtype="float64").dropna()
    s = s[s > 0]
    if s.empty:
        return None
    cur = current_pe if current_pe is not None else s.iloc[-1]
    avg = s.mean()
    if avg == 0:
        return None
    return float(cur / avg - 1.0)


def pe_volatility(pe_history) -> float | None:
    """Standard deviation of the P/E series (absolute multiple points)."""
    s = pd.Series(list(pe_history), dtype="float64").dropna()
    s = s[s > 0]
    if len(s) < 2:
        return None
    return float(s.std(ddof=1))
