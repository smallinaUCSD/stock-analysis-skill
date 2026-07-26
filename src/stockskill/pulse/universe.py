"""ETF proxies used to read the market's pulse from free data.

Sector SPDRs for sector rotation, factor pairs for style/risk rotation, and a
small set of macro tickers for a regime snapshot. All liquid, free to pull.
"""

from __future__ import annotations

SECTOR_ETFS: dict[str, str] = {
    "XLK": "Technology",
    "XLC": "Communication Svcs",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
}

# (label, numerator ticker, denominator ticker): RS = ret(num) - ret(den).
# Positive = the first leg is leading (risk-on read for most of these).
FACTOR_PAIRS: list[tuple[str, str, str]] = [
    ("Growth vs Value", "VUG", "VTV"),
    ("Small vs Large", "IWM", "SPY"),
    ("High-beta vs Low-vol", "SPHB", "SPLV"),
    ("Cyclicals vs Defensives", "XLY", "XLP"),
    ("Semis vs Market", "SMH", "SPY"),
]

REGIME_TICKERS: dict[str, str] = {
    "SPY": "S&P 500",
    "RSP": "S&P 500 Equal Weight",
    "^VIX": "VIX (volatility)",
    "^TNX": "10Y Treasury yield",
    "^IRX": "13-week T-bill yield",
    "HYG": "High-yield credit",
    "LQD": "Investment-grade credit",
    "UUP": "US Dollar",
    "GLD": "Gold",
}

# All tickers the pulse command needs to fetch.
def all_tickers() -> list[str]:
    tickers: set[str] = set(SECTOR_ETFS) | set(REGIME_TICKERS)
    for _, num, den in FACTOR_PAIRS:
        tickers.add(num)
        tickers.add(den)
    return sorted(tickers)
