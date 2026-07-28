"""ETF / fund look-through: top holdings and sector weights from yfinance.

Used to extend leverage look-through to plain index/sector ETFs (VOO, QQQ, XLK…)
that aren't in the leveraged-product registry. Best-effort — returns None when
the ticker isn't a fund or the data isn't available.
"""

from __future__ import annotations


def etf_holdings(ticker: str, limit: int = 15) -> dict | None:
    import yfinance as yf

    try:
        tk = yf.Ticker(ticker)
        fd = tk.funds_data
        th = fd.top_holdings          # DataFrame indexed by symbol
    except Exception:  # noqa: BLE001
        return None
    if th is None or getattr(th, "empty", True):
        return None

    holdings = []
    for sym, row in th.iterrows():
        try:
            w = float(row.get("Holding Percent"))
        except Exception:  # noqa: BLE001
            w = None
        if not w:
            continue
        holdings.append({"underlying": str(sym), "name": str(row.get("Name", "")), "weight": w})
        if len(holdings) >= limit:
            break
    if not holdings:
        return None

    sectors = None
    try:
        sw = fd.sector_weightings
        if isinstance(sw, dict) and sw:
            sectors = {k: float(v) for k, v in sw.items()}
    except Exception:  # noqa: BLE001
        sectors = None

    name = ""
    try:
        name = (tk.info or {}).get("longName") or ""
    except Exception:  # noqa: BLE001
        name = ""

    return {"name": name, "holdings": holdings, "sectors": sectors}
