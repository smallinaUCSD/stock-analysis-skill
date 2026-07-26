"""Assemble the market pulse from a price map (ticker -> list of closes).

Pure given the price map: the CLI fetches prices (free data) and hands them in,
these functions do the arithmetic. A saved price map reproduces the pulse
exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import metrics
from .universe import SECTOR_ETFS, FACTOR_PAIRS, REGIME_TICKERS

PriceMap = dict[str, list[float]]


def _last(prices: PriceMap, ticker: str) -> float | None:
    s = prices.get(ticker)
    return s[-1] if s else None


@dataclass
class SectorRow:
    ticker: str
    name: str
    returns: dict[str, float | None]


def sector_table(prices: PriceMap, sort_window: str = "1m") -> list[SectorRow]:
    rows = []
    for tk, name in SECTOR_ETFS.items():
        s = prices.get(tk, [])
        rets = {w: metrics.trailing_return(s, n) for w, n in metrics.WINDOWS.items()}
        rows.append(SectorRow(tk, name, rets))
    rows.sort(key=lambda r: (r.returns.get(sort_window) is not None,
                             r.returns.get(sort_window) or 0.0), reverse=True)
    return rows


@dataclass
class FactorRow:
    label: str
    num: str
    den: str
    rs: dict[str, float | None]


def factor_table(prices: PriceMap) -> list[FactorRow]:
    rows = []
    for label, num, den in FACTOR_PAIRS:
        a, b = prices.get(num, []), prices.get(den, [])
        rs = {w: metrics.relative_strength(a, b, n) for w, n in metrics.WINDOWS.items()}
        rows.append(FactorRow(label, num, den, rs))
    return rows


@dataclass
class Breadth:
    pct_positive_1m: float | None
    pct_above_50d: float | None
    n_sectors: int


def breadth(prices: PriceMap) -> Breadth:
    series = [prices[tk] for tk in SECTOR_ETFS if prices.get(tk)]
    rets_1m = [metrics.trailing_return(s, metrics.WINDOWS["1m"]) for s in series]
    return Breadth(
        pct_positive_1m=metrics.pct_positive(rets_1m),
        pct_above_50d=metrics.pct_above_ma(series, 50),
        n_sectors=len(series),
    )


@dataclass
class Regime:
    values: dict[str, float | None] = field(default_factory=dict)
    flags: dict[str, bool] = field(default_factory=dict)


def regime(prices: PriceMap) -> Regime:
    """Macro snapshot + simple threshold flags (rule-based, not interpretation)."""
    vix = _last(prices, "^VIX")
    tnx = _last(prices, "^TNX")     # 10Y yield (percent units on Yahoo)
    irx = _last(prices, "^IRX")     # 13-week bill yield (same units)
    curve = (tnx - irx) if (tnx is not None and irx is not None) else None
    n1m = metrics.WINDOWS["1m"]

    values = {
        "vix": vix,
        "10y_yield": tnx,
        "3m_yield": irx,
        "yield_curve_10y_3m": curve,
        "spy_vs_rsp_1m": metrics.relative_strength(
            prices.get("SPY", []), prices.get("RSP", []), n1m),
        "hyg_vs_lqd_1m": metrics.relative_strength(
            prices.get("HYG", []), prices.get("LQD", []), n1m),
        "growth_vs_value_1m": metrics.relative_strength(
            prices.get("VUG", []), prices.get("VTV", []), n1m),
        "gold_1m": metrics.trailing_return(prices.get("GLD", []), n1m),
        "dollar_1m": metrics.trailing_return(prices.get("UUP", []), n1m),
        "spy_1m": metrics.trailing_return(prices.get("SPY", []), n1m),
    }
    flags = {}
    if vix is not None:
        flags["vix_elevated"] = vix > 20.0
        flags["vix_stressed"] = vix > 30.0
    if curve is not None:
        flags["yield_curve_inverted"] = curve < 0.0
    if values["spy_vs_rsp_1m"] is not None:
        flags["narrow_leadership"] = values["spy_vs_rsp_1m"] > 0.0
    if values["hyg_vs_lqd_1m"] is not None:
        flags["credit_risk_off"] = values["hyg_vs_lqd_1m"] < 0.0
    return Regime(values=values, flags=flags)
