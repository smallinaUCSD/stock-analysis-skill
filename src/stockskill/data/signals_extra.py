"""Fetchers for the extra analysis-page signals: insider trades (Finnhub, SEC
Form 4), short interest (Yahoo) and two years of annual statements (FMP when it
has quota, else Yahoo). Best-effort: every function returns None/[] on failure.
"""

from __future__ import annotations

from datetime import date, timedelta

# yfinance statement row -> our key (first match wins)
_YF_ROWS = {
    "net_income": ["Net Income", "Net Income Common Stockholders"],
    "revenue": ["Total Revenue", "Operating Revenue"],
    "gross_profit": ["Gross Profit"],
    "total_assets": ["Total Assets"],
    "long_term_debt": ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
    "current_assets": ["Current Assets"],
    "current_liabilities": ["Current Liabilities"],
    "shares": ["Ordinary Shares Number", "Share Issued"],
    "cfo": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
}
# FMP stable field -> our key
_FMP_FIELDS = {
    "net_income": "netIncome", "revenue": "revenue", "gross_profit": "grossProfit",
    "total_assets": "totalAssets", "long_term_debt": "longTermDebt",
    "current_assets": "totalCurrentAssets", "current_liabilities": "totalCurrentLiabilities",
    "shares": "weightedAverageShsOut", "cfo": "operatingCashFlow",
}


def insider_trades(ticker: str, years: int = 4) -> list[dict] | None:
    """[{name, date, code, shares, price}] of Form 4 transactions (Finnhub)."""
    from . import finnhub
    if not finnhub.has_finnhub():
        return None
    j = finnhub._get("/stock/insider-transactions", symbol=ticker,
                     **{"from": str(date.today() - timedelta(days=365 * years + 30))})
    rows = (j or {}).get("data") if isinstance(j, dict) else None
    if rows is None:
        return None
    out = []
    for r in rows:
        if r.get("isDerivative"):
            continue
        out.append({"name": r.get("name") or "", "date": r.get("transactionDate") or r.get("filingDate") or "",
                    "code": (r.get("transactionCode") or "").upper(),
                    "shares": r.get("change") or 0, "price": r.get("transactionPrice") or 0})
    return out


def short_interest(ticker: str) -> dict | None:
    """{pct_float, days_to_cover, shares_short, change_vs_prior, as_of} (Yahoo)."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
    except Exception:  # noqa: BLE001
        return None
    ss, prior = info.get("sharesShort"), info.get("sharesShortPriorMonth")
    if ss is None and info.get("shortPercentOfFloat") is None:
        return None
    ts = info.get("dateShortInterest")
    as_of = date.fromtimestamp(ts).isoformat() if isinstance(ts, (int, float)) else None
    return {"pct_float": info.get("shortPercentOfFloat"), "days_to_cover": info.get("shortRatio"),
            "shares_short": ss, "as_of": as_of,
            "change_vs_prior": (ss / prior - 1.0) if (ss and prior) else None}


def annual_statements(ticker: str) -> tuple[dict, dict] | None:
    """(latest fiscal year, prior fiscal year) as dicts of _YF_ROWS keys."""
    from . import fmp
    if fmp.has_fmp() and not fmp.quota_exhausted():
        try:
            parts = [fmp._get(p, symbol=ticker, limit=2) for p in
                     ("/income-statement", "/balance-sheet-statement", "/cash-flow-statement")]
            if all(isinstance(p, list) and len(p) >= 2 for p in parts):
                years = []
                for i in range(2):
                    merged = {**parts[0][i], **parts[1][i], **parts[2][i]}
                    years.append({k: merged.get(f) for k, f in _FMP_FIELDS.items()})
                return years[0], years[1]
        except Exception:  # noqa: BLE001
            pass
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        frames = [t.financials, t.balance_sheet, t.cashflow]
    except Exception:  # noqa: BLE001
        return None
    years = [{}, {}]
    for key, labels in _YF_ROWS.items():
        for fr in frames:
            if fr is None or getattr(fr, "empty", True) or fr.shape[1] < 2:
                continue
            hit = next((lbl for lbl in labels if lbl in fr.index), None)
            if hit is None:
                continue
            for i in range(2):
                v = fr.loc[hit].iloc[i]
                years[i][key] = None if v != v else float(v)       # NaN -> None
            break
    if not any(v is not None for v in years[0].values()):
        return None
    return years[0], years[1]
