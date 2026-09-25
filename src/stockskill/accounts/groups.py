"""The sector / index groups a new user picks from; their union becomes the
starting watchlist.

Indices are complete: the Magnificent 7, the Dow Jones 30 and the Nasdaq-100
(fetched from Nasdaq daily, with a saved copy as fallback). Sectors come from
the board's own sections in data/tickers.csv, plus a few curated groups for
fund and income investors.
"""

from __future__ import annotations

import json
import os
import time

# Dow Jones Industrial Average members (last change Nov 2024: NVDA, SHW in).
DOW30 = ["AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "GS", "HD", "HON",
         "IBM", "JNJ", "JPM", "KO", "MCD", "MMM", "MRK", "MSFT", "NKE", "NVDA", "PG", "SHW", "TRV",
         "UNH", "V", "VZ", "WMT"]

# Nasdaq-100 as of 2026-09-25; the live list replaces it when reachable.
NASDAQ100_SAVED = [
    "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "ALAB", "ALNY", "AMAT", "AMD", "AMGN", "AMZN", "APP",
    "ARM", "ASML", "AVGO", "AXON", "BKNG", "BKR", "CCEP", "CDNS", "CEG", "CMCSA", "COST", "CPRT", "CRWD",
    "CRWV", "CSCO", "CSX", "CTAS", "DASH", "DDOG", "DXCM", "EXC", "FANG", "FAST", "FER", "FTNT", "GEHC",
    "GILD", "GOOG", "GOOGL", "HON", "HONA", "IDXX", "INTC", "INTU", "ISRG", "KDP", "KLAC", "LIN", "LITE",
    "LRCX", "MAR", "MCHP", "MDLZ", "MELI", "META", "MNST", "MPWR", "MRVL", "MSFT", "MSTR", "MU", "NBIS",
    "NFLX", "NVDA", "NXPI", "ODFL", "ORLY", "PANW", "PAYX", "PCAR", "PDD", "PEP", "PLTR", "PYPL", "QCOM",
    "REGN", "RKLB", "ROP", "ROST", "SBUX", "SHOP", "SNDK", "SNPS", "SPCX", "STX", "TER", "TMUS", "TRI",
    "TSLA", "TTWO", "TXN", "VRTX", "WBD", "WDAY", "WDC", "WMT", "XEL"]

ETFS = ["SPY", "VOO", "VTI", "QQQ", "DIA", "IWM", "SCHD", "XLK", "SMH", "XLF", "XLE", "XLV"]
SOFTWARE = ["ORCL", "CRM", "ADBE", "INTU", "NFLX", "SHOP", "WDAY", "SNOW", "DDOG", "PLTR", "NET",
            "ADSK", "MELI", "ABNB", "BKNG", "DASH", "APP"]
DIVIDEND = ["KO", "PEP", "PG", "JNJ", "MCD", "WMT", "HD", "VZ", "XOM", "CVX", "JPM", "MRK", "IBM", "SCHD"]

# (key, label, kind, blurb, source): source is a tickers.csv section name or a list
_DEFS = [
    ("mag7", "Magnificent 7", "index", "Apple, Microsoft, Alphabet, Amazon, Nvidia, Meta, Tesla", "M7"),
    ("dow30", "Dow Jones 30", "index", "The 30 blue chips of the Dow Jones Industrial Average", DOW30),
    ("nasdaq100", "Nasdaq-100", "index", "The 100 largest non-financial Nasdaq companies", "NASDAQ100*"),
    ("etfs", "Index & sector ETFs", "funds", "S&P 500, total market, Nasdaq, Dow, small caps, sector funds", ETFS),
    ("dividend", "Dividend & defensive", "theme", "Steady payers: staples, healthcare, energy, telecom", DIVIDEND),
    ("semis", "Semiconductors", "sector", "Chip designers, equipment makers, memory", "SEMIS"),
    ("ai", "AI & data centers", "sector", "Power, networking, cooling and AI software", "AI-DATACENTER"),
    ("software", "Software & internet", "sector", "Cloud, SaaS, marketplaces and streaming", SOFTWARE),
    ("cyber", "Cybersecurity", "sector", "Network, endpoint and identity security", "CYBERSECURITY"),
    ("financials", "Banks & payments", "sector", "Money-center banks, card networks, brokers", "FINANCIALS"),
    ("healthcare", "Healthcare", "sector", "Pharma, insurers, med-tech", "HEALTHCARE"),
    ("energy", "Energy", "sector", "Oil and gas producers", "ENERGY"),
    ("consumer", "Consumer & retail", "sector", "Retailers, restaurants, household brands", "CONSUMER"),
    ("industrials", "Industrials", "sector", "Machinery, materials, autonomy", "INDUSTRIALS"),
    ("space", "Space", "sector", "Launch, satellites, lunar", "SPACE"),
    ("crypto", "Crypto", "sector", "Bitcoin funds and crypto companies", "CRYPTO"),
    ("intl", "International", "sector", "Large non-US companies", "INTL"),
    ("leveraged", "Leveraged ETFs", "funds", "2x and 3x daily funds (high risk, decay over time)", "LEVERAGED"),
    ("inverse", "Inverse ETFs", "funds", "Funds that rise when a stock or index falls", "LEVERAGED-BEAR"),
]
_CACHE: dict = {"t": 0.0, "groups": None}


def _nasdaq100(cache_dir: str | None) -> list[str]:
    path = os.path.join(cache_dir or ".cache", "_groups", "nasdaq100.json")
    try:
        if time.time() - os.path.getmtime(path) < 86400:
            return json.load(open(path))
    except OSError:
        pass
    try:
        import requests
        r = requests.get("https://api.nasdaq.com/api/quote/list-type/nasdaq100", timeout=15,
                         headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                                                "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                                  "Accept": "application/json"})
        rows = r.json()["data"]["data"]["rows"]
        syms = sorted({x["symbol"].strip().upper().replace("/", "-") for x in rows if x.get("symbol")})
        if len(syms) >= 90:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            json.dump(syms, open(path, "w"))
            return syms
    except Exception:  # noqa: BLE001
        pass
    try:
        return json.load(open(path))
    except Exception:  # noqa: BLE001
        return list(NASDAQ100_SAVED)


def groups(tickers_path: str = "data/tickers.csv", cache_dir: str | None = None) -> list[dict]:
    """[{key, label, kind, blurb, tickers}] - cached for an hour."""
    if _CACHE["groups"] is not None and time.time() - _CACHE["t"] < 3600:
        return _CACHE["groups"]
    try:
        from ..watchlist.tickers import parse_tickers
        sections = parse_tickers(tickers_path)["sections"]
    except Exception:  # noqa: BLE001
        sections = {}
    out = []
    for key, label, kind, blurb, src in _DEFS:
        if src == "NASDAQ100*":
            tks = _nasdaq100(cache_dir)
        elif isinstance(src, str):
            tks = list(sections.get(src) or [])
        else:
            tks = list(src)
        if tks:
            out.append({"key": key, "label": label, "kind": kind, "blurb": blurb, "tickers": tks})
    _CACHE.update(t=time.time(), groups=out)
    return out


def tickers_for(keys, tickers_path: str = "data/tickers.csv", cache_dir: str | None = None) -> list[str]:
    """Union of the chosen groups, in the order the groups are listed."""
    want = set(keys or [])
    seen, out = set(), []
    for g in groups(tickers_path, cache_dir):
        if g["key"] in want:
            for t in g["tickers"]:
                if t not in seen:
                    seen.add(t)
                    out.append(t)
    return out

