"""Market-wide screener universe: every US-listed common stock with price,
size and sector (Nasdaq's public screener feed, one call) joined to annual
fundamentals for every SEC filer (XBRL "frames", one call per line item).

Fundamentals are for the fiscal year closest to the last calendar year (the
SEC maps each company's year onto calendar years); growth compares it with the
year before. ``build_rows`` is pure (tested); ``universe`` fetches and caches.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import date

_NASDAQ = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true"
_UA_BROWSER = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
               "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")

FLOW = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                "RevenuesNetOfInterestExpense", "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "gross_profit": ["GrossProfit"],
    "op_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
}
INSTANT = {
    "equity": ["StockholdersEquity"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
}
_UNIT = {"eps": "USD-per-shares"}
_BAD_NAME = re.compile(r"\b(warrants?|rights?|units?|preferred|depositary shares? representing|notes? due)\b", re.I)


def _num(s) -> float | None:
    if s in (None, "", "NA"):
        return None
    try:
        return float(str(s).replace("$", "").replace(",", "").replace("%", ""))
    except ValueError:
        return None


def parse_listings(j: dict) -> list[dict]:
    """Nasdaq screener JSON -> [{ticker, name, price, mcap, chg, volume, sector,
    industry, country}] for common stocks (no warrants, units, preferreds)."""
    out = []
    for r in ((j or {}).get("data") or {}).get("rows") or []:
        sym = (r.get("symbol") or "").strip().upper()
        name = (r.get("name") or "").strip()
        if not re.fullmatch(r"[A-Z]{1,5}(/[A-Z])?", sym) or _BAD_NAME.search(name):
            continue
        sym = sym.replace("/", "-")                     # share classes: BRK/B -> BRK-B
        price = _num(r.get("lastsale"))
        if not price:
            continue
        name = re.sub(r"\s+(Class [A-C] )?(Common Stock|Ordinary Shares|Common Shares|American Depositary Shares).*$",
                      "", name, flags=re.I).strip()
        chg = _num(r.get("pctchange"))
        out.append({"ticker": sym, "name": name, "price": price, "mcap": _num(r.get("marketCap")) or None,
                    "chg": chg / 100 if chg is not None else None, "volume": _num(r.get("volume")),
                    "sector": r.get("sector") or None, "industry": r.get("industry") or None,
                    "country": r.get("country") or None})
    return out


def merge_frames(frames: dict[str, list[dict]], keys: dict[str, list[str]]) -> dict[int, dict]:
    """{concept: frame rows} -> {cik: {key: val, key_end: period end}}, the
    first concept in each key's list winning."""
    out: dict[int, dict] = {}
    for key, concepts in keys.items():
        for concept in concepts:
            for r in frames.get(concept) or []:
                row = out.setdefault(r["cik"], {})
                if key not in row:
                    row[key] = float(r["val"])
                    row.setdefault("_end", r.get("end"))
    return out


def _div(a, b):
    return a / b if a is not None and b not in (None, 0) else None


def _growth(a, b):
    return a / b - 1 if a is not None and b is not None and b > 0 else None


def build_rows(listings: list[dict], cur: dict[int, dict], prev: dict[int, dict],
               cik_of: dict[str, int]) -> list[dict]:
    """One row per listing with valuation, profitability and growth metrics."""
    rows = []
    for L in listings:
        cik = cik_of.get(L["ticker"])
        f = (cur.get(cik) if cik else None) or {}
        p = (prev.get(cik) if cik else None) or {}
        mc, px = L.get("mcap"), L.get("price")
        rev, ni, ocf, capex = f.get("revenue"), f.get("net_income"), f.get("ocf"), f.get("capex")
        fcf = ocf - capex if ocf is not None and capex is not None else None
        eps = f.get("eps")
        eq = f.get("equity")
        pe = px / eps if eps and eps > 0 else (_div(mc, ni) if ni and ni > 0 else None)
        ev = mc + (f.get("long_term_debt") or 0) - (f.get("cash") or 0) if mc and f else None
        rows.append({
            **L,
            "fy_end": f.get("_end"),
            "revenue": rev, "net_income": ni, "fcf": fcf,
            "pe": pe if pe is None or pe < 2000 else None,
            "ps": _div(mc, rev) if rev and rev > 0 else None,
            "pb": _div(mc, eq) if eq and eq > 0 else None,
            "pfcf": _div(mc, fcf) if fcf and fcf > 0 else None,
            "fcf_yield": _div(fcf, mc),
            "ev_sales": _div(ev, rev) if ev and rev and rev > 0 else None,
            "gross_margin": _div(f.get("gross_profit"), rev) if rev and rev > 0 else None,
            "op_margin": _div(f.get("op_income"), rev) if rev and rev > 0 else None,
            "net_margin": _div(ni, rev) if rev and rev > 0 else None,
            "rev_growth": _growth(rev, p.get("revenue")),
            "ni_growth": _growth(ni, p.get("net_income")),
            "roe": _div(ni, eq) if eq and eq > 0 else None,
            "debt_equity": _div(f.get("long_term_debt") or 0, eq) if eq and eq > 0 else None,
        })
    return rows


# --- fetching + caching ----------------------------------------------------

_STATE = {"running": False, "error": None, "rows": None, "built": 0.0, "year": None}
_LOCK = threading.Lock()
_TTL_UNIVERSE = 12 * 3600
_TTL_FRAME = 7 * 86400


def _frame(concept: str, period: str, unit: str, cache_dir) -> list[dict]:
    from . import sec as SEC
    path = os.path.join(SEC._cache_dir(cache_dir), f"frame_{concept}_{unit}_{period}.json")
    j = SEC._cached(path, _TTL_FRAME,
                    lambda: SEC._get_json(f"{SEC._BASE_DATA}/api/xbrl/frames/us-gaap/{concept}/{unit}/{period}.json"))
    return (j or {}).get("data") or []


def _fundamentals(year: int, cache_dir) -> dict[int, dict]:
    frames = {}
    for key, concepts in FLOW.items():
        for c in concepts:
            frames[c] = _frame(c, f"CY{year}", _UNIT.get(key, "USD"), cache_dir)
    out = merge_frames(frames, FLOW)
    inst = {c: _frame(c, f"CY{year}Q4I", "USD", cache_dir) for cs in INSTANT.values() for c in cs}
    for cik, vals in merge_frames(inst, INSTANT).items():
        vals.pop("_end", None)
        out.setdefault(cik, {}).update(vals)
    return out


def _listings(cache_dir) -> list[dict]:
    from . import sec as SEC
    path = os.path.join(SEC._cache_dir(cache_dir), "nasdaq_listings.json")

    def fetch():
        try:
            import requests
            r = requests.get(_NASDAQ, headers={"User-Agent": _UA_BROWSER, "Accept": "application/json"}, timeout=30)
            return r.json() if r.status_code == 200 else None
        except Exception:  # noqa: BLE001
            return None

    return parse_listings(SEC._cached(path, 6 * 3600, fetch) or {})


def _build(cache_dir, watch: dict) -> None:
    from . import sec as SEC
    try:
        listings = _listings(cache_dir)
        if not listings:
            raise RuntimeError("the market listing feed is unavailable")
        SEC.cik_for("AAPL", cache_dir)                      # load the ticker -> CIK map
        cik_of = dict(SEC._CIK_MEMO["map"])
        year = date.today().year - 1
        cur, prev = _fundamentals(year, cache_dir), _fundamentals(year - 1, cache_dir)
        if len(cur) < 1000:                                  # early in the year: last year isn't filed yet
            year -= 1
            cur, prev = prev, _fundamentals(year - 1, cache_dir)
        rows = build_rows(listings, cur, prev, cik_of)
        for r in rows:
            w = watch.get(r["ticker"])
            r["watch"] = bool(w is not None)
            if w:
                r.update(w)
        with _LOCK:
            _STATE.update(rows=rows, built=time.time(), error=None, year=year)
    except Exception as e:  # noqa: BLE001
        with _LOCK:
            _STATE["error"] = str(e)
    finally:
        with _LOCK:
            _STATE["running"] = False


def universe(cache_dir, watch_fn) -> dict:
    """{rows, year, built} when ready; otherwise starts a background build and
    returns {warming: True}. ``watch_fn()`` -> {ticker: extra fields} for the
    watchlist (momentum from cached prices)."""
    with _LOCK:
        fresh = _STATE["rows"] is not None and time.time() - _STATE["built"] < _TTL_UNIVERSE
        if fresh:
            return {"rows": _STATE["rows"], "year": _STATE["year"], "built": _STATE["built"]}
        if not _STATE["running"]:
            _STATE["running"] = True
            threading.Thread(target=_build, args=(cache_dir, watch_fn()), daemon=True).start()
        stale = _STATE["rows"]
        err = _STATE["error"]
    if stale is not None:                                     # serve the old table while refreshing
        return {"rows": stale, "year": _STATE["year"], "built": _STATE["built"], "refreshing": True}
    return {"warming": True, "error": err}


def compact(rows: list[dict]) -> dict:
    """Column-oriented JSON (much smaller than a list of dicts)."""
    cols = ["ticker", "name", "sector", "industry", "country", "price", "mcap", "chg", "volume",
            "pe", "ps", "pb", "pfcf", "fcf_yield", "ev_sales", "gross_margin", "op_margin", "net_margin",
            "rev_growth", "ni_growth", "roe", "debt_equity", "revenue", "net_income", "fcf", "fy_end",
            "watch", "r1m", "r3m", "r1y"]

    def rnd(v):
        return round(v, 4) if isinstance(v, float) else v
    return {"cols": cols, "data": [[rnd(r.get(c)) for c in cols] for r in rows]}


def _json_default(o):
    return str(o)


def dumps(obj) -> str:
    return json.dumps(obj, default=_json_default, separators=(",", ":"))
