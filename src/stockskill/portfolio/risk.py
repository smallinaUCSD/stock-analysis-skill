"""Concentration and exposure risk metrics over look-through exposures.

All deterministic. Feed these the ``notional_by_underlying`` from
``lookthrough.expand`` (economic exposure) rather than raw position values,
so leverage and overlap are reflected.
"""

from __future__ import annotations

from dataclasses import dataclass


def herfindahl(weights: dict[str, float]) -> float:
    """Herfindahl-Hirschman Index of concentration (sum of squared shares).

    Weights are renormalized first. 1.0 == everything in one name;
    1/N == perfectly even across N names.
    """
    total = sum(weights.values())
    if total <= 0:
        return float("nan")
    return sum((w / total) ** 2 for w in weights.values())


def effective_number_of_bets(weights: dict[str, float]) -> float:
    """1 / HHI -- how many independent-sized positions you *effectively* hold.

    A portfolio that looks like 10 tickers but is 80% one name has an
    effective count far below 10.
    """
    hhi = herfindahl(weights)
    return 1.0 / hhi if hhi and hhi == hhi else float("nan")


def top_n_concentration(weights: dict[str, float], n: int = 5) -> float:
    """Share of total held in the largest ``n`` exposures."""
    total = sum(weights.values())
    if total <= 0:
        return float("nan")
    ranked = sorted(weights.values(), reverse=True)
    return sum(ranked[:n]) / total


@dataclass
class GroupExposure:
    group: str
    dollars: float
    share: float


def group_exposure(notional_by_underlying: dict[str, float],
                   mapping: dict[str, str],
                   default_group: str = "other") -> list[GroupExposure]:
    """Aggregate underlying exposure into sectors/factors via ``mapping``.

    ``mapping`` is underlying-ticker -> group label (e.g. "mega-cap tech",
    "crypto", "defensive"). Underlyings absent from the map fall into
    ``default_group``. Returned sorted by dollars, descending.
    """
    totals: dict[str, float] = {}
    for ul, amt in notional_by_underlying.items():
        g = mapping.get(ul, default_group)
        totals[g] = totals.get(g, 0.0) + amt
    grand = sum(totals.values())
    out = [
        GroupExposure(g, d, d / grand if grand else float("nan"))
        for g, d in totals.items()
    ]
    out.sort(key=lambda ge: ge.dollars, reverse=True)
    return out
