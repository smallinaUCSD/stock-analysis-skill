"""Market-indicators bar: indices, commodities, crypto — last price + day change.

Quote computation is pure (given a price map); the CLI fetches the series. Some
of these (gold, VIX, dollar) also appear in the regime snapshot; here they form
the top-of-dashboard ticker strip.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..technicals.changes import pct_change

INDICES = {"^DJI": "Dow", "^GSPC": "S&P 500", "^IXIC": "Nasdaq"}
COMMODITIES = {"GC=F": "Gold", "SI=F": "Silver", "HG=F": "Copper",
               "CL=F": "Crude Oil", "NG=F": "Nat Gas", "PL=F": "Platinum",
               "ZS=F": "Soybeans", "ZC=F": "Corn", "ZW=F": "Wheat"}
CRYPTO = {"BTC-USD": "Bitcoin", "ETH-USD": "Ethereum"}
# index ETFs used for rotation (liquid, clean intraday)
ROTATION = {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "IWM": "Small caps",
            "MDY": "Mid caps", "RSP": "Equal weight"}

_BAR = {**INDICES, **COMMODITIES, **CRYPTO}


def all_market_tickers() -> list[str]:
    """Every ticker the market bar + rotation needs fetched."""
    return list(dict.fromkeys([*_BAR, *ROTATION]))


@dataclass
class Quote:
    ticker: str
    name: str
    last: float | None
    change: float | None    # day % change (decimal)
    group: str              # index | commodity | crypto


def market_quotes(price_map: dict[str, list[float]]) -> list[Quote]:
    """Last price + day change for each market-bar instrument."""
    groups = [(INDICES, "index"), (COMMODITIES, "commodity"), (CRYPTO, "crypto")]
    out: list[Quote] = []
    for mapping, group in groups:
        for tk, name in mapping.items():
            c = price_map.get(tk, [])
            out.append(Quote(tk, name, c[-1] if c else None,
                             pct_change(c, 1), group))
    return out
