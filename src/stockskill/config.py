"""Static configuration: factor/sector grouping for exposure aggregation.

This is a lookup table, not a model. Edit freely as holdings change.
"""

from __future__ import annotations

# Underlying ticker -> group label, for portfolio.risk.group_exposure.
FACTOR_GROUPS: dict[str, str] = {
    # mega-cap platforms
    "AAPL": "mega-cap platform", "MSFT": "mega-cap platform",
    "GOOGL": "mega-cap platform", "GOOG": "mega-cap platform",
    "AMZN": "mega-cap platform", "META": "mega-cap platform",
    "NFLX": "mega-cap platform",
    # AI / semiconductors
    "NVDA": "AI / semis", "AVGO": "AI / semis", "AMD": "AI / semis",
    # software growth
    "CRM": "software growth", "CRWD": "software growth",
    "SNOW": "software growth", "PLTR": "software growth",
    "UBER": "software growth",
    # crypto-linked
    "COIN": "crypto-linked",
    # EV / auto
    "TSLA": "EV / auto",
    # defensive (recession playbook targets)
    "COST": "defensive staples", "PEP": "defensive staples",
    "PG": "defensive staples", "KO": "defensive staples",
    "WMT": "defensive staples",
}
