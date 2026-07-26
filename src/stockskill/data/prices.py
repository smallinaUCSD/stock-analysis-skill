"""Historical daily returns, for replaying real paths through the decay model."""

from __future__ import annotations


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
