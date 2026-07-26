"""Historical prices/returns, for the decay model and the market pulse."""

from __future__ import annotations

import json
from pathlib import Path


def closing_prices(ticker: str, period: str = "1y") -> list[float]:
    """Adjusted closing prices (oldest -> newest) for ``ticker``. [] on failure."""
    import yfinance as yf

    try:
        hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    except Exception:
        return []
    if hist is None or hist.empty or "Close" not in hist:
        return []
    return hist["Close"].dropna().tolist()


def price_map(tickers: list[str], period: str = "1y") -> dict[str, list[float]]:
    """Fetch closing-price series for many tickers into a dict."""
    return {tk: closing_prices(tk, period) for tk in tickers}


def save_price_map(pm: dict[str, list[float]], path: str | Path) -> None:
    Path(path).write_text(json.dumps(pm))


def load_price_map(path: str | Path) -> dict[str, list[float]]:
    return json.loads(Path(path).read_text())


def daily_returns(ticker: str, period: str = "1y") -> list[float]:
    """Simple daily returns for ``ticker`` over ``period`` (yfinance history).

    Returns an ordered list of daily simple returns (0.01 == +1%). Empty list
    if the fetch fails or there is no data.
    """
    import yfinance as yf

    try:
        hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    except Exception:
        return []
    if hist is None or hist.empty or "Close" not in hist:
        return []
    closes = hist["Close"].dropna()
    return closes.pct_change().dropna().tolist()
