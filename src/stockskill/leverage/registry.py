"""Registry mapping leveraged products to their true underlying exposure.

Two product shapes:

* **single-stock** leveraged funds (AAPU -> 2x AAPL): one underlying, one
  daily multiplier.
* **basket** leveraged notes (FNGU -> 3x a 10-name index): many underlyings,
  each with an index weight, times a shared multiplier.

Basket constituents and even single-stock multipliers DRIFT -- issuers change
leverage factors (Direxion single-stock funds moved 1.5x -> 2x) and indices
rebalance. Every entry carries an ``as_of`` date and a ``verify`` flag. The
data layer can call :func:`override_constituents` with an issuer's published
daily holdings to replace a snapshot before any exposure math runs.

Nothing here estimates prices or returns; it only records structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class LeveragedProduct:
    ticker: str
    name: str
    kind: str                       # "single" | "basket"
    multiplier: float               # daily leverage factor (e.g. 2.0, 3.0)
    constituents: dict[str, float]  # underlying ticker -> index weight (sums ~1.0)
    structure: str = "ETF"          # "ETF" | "ETN"
    expense_ratio: float = 0.0
    as_of: str = "2026-01-01"
    verify: bool = True             # True => snapshot, confirm before relying on it

    def normalized_constituents(self) -> dict[str, float]:
        """Constituent weights renormalized to sum to 1.0."""
        total = sum(self.constituents.values())
        if total <= 0:
            return dict(self.constituents)
        return {k: v / total for k, v in self.constituents.items()}


# NYSE FANG+ index (FNGU underlying): 10 equal-weighted names, rebalanced
# quarterly. Snapshot -- VERIFY against the issuer's daily holdings file.
_FANG_PLUS = {
    "AAPL": 0.1, "AMZN": 0.1, "AVGO": 0.1, "CRWD": 0.1, "GOOGL": 0.1,
    "META": 0.1, "MSFT": 0.1, "NFLX": 0.1, "NVDA": 0.1, "PLTR": 0.1,
}

# Solactive FANG Innovation index (BULZ underlying): 15 tech/innovation names,
# roughly equal-weighted. Snapshot -- VERIFY.
_FANG_INNOVATION = {
    "AAPL": 1 / 15, "AMD": 1 / 15, "AMZN": 1 / 15, "AVGO": 1 / 15,
    "CRM": 1 / 15, "CRWD": 1 / 15, "GOOGL": 1 / 15, "META": 1 / 15,
    "MSFT": 1 / 15, "NFLX": 1 / 15, "NVDA": 1 / 15, "PLTR": 1 / 15,
    "SNOW": 1 / 15, "TSLA": 1 / 15, "UBER": 1 / 15,
}


_REGISTRY: dict[str, LeveragedProduct] = {
    "AAPU": LeveragedProduct("AAPU", "Direxion Daily AAPL Bull", "single", 2.0,
                             {"AAPL": 1.0}, expense_ratio=0.0113),
    "MSFU": LeveragedProduct("MSFU", "Direxion Daily MSFT Bull", "single", 2.0,
                             {"MSFT": 1.0}, expense_ratio=0.0113),
    "METU": LeveragedProduct("METU", "Direxion Daily META Bull", "single", 2.0,
                             {"META": 1.0}, expense_ratio=0.0113),
    "TSLL": LeveragedProduct("TSLL", "Direxion Daily TSLA Bull", "single", 2.0,
                             {"TSLA": 1.0}, expense_ratio=0.0084),
    "CONL": LeveragedProduct("CONL", "GraniteShares 2x Long COIN Daily", "single",
                             2.0, {"COIN": 1.0}, expense_ratio=0.0119),
    "PTIR": LeveragedProduct("PTIR", "GraniteShares 2x Long PLTR Daily", "single",
                             2.0, {"PLTR": 1.0}, expense_ratio=0.0119),
    "FNGU": LeveragedProduct("FNGU", "MicroSectors FANG+ 3X Leveraged ETN", "basket",
                             3.0, dict(_FANG_PLUS), structure="ETN",
                             expense_ratio=0.0095),
    "BULZ": LeveragedProduct("BULZ", "MicroSectors FANG & Innovation 3X ETN", "basket",
                             3.0, dict(_FANG_INNOVATION), structure="ETN",
                             expense_ratio=0.0095),
}


def get(ticker: str) -> LeveragedProduct | None:
    """Return the product for ``ticker`` (case-insensitive), or None."""
    return _REGISTRY.get(ticker.upper())


def is_leveraged(ticker: str) -> bool:
    return ticker.upper() in _REGISTRY


def all_products() -> dict[str, LeveragedProduct]:
    return dict(_REGISTRY)


def override_constituents(ticker: str, constituents: dict[str, float],
                          as_of: str) -> LeveragedProduct:
    """Replace a snapshot basket with live issuer holdings and clear ``verify``.

    Returns the updated product and stores it back in the registry so later
    look-through math uses the fresh weights.
    """
    prod = get(ticker)
    if prod is None:
        raise KeyError(f"{ticker} is not a known leveraged product")
    updated = replace(prod, constituents=dict(constituents), as_of=as_of, verify=False)
    _REGISTRY[ticker.upper()] = updated
    return updated
