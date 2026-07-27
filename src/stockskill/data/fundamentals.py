"""Fetch the numeric inputs valuation needs, and cache them for reproducibility.

Design contract: this module *only* moves numbers around -- it fetches raw
fundamentals from a free source (yfinance / Yahoo) and stores them verbatim in
a :class:`FundamentalSnapshot`. The valuation math lives elsewhere and operates
on these numbers. A snapshot can be saved to and loaded from JSON, so a
valuation is fully reproducible: same snapshot in -> same fair value out,
no network and no model judgement involved.

If the network or a field is unavailable, the corresponding attribute is None
and the valuation engine simply skips the methods it can't support.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path


@dataclass
class FundamentalSnapshot:
    ticker: str
    as_of: str
    source: str = "yfinance"
    price: float | None = None
    shares: float | None = None
    market_cap: float | None = None
    fcf: float | None = None            # free cash flow to firm (annual)
    net_debt: float | None = None       # total debt - cash & short-term inv
    eps: float | None = None            # trailing EPS
    ebitda: float | None = None
    revenue: float | None = None
    dividend_annual: float | None = None
    beta: float | None = None
    currency: str | None = None
    # growth & quality (decimals; e.g. 0.12 == 12%)
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    profit_margin: float | None = None
    roe: float | None = None
    # reported third-party analyst consensus (NOT our view -- displayed as-is)
    analyst_reco: str | None = None          # e.g. "buy", "hold"
    analyst_mean: float | None = None        # 1=strong buy .. 5=strong sell
    analyst_count: int | None = None
    target_mean: float | None = None
    name: str | None = None
    sector: str | None = None
    quote_type: str | None = None       # EQUITY | ETF | ...
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    avg_volume: float | None = None
    next_earnings: str | None = None     # ISO date if known
    # extended-hours (pre/post-market) — populated when the session is active
    market_state: str | None = None      # REGULAR | PRE | POST | CLOSED | PREPRE | POSTPOST
    ext_price: float | None = None       # pre- or post-market last price
    ext_change: float | None = None      # extended-hours change (decimal)

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def from_json(cls, path: str | Path) -> "FundamentalSnapshot":
        return cls(**json.loads(Path(path).read_text()))


def _first(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def fetch_snapshot(ticker: str) -> FundamentalSnapshot:
    """Pull a fundamentals snapshot from yfinance. Missing fields stay None."""
    import yfinance as yf

    t = yf.Ticker(ticker)
    info: dict = {}
    try:
        info = t.info or {}
    except Exception:
        info = {}

    price = None
    shares = None
    try:
        fi = t.fast_info
        price = _first(getattr(fi, "last_price", None), info.get("currentPrice"))
        shares = _first(getattr(fi, "shares", None), info.get("sharesOutstanding"))
    except Exception:
        price = info.get("currentPrice")
        shares = info.get("sharesOutstanding")

    total_debt = info.get("totalDebt")
    cash = _first(info.get("totalCash"), info.get("cash"))
    net_debt = None
    if total_debt is not None and cash is not None:
        net_debt = total_debt - cash

    fcf = info.get("freeCashflow")
    if fcf is None:
        ocf = info.get("operatingCashflow")
        capex = info.get("capitalExpenditures")
        if ocf is not None and capex is not None:
            fcf = ocf + capex  # capex is reported negative
    if fcf is None:
        # Fall back to the annual cash-flow statement.
        try:
            cf = t.cashflow
            if cf is not None and not cf.empty:
                col = cf.columns[0]
                if "Free Cash Flow" in cf.index:
                    fcf = float(cf.loc["Free Cash Flow", col])
                elif "Operating Cash Flow" in cf.index and "Capital Expenditure" in cf.index:
                    fcf = float(cf.loc["Operating Cash Flow", col]) + float(cf.loc["Capital Expenditure", col])
        except Exception:
            pass

    dividend = _first(info.get("dividendRate"), info.get("trailingAnnualDividendRate"))

    # Extended-hours (pre/post-market). yfinance exposes these on `info`.
    market_state = info.get("marketState")
    ext_price = ext_change = None
    if market_state in ("PRE", "PREPRE"):
        ext_price = info.get("preMarketPrice")
        pmc = info.get("preMarketChangePercent")
        ext_change = (pmc / 100.0) if pmc is not None else None
    elif market_state in ("POST", "POSTPOST", "CLOSED"):
        ext_price = info.get("postMarketPrice")
        pmc = info.get("postMarketChangePercent")
        ext_change = (pmc / 100.0) if pmc is not None else None
    # some payloads give the change fraction already; guard against absurd values
    if ext_change is not None and abs(ext_change) > 2:
        ext_change = ext_change / 100.0

    # Next earnings date (upcoming only). yfinance gives unix timestamps in info;
    # keep it only if it's today or later (else it's the last report).
    next_earnings = None
    ets = _first(info.get("earningsTimestampStart"), info.get("earningsTimestamp"))
    if ets:
        try:
            from datetime import datetime, timezone
            ed = datetime.fromtimestamp(ets, tz=timezone.utc).date()
            if ed >= date.today():
                next_earnings = ed.isoformat()
        except Exception:
            next_earnings = None

    return FundamentalSnapshot(
        ticker=ticker.upper(),
        as_of=date.today().isoformat(),
        source="yfinance",
        price=price,
        shares=shares,
        market_cap=info.get("marketCap"),
        fcf=fcf,
        net_debt=net_debt,
        eps=info.get("trailingEps"),
        ebitda=info.get("ebitda"),
        revenue=info.get("totalRevenue"),
        dividend_annual=dividend,
        beta=info.get("beta"),
        currency=info.get("currency"),
        revenue_growth=info.get("revenueGrowth"),
        earnings_growth=info.get("earningsGrowth"),
        profit_margin=info.get("profitMargins"),
        roe=info.get("returnOnEquity"),
        analyst_reco=info.get("recommendationKey"),
        analyst_mean=info.get("recommendationMean"),
        analyst_count=info.get("numberOfAnalystOpinions"),
        target_mean=info.get("targetMeanPrice"),
        name=info.get("longName") or info.get("shortName"),
        sector=info.get("sector"),
        quote_type=info.get("quoteType"),
        fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
        fifty_two_week_low=info.get("fiftyTwoWeekLow"),
        avg_volume=info.get("averageVolume"),
        next_earnings=next_earnings,
        market_state=market_state,
        ext_price=ext_price,
        ext_change=ext_change,
    )
