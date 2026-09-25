"""SEC EDGAR: annual financial statements (XBRL company facts) and industry codes.

Free and official. The SEC requires every request to identify its sender, so
this reads ``SEC_USER_AGENT`` ("Name email") from the environment; without it
every function returns None and callers fall back to the other providers.
Requests are kept under the SEC's 10-per-second limit, and results are cached
on disk (the filings change a few times a year).

Only US-GAAP filers reporting in USD are parsed (IFRS/foreign filers return
None). For each fiscal year the latest-filed value is used (restatements win),
and ``filed`` records when that year's figures were FIRST public, which is what
a point-in-time backtest needs.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import date

_BASE_DATA = "https://data.sec.gov"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_TTL_TICKERS = 7 * 86400
_TTL_FACTS = 86400
_TTL_SUBMISSIONS = 30 * 86400

# our key -> us-gaap concepts to try, first match per fiscal year wins
_FLOW = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "RevenuesNetOfInterestExpense"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
              "PaymentsForCapitalImprovements"],
    "da": ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
           "DepreciationAndAmortization", "DepreciationAmortizationAndImpairment", "Depreciation"],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "net_income": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "op_income": ["OperatingIncomeLoss"],
    "gross_profit": ["GrossProfit"],
    "shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}
_INSTANT = {
    "total_assets": ["Assets"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations",
                       "LongTermDebtAndFinanceLeasesNoncurrent", "DebtAndCapitalLeaseObligations",
                       "LongTermDebtAndCapitalLeaseObligationsNoncurrent"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "equity": ["StockholdersEquity"],
}
_ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT"}


def _ua() -> str | None:
    ua = (os.environ.get("SEC_USER_AGENT") or "").strip().strip('"')
    return ua or None


def has_sec() -> bool:
    return bool(_ua())


class _Limiter:
    def __init__(self, per_sec: float = 8.0):
        self.gap = 1.0 / per_sec
        self.last = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            d = self.last + self.gap - time.monotonic()
            if d > 0:
                time.sleep(d)
            self.last = time.monotonic()


_LIMIT = _Limiter()


def _get_json(url: str):
    ua = _ua()
    if not ua:
        return None
    try:
        import requests
        _LIMIT.wait()
        r = requests.get(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, timeout=20)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:  # noqa: BLE001
        return None


def _cache_dir(cache_dir: str | None) -> str:
    d = os.path.join(cache_dir or ".cache", "_sec")
    os.makedirs(d, exist_ok=True)
    return d


def _cached(path: str, ttl: float, fetch):
    """Read ``path`` if younger than ``ttl``; else fetch, store, return. On a
    failed fetch, an older copy is better than nothing."""
    try:
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl:
            with open(path) as f:
                return json.load(f)
    except Exception:  # noqa: BLE001
        pass
    data = fetch()
    if data is not None:
        try:
            tmp = f"{path}.{os.getpid()}.tmp"
            with open(tmp, "w") as f:
                json.dump(data, f)
            os.replace(tmp, path)
        except Exception:  # noqa: BLE001
            pass
        return data
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:  # noqa: BLE001
        pass
    return None


_CIK_MEMO: dict = {"path": None, "mtime": None, "map": {}}


def cik_for(ticker: str, cache_dir: str | None = None, offline: bool = False) -> int | None:
    path = os.path.join(_cache_dir(cache_dir), "company_tickers.json")
    if not offline:
        _cached(path, _TTL_TICKERS, lambda: _get_json(_TICKERS_URL))
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    if _CIK_MEMO["path"] != path or _CIK_MEMO["mtime"] != mtime:
        data = _read(path) or {}
        m: dict = {}
        # the file is ordered largest company first; a ticker can appear more
        # than once (e.g. a new holding company) - keep the first (main) one
        for k in sorted(data, key=lambda x: int(x) if str(x).isdigit() else 0):
            v = data[k]
            m.setdefault(v.get("ticker", "").upper(), int(v["cik_str"]))
        _CIK_MEMO.update(path=path, mtime=mtime, map=m)
    return _CIK_MEMO["map"].get(ticker.upper().replace(".", "-"))


def _read(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return None


def _duration_days(f) -> int | None:
    try:
        s, e = date.fromisoformat(f["start"]), date.fromisoformat(f["end"])
        return (e - s).days
    except Exception:  # noqa: BLE001
        return None


def extract_annual(facts: dict, flow: dict | None = None, instant: dict | None = None,
                   units: dict | None = None, fallback: bool = False,
                   keep_filed: bool = False) -> list[dict]:
    """Annual rows [{end, filed, fy, <keys>...}] oldest -> newest from a
    company-facts JSON. Pure (unit-tested with fixtures).

    ``flow``/``instant`` override the concept maps; ``units`` gives a non-USD
    unit per key (e.g. EPS in "USD/shares"). With ``fallback`` a balance-sheet
    key takes a later concept for years the first one leaves empty.
    ``keep_filed`` keeps ``_f_<key>``: the filing date each value came from."""
    flow = _FLOW if flow is None else flow
    instant = _INSTANT if instant is None else instant
    units = {"shares": "shares", **(units or {})}
    gaap = ((facts or {}).get("facts") or {}).get("us-gaap") or {}
    if not gaap:
        return []

    def facts_for(concept, unit):
        c = gaap.get(concept) or {}
        return (c.get("units") or {}).get(unit) or []

    years: dict[str, dict] = {}

    def put(end, key, val, filed, fy, latest_filed):
        row = years.setdefault(end, {"end": end, "filed": filed, "fy": fy})
        row["filed"] = min(row["filed"], filed) if row.get("filed") else filed
        prev = row.get("_f_" + key)
        if prev is None or latest_filed > prev:
            row[key] = val
            row["_f_" + key] = latest_filed

    # flows: a ~1-year duration reported in an annual report
    for key, concepts in flow.items():
        unit = units.get(key, "USD")
        taken: set[str] = set()
        for concept in concepts:
            for f in facts_for(concept, unit):
                if f.get("form") not in _ANNUAL_FORMS:
                    continue
                dd = _duration_days(f)
                if dd is None or not 350 <= dd <= 380:
                    continue
                end = f["end"]
                if end in taken:
                    continue           # an earlier (preferred) concept already covers this year
                put(end, key, float(f["val"]), f.get("filed", ""), f.get("fy"), f.get("filed", ""))
            taken |= {e for e, r in years.items() if key in r}
    ends = set(years)
    # balance sheet: the value at each fiscal year end
    for key, concepts in instant.items():
        for concept in concepts:
            hit = False
            for f in facts_for(concept, units.get(key, "USD")):
                if f.get("form") not in _ANNUAL_FORMS or "start" in f or f.get("end") not in ends:
                    continue
                if key in years[f["end"]] and years[f["end"]].get("_c_" + key) != concept:
                    continue
                years[f["end"]]["_c_" + key] = concept
                put(f["end"], key, float(f["val"]), f.get("filed", ""), f.get("fy"), f.get("filed", ""))
                hit = True
            if hit and not fallback:
                break
    out = []
    for end in sorted(years):
        r = {k: v for k, v in years[end].items()
             if not k.startswith("_") or (keep_filed and k.startswith("_f_"))}
        anchors = [k for k in ("revenue", "ocf") if k in flow] or list(flow)
        if any(r.get(k) is not None for k in anchors):
            out.append(r)
    return out


def annual_history(ticker: str, cache_dir: str | None = None, offline: bool = False) -> dict | None:
    """{cik, name, sic, sic_desc, years: [...]} for ``ticker`` from EDGAR.

    ``offline=True`` reads only what's already cached (for network-free builds)."""
    cik = cik_for(ticker, cache_dir, offline=offline)
    if not cik:
        return None
    d = _cache_dir(cache_dir)
    hist_path = os.path.join(d, f"hist_{cik}.json")
    sub_path = os.path.join(d, f"sub_{cik}.json")

    def fetch_hist():
        facts = _get_json(f"{_BASE_DATA}/api/xbrl/companyfacts/CIK{cik:010d}.json")
        if not facts:
            return None
        return {"cik": cik, "name": facts.get("entityName"), "years": extract_annual(facts)}

    def fetch_sub():
        s = _get_json(f"{_BASE_DATA}/submissions/CIK{cik:010d}.json")
        if not s:
            return None
        return {"sic": s.get("sic"), "sic_desc": s.get("sicDescription"), "name": s.get("name")}

    if offline:
        hist, sub = _read(hist_path), _read(sub_path)
    else:
        hist = _cached(hist_path, _TTL_FACTS, fetch_hist)
        sub = _cached(sub_path, _TTL_SUBMISSIONS, fetch_sub)
    if not hist:
        return None
    return {**hist, "sic": (sub or {}).get("sic"), "sic_desc": (sub or {}).get("sic_desc")}


def prefetch(tickers: list[str], cache_dir: str | None = None) -> int:
    """Warm the cache for many tickers (used by the nightly refresh). Returns
    how many have SEC history."""
    return sum(1 for t in tickers if annual_history(t, cache_dir))


def yahoo_revenue_history(ticker: str, cache_dir: str | None = None,
                          offline: bool = False) -> dict | None:
    """Fallback for companies without usable SEC data (foreign filers, new
    registrants): annual revenue from Yahoo's financial statements, in the
    same row shape, so the multi-year growth rate can still be computed.
    Revenue only: Yahoo reports foreign filers in their home currency, which
    is fine for a growth ratio but not for cash-flow levels."""
    path = os.path.join(_cache_dir(cache_dir), f"yrev_{ticker.upper()}.json")

    def fetch():
        try:
            import yfinance as yf
            fin = yf.Ticker(ticker).financials
            if fin is None or fin.empty or "Total Revenue" not in fin.index:
                return None
            rows = []
            for col in fin.columns:
                v = fin.loc["Total Revenue", col]
                if v == v:                                     # skip NaN
                    rows.append({"end": col.date().isoformat(), "filed": None, "revenue": float(v)})
            return {"source": "yahoo", "years": sorted(rows, key=lambda r: r["end"])} if rows else None
        except Exception:  # noqa: BLE001
            return None
    return _read(path) if offline else _cached(path, _TTL_FACTS, fetch)


def _get_text_bytes(url: str) -> bytes | None:
    """Raw bytes of an EDGAR document (rate-limited, identified)."""
    ua = _ua()
    if not ua:
        return None
    try:
        import requests
        _LIMIT.wait()
        r = requests.get(url, headers={"User-Agent": ua}, timeout=60)
        return r.content if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None
