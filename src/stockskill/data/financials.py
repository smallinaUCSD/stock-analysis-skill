"""Multi-year financial statements and ratios from SEC XBRL company facts.

The Bloomberg "FA" view for free: ten fiscal years of the income statement,
balance sheet and cash-flow statement as filed in 10-Ks, plus ratios computed
here (never estimated). ``build_statements`` is pure (unit-tested);
``statements`` fetches and caches per company.
"""

from __future__ import annotations

import os

from . import sec as SEC

_TTL = 86400

FLOW = {
    "revenue": SEC._FLOW["revenue"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold",
                        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"],
    "gross_profit": ["GrossProfit"],
    "rnd": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
    "sga": ["SellingGeneralAndAdministrativeExpense"],
    "op_income": ["OperatingIncomeLoss"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
    "pretax_income": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                      "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
                      "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic"],
    "income_tax": ["IncomeTaxExpenseBenefit"],
    "net_income": SEC._FLOW["net_income"],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"],
    "shares": SEC._FLOW["shares"],
    "ocf": SEC._FLOW["ocf"],
    "capex": SEC._FLOW["capex"],
    "da": SEC._FLOW["da"],
    "sbc": SEC._FLOW["sbc"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfEquity"],
    "dividends": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "acquisitions": ["PaymentsToAcquireBusinessesNetOfCashAcquired", "PaymentsToAcquireBusinessesGross"],
}
INSTANT = {
    "cash": SEC._INSTANT["cash"],
    "st_investments": ["ShortTermInvestments", "MarketableSecuritiesCurrent",
                       "AvailableForSaleSecuritiesDebtSecuritiesCurrent"],
    "receivables": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
    "inventory": ["InventoryNet"],
    "current_assets": ["AssetsCurrent"],
    "ppe": ["PropertyPlantAndEquipmentNet",
            "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization"],
    "goodwill": ["Goodwill"],
    "total_assets": ["Assets"],
    "payables": ["AccountsPayableCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "long_term_debt": SEC._INSTANT["long_term_debt"],
    "total_liabilities": ["Liabilities"],
    "liab_and_equity": ["LiabilitiesAndStockholdersEquity"],
    "equity": ["StockholdersEquity",
               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
}
UNITS = {"eps": "USD/shares"}

# (key, label, kind) - kind: "usd" (dollars), "eps" (per share), "sh" (shares), "pct", "x" (multiple)
LAYOUT = {
    "income": [
        ("revenue", "Revenue", "usd"),
        ("cost_of_revenue", "Cost of revenue", "usd"),
        ("gross_profit", "Gross profit", "usd"),
        ("rnd", "Research & development", "usd"),
        ("sga", "Selling, general & admin", "usd"),
        ("op_income", "Operating income", "usd"),
        ("interest_expense", "Interest expense", "usd"),
        ("pretax_income", "Pre-tax income", "usd"),
        ("income_tax", "Income tax", "usd"),
        ("net_income", "Net income", "usd"),
        ("eps", "EPS (diluted)", "eps"),
        ("shares", "Diluted shares", "sh"),
    ],
    "balance": [
        ("cash", "Cash & equivalents", "usd"),
        ("st_investments", "Short-term investments", "usd"),
        ("receivables", "Receivables", "usd"),
        ("inventory", "Inventory", "usd"),
        ("current_assets", "Current assets", "usd"),
        ("ppe", "Property, plant & equipment", "usd"),
        ("goodwill", "Goodwill", "usd"),
        ("total_assets", "Total assets", "usd"),
        ("payables", "Accounts payable", "usd"),
        ("current_liabilities", "Current liabilities", "usd"),
        ("long_term_debt", "Long-term debt", "usd"),
        ("total_liabilities", "Total liabilities", "usd"),
        ("equity", "Shareholders' equity", "usd"),
    ],
    "cashflow": [
        ("ocf", "Operating cash flow", "usd"),
        ("capex", "Capital expenditure", "usd"),
        ("fcf", "Free cash flow", "usd"),
        ("sbc", "Stock-based compensation", "usd"),
        ("da", "Depreciation & amortization", "usd"),
        ("buybacks", "Share buybacks", "usd"),
        ("dividends", "Dividends paid", "usd"),
        ("acquisitions", "Acquisitions", "usd"),
    ],
    "ratios": [
        ("rev_growth", "Revenue growth", "pct"),
        ("eps_growth", "EPS growth", "pct"),
        ("gross_margin", "Gross margin", "pct"),
        ("op_margin", "Operating margin", "pct"),
        ("net_margin", "Net margin", "pct"),
        ("fcf_margin", "Free cash flow margin", "pct"),
        ("rnd_pct", "R&D / revenue", "pct"),
        ("sbc_pct", "Stock comp / revenue", "pct"),
        ("capex_pct", "Capex / revenue", "pct"),
        ("tax_rate", "Effective tax rate", "pct"),
        ("roe", "Return on equity", "pct"),
        ("roic", "Return on invested capital", "pct"),
        ("current_ratio", "Current ratio", "x"),
        ("debt_equity", "Debt / equity", "x"),
        ("interest_cover", "Interest coverage", "x"),
        ("share_change", "Share count change", "pct"),
        ("payout", "Buybacks + dividends / FCF", "pct"),
    ],
}


def _div(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


def _avg(a, b):
    if a is None:
        return b
    return a if b is None else (a + b) / 2


def _growth(cur, prev):
    if cur is None or prev is None or prev <= 0:
        return None
    return cur / prev - 1


def derive(rows: list[dict]) -> list[dict]:
    """Add filled-in lines (gross profit, FCF, total liabilities) and ratios.
    Rows oldest -> newest; returns new dicts."""
    out = []
    prev = None
    for r in rows:
        r = dict(r)
        rev = r.get("revenue")
        if r.get("gross_profit") is None and rev is not None and r.get("cost_of_revenue") is not None:
            r["gross_profit"] = rev - r["cost_of_revenue"]
        if r.get("ocf") is not None and r.get("capex") is not None:
            r["fcf"] = r["ocf"] - r["capex"]
        if r.get("total_liabilities") is None and r.get("liab_and_equity") is not None and r.get("equity") is not None:
            r["total_liabilities"] = r["liab_and_equity"] - r["equity"]
        r.pop("liab_and_equity", None)
        p = prev or {}
        r["rev_growth"] = _growth(rev, p.get("revenue"))
        r["eps_growth"] = _growth(r.get("eps"), p.get("eps"))
        r["gross_margin"] = _div(r.get("gross_profit"), rev)
        r["op_margin"] = _div(r.get("op_income"), rev)
        r["net_margin"] = _div(r.get("net_income"), rev)
        r["fcf_margin"] = _div(r.get("fcf"), rev)
        r["rnd_pct"] = _div(r.get("rnd"), rev)
        r["sbc_pct"] = _div(r.get("sbc"), rev)
        r["capex_pct"] = _div(r.get("capex"), rev)
        pti = r.get("pretax_income")
        tax = _div(r.get("income_tax"), pti) if pti and pti > 0 else None
        r["tax_rate"] = tax if tax is None or 0 <= tax <= 0.6 else None
        eq = _avg(r.get("equity"), p.get("equity"))
        r["roe"] = _div(r.get("net_income"), eq) if eq and eq > 0 else None
        invested = None
        if r.get("equity") is not None:
            invested = r["equity"] + (r.get("long_term_debt") or 0) - (r.get("cash") or 0)
        nopat = r["op_income"] * (1 - (r["tax_rate"] if r["tax_rate"] is not None else 0.21)) \
            if r.get("op_income") is not None else None
        r["roic"] = _div(nopat, invested) if invested and invested > 0 else None
        r["current_ratio"] = _div(r.get("current_assets"), r.get("current_liabilities"))
        eqn = r.get("equity")
        r["debt_equity"] = _div(r.get("long_term_debt") or 0, eqn) if eqn and eqn > 0 else None
        ie = r.get("interest_expense")
        r["interest_cover"] = _div(r.get("op_income"), ie) if ie and ie > 0 else None
        r["share_change"] = _growth(r.get("shares"), p.get("shares"))
        paid = (r.get("buybacks") or 0) + (r.get("dividends") or 0)
        fcf = r.get("fcf")
        r["payout"] = paid / fcf if fcf and fcf > 0 and paid else None
        out.append(r)
        prev = r
    return out


def cagr(rows: list[dict], key: str, years: int) -> float | None:
    """Compound annual growth of ``key`` over the last ``years`` years."""
    if len(rows) <= years:
        return None
    a, b = rows[-1 - years].get(key), rows[-1].get(key)
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return (b / a) ** (1 / years) - 1


_CLEAN = (1.5, 2, 3, 4, 5, 6, 7, 8, 10, 15, 20, 25, 30, 40, 50, 100)


def _clean_ratio(r: float) -> float | None:
    """Snap a restatement ratio to a stock-split ratio (or its inverse for a
    reverse split); None if it is not one."""
    inv = r < 1
    x = 1 / r if inv else r
    hit = next((c for c in _CLEAN if abs(x - c) / c < 0.03), None)
    if hit is None:
        return None
    return 1 / hit if inv else float(hit)


def split_events(facts: dict) -> list[tuple[str, float]]:
    """[(filed_date, ratio)] of stock splits, inferred from the company's own
    restatements: when a later 10-K reports a past year's diluted share count
    at a clean multiple of what was first filed, a split happened in between."""
    gaap = ((facts or {}).get("facts") or {}).get("us-gaap") or {}
    by_period: dict = {}
    # share counts rise by the split ratio; EPS falls by it
    for concept, unit, inverse in (("WeightedAverageNumberOfDilutedSharesOutstanding", "shares", False),
                                   ("WeightedAverageNumberOfSharesOutstandingBasic", "shares", False),
                                   ("EarningsPerShareDiluted", "USD/shares", True),
                                   ("EarningsPerShareBasic", "USD/shares", True)):
        for f in ((gaap.get(concept) or {}).get("units") or {}).get(unit) or []:
            if f.get("form") in SEC._ANNUAL_FORMS and f.get("start") and f.get("val"):
                by_period.setdefault((concept, inverse, f["start"], f["end"]), []).append(
                    (f.get("filed", ""), float(f["val"])))
    found: list[tuple[str, float]] = []
    for (_, inverse, _, _), vals in by_period.items():
        vals.sort()
        for (_, a), (d2, b) in zip(vals, vals[1:]):
            if not a or not b or (a < 0) != (b < 0):
                continue
            r = _clean_ratio(a / b if inverse else b / a)
            if r:
                found.append((d2, r))
    # one event per split: the earliest filing that reveals it
    events: list[tuple[str, float]] = []
    for d, r in sorted(found):
        if not any(abs(r - e[1]) < 1e-9 and abs(_days(e[0], d)) < 400 for e in events):
            events.append((d, r))
    return events


def _days(a: str, b: str) -> int:
    from datetime import date
    try:
        return (date.fromisoformat(b) - date.fromisoformat(a)).days
    except ValueError:
        return 10 ** 6


def split_adjust(rows: list[dict], events: list[tuple[str, float]]) -> list[dict]:
    """Restate EPS and share counts on today's share basis. A value first
    filed before a split is multiplied (shares) or divided (EPS) by it."""
    out = []
    for r in rows:
        r = dict(r)
        for key, inverse in (("shares", False), ("eps", True)):
            filed = r.get("_f_" + key)
            if r.get(key) is None or not filed:
                continue
            f = 1.0
            for d, ratio in events:
                if d > filed:
                    f *= ratio
            if f != 1.0:
                r[key] = r[key] / f if inverse else r[key] * f
        out.append(r)
    return out


def build_statements(facts: dict, years: int = 10) -> dict:
    """{name, years: [...rows], cagr: {...}, splits} from a company-facts JSON."""
    rows = SEC.extract_annual(facts, FLOW, INSTANT, UNITS, fallback=True, keep_filed=True)
    rows = [r for r in rows if r.get("revenue") is not None or r.get("net_income") is not None]
    events = split_events(facts)
    rows = split_adjust(rows, events)
    rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    rows = derive(rows)[-years:]
    cg = {}
    for key in ("revenue", "eps", "fcf", "net_income"):
        cg[key] = {n: cagr(rows, key, n) for n in (3, 5, 10) if len(rows) > n}
    return {"name": (facts or {}).get("entityName"), "years": rows, "cagr": cg,
            "splits": [{"filed": d, "ratio": r} for d, r in events]}


def statements(ticker: str, cache_dir: str | None = None) -> dict | None:
    """Cached statements for ``ticker``; None without SEC access or for
    non-US-GAAP filers."""
    cik = SEC.cik_for(ticker, cache_dir)
    if not cik:
        return None
    path = os.path.join(SEC._cache_dir(cache_dir), f"fin_{cik}.json")

    def fetch():
        facts = SEC._get_json(f"{SEC._BASE_DATA}/api/xbrl/companyfacts/CIK{cik:010d}.json")
        if not facts:
            return None
        return {"cik": cik, **build_statements(facts)}

    data = SEC._cached(path, _TTL, fetch)
    if not data or not data.get("years"):
        return None
    return data
