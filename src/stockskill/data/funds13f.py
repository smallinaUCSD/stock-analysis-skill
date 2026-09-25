"""Hedge-fund holdings from SEC Form 13F (managers with $100M+ in US stocks
file their long positions every quarter, up to 45 days after quarter end).

For each fund: the latest two 13F-HR filings, holdings summed per security
(big funds split one stock across several rows), and the change between the
quarters (new, added, trimmed, sold out). 13F shows only long US positions
and options, not shorts, cash or foreign stocks, and it's 45+ days stale.

CUSIPs are mapped to tickers through OpenFIGI (free, no key) and cached for
good. The diff and parse functions are pure (tested).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import xml.etree.ElementTree as ET

from .sec import _get_json, _LIMIT, _ua

# Well-known managers (verified SEC filer IDs).
FUNDS = [
    ("Berkshire Hathaway", "Warren Buffett", 1067983),
    ("Pershing Square", "Bill Ackman", 2026053),
    ("Scion Asset Management", "Michael Burry", 1649339),
    ("Bridgewater Associates", "Ray Dalio", 1350694),
    ("Renaissance Technologies", "Jim Simons' firm", 1037389),
    ("Appaloosa", "David Tepper", 1656456),
    ("Duquesne Family Office", "Stanley Druckenmiller", 1536411),
    ("Third Point", "Dan Loeb", 1040273),
    ("Tiger Global", "Chase Coleman", 1167483),
    ("Coatue", "Philippe Laffont", 1135730),
    ("Baupost Group", "Seth Klarman", 1061768),
    ("Soros Fund Management", "George Soros", 1029160),
    ("ARK Investment", "Cathie Wood", 1697748),
    ("Icahn", "Carl Icahn", 921669),
    ("Viking Global", "Andreas Halvorsen", 1103804),
    ("Lone Pine Capital", "Stephen Mandel", 1061165),
    ("Himalaya Capital", "Li Lu", 1709323),
    ("Gates Foundation Trust", "Gates Foundation", 1166559),
    ("Point72", "Steve Cohen", 1603466),
    ("Elliott Investment Management", "Paul Singer", 1791786),
    ("Citadel Advisors", "Ken Griffin", 1423053),
]
_NS = re.compile(r"\{.*?\}")


def parse_info_table(xml_text: str) -> dict:
    """{cusip: {name, value, shares, put_call}} summed across rows. Puts and
    calls are kept as separate entries (cusip + ":PUT"/":CALL")."""
    out: dict = {}
    root = ET.fromstring(xml_text)
    for it in root.iter():
        if _NS.sub("", it.tag) != "infoTable":
            continue
        f = {_NS.sub("", c.tag): c for c in it}
        amt = {_NS.sub("", c.tag): c for c in (f.get("shrsOrPrnAmt") if f.get("shrsOrPrnAmt") is not None else [])}
        cusip = (f["cusip"].text or "").strip().upper() if "cusip" in f else ""
        if not cusip:
            continue
        pc = (f["putCall"].text or "").strip().upper() if "putCall" in f and f["putCall"].text else ""
        key = cusip + (":" + pc if pc else "")
        row = out.setdefault(key, {"cusip": cusip, "name": (f["nameOfIssuer"].text or "").strip()
                                   if "nameOfIssuer" in f else "", "value": 0.0, "shares": 0.0,
                                   "put_call": pc or None})
        row["value"] += float((f["value"].text or "0").strip() or 0) if "value" in f else 0.0
        row["shares"] += float((amt["sshPrnamt"].text or "0").strip() or 0) if "sshPrnamt" in amt else 0.0
    return out


def diff(cur: dict, prev: dict) -> list[dict]:
    """Positions this quarter with their change vs last quarter, largest first,
    followed by positions sold out entirely (value 0)."""
    total = sum(r["value"] for r in cur.values()) or 1.0
    rows = []
    for k, r in cur.items():
        p = prev.get(k)
        if p is None or not p.get("shares"):
            change, chg = "New", None
        else:
            chg = r["shares"] / p["shares"] - 1.0 if p["shares"] else None
            change = "Added" if chg is not None and chg > 0.02 else ("Trimmed" if chg is not None and chg < -0.02 else "Held")
        rows.append({**r, "key": k, "weight": r["value"] / total, "change": change, "share_change": chg})
    rows.sort(key=lambda r: r["value"], reverse=True)
    for k, p in prev.items():
        if k not in cur:
            rows.append({**p, "key": k, "value": 0.0, "weight": 0.0, "change": "Sold out",
                         "share_change": -1.0, "prev_value": p["value"]})
    return rows


# ------------------------------------------------------------------ fetching
def _dir(cache_dir):
    d = os.path.join(cache_dir or ".cache", "_13f")
    os.makedirs(d, exist_ok=True)
    return d


def _get_text(url: str) -> str | None:
    ua = _ua()
    if not ua:
        return None
    try:
        import requests
        _LIMIT.wait()
        r = requests.get(url, headers={"User-Agent": ua}, timeout=30)
        return r.text if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None


def _filings(cik: int, n: int = 2) -> list[dict]:
    j = _get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    if not j:
        return []
    rec = j["filings"]["recent"]
    out = []
    for i, form in enumerate(rec["form"]):
        if form == "13F-HR":
            out.append({"acc": rec["accessionNumber"][i], "filed": rec["filingDate"][i],
                        "period": rec["reportDate"][i], "name": j.get("name")})
            if len(out) >= n:
                break
    return out


def _holdings(cik: int, acc: str, cache_dir) -> dict | None:
    path = os.path.join(_dir(cache_dir), f"h_{acc}.json")
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except Exception:  # noqa: BLE001
            pass
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
    idx = _get_json(f"{base}/index.json")
    items = ((idx or {}).get("directory") or {}).get("item") or []
    xmls = [it["name"] for it in items if it["name"].lower().endswith(".xml")
            and "primary_doc" not in it["name"].lower()]
    if not xmls:
        return None
    text = _get_text(f"{base}/{xmls[0]}")
    if not text:
        return None
    try:
        h = parse_info_table(text)
    except ET.ParseError:
        return None
    json.dump(h, open(path, "w"))
    return h


_FIGI_LOCK = threading.Lock()


def map_cusips(cusips: list[str], cache_dir) -> dict:
    """{cusip: ticker} via OpenFIGI (no key: 10 per request, ~25 requests/min),
    cached permanently; unknowns are remembered as None."""
    path = os.path.join(_dir(cache_dir), "cusip_tickers.json")
    with _FIGI_LOCK:
        try:
            known = json.load(open(path))
        except Exception:  # noqa: BLE001
            known = {}
        need = [c for c in dict.fromkeys(cusips) if c not in known]
        try:
            import requests
            for i in range(0, len(need), 10):
                batch = need[i:i + 10]
                r = requests.post("https://api.openfigi.com/v3/mapping", timeout=30,
                                  json=[{"idType": "ID_CUSIP", "idValue": c} for c in batch])
                if r.status_code == 429:
                    time.sleep(6)
                    continue
                if r.status_code != 200:
                    break
                for c, res in zip(batch, r.json()):
                    data = res.get("data") or []
                    us = next((d for d in data if d.get("exchCode") == "US"), data[0] if data else None)
                    known[c] = us.get("ticker") if us else None
                time.sleep(2.5)
        except Exception:  # noqa: BLE001
            pass
        try:
            json.dump(known, open(path, "w"))
        except Exception:  # noqa: BLE001
            pass
    return {c: known.get(c) for c in cusips}


_SUFFIX = {"INC", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC", "HLDGS",
           "HOLDINGS", "HOLDING", "GROUP", "THE", "NEW", "CL", "CLASS", "SA", "NV", "AG", "LP",
           "DEL", "COM", "INCORPORATED", "ORD", "SHS", "ADR", "SPONSORED"}
_ABBR = {"FINL": "FINANCIAL", "PETE": "PETROLEUM", "AMER": "AMERICA", "BK": "BANK",
         "INTL": "INTERNATIONAL", "TECHNOLOGIES": "TECHNOLOGY", "SVCS": "SERVICES",
         "COMMUNICATIONS": "COMMUNICATION", "PHARMACEUTICALS": "PHARMACEUTICAL", "MTRS": "MOTORS"}


def _name_key(s: str) -> str:
    toks = re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper()).split()
    toks = [_ABBR.get(t, t) for t in toks if t not in _SUFFIX]
    return " ".join(toks)


def _names_to_tickers(cache_dir) -> dict:
    """{normalized SEC company title: ticker} from the SEC's ticker list."""
    from .sec import _cache_dir as sec_dir
    try:
        data = json.load(open(os.path.join(sec_dir(cache_dir), "company_tickers.json")))
    except Exception:  # noqa: BLE001
        return {}
    out: dict = {}
    for k in sorted(data, key=lambda x: int(x) if str(x).isdigit() else 0):
        v = data[k]
        out.setdefault(_name_key(v.get("title", "")), v.get("ticker"))
    return out


def fund_report(cik: int, cache_dir=None, top: int = 60) -> dict | None:
    """Latest quarter's holdings with changes vs the previous quarter."""
    path = os.path.join(_dir(cache_dir), f"report_{cik}.json")
    try:
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < 12 * 3600:
            return json.load(open(path))
    except Exception:  # noqa: BLE001
        pass
    fl = _filings(cik, 2)
    if not fl:
        return None
    cur = _holdings(cik, fl[0]["acc"], cache_dir) or {}
    prev = _holdings(cik, fl[1]["acc"], cache_dir) if len(fl) > 1 else {}
    rows = diff(cur, prev or {})
    held = [r for r in rows if r["change"] != "Sold out"]
    sold = sorted((r for r in rows if r["change"] == "Sold out"), key=lambda r: r.get("prev_value") or 0,
                  reverse=True)
    keep = held[:top] + sold[:15]
    tickers = map_cusips([r["cusip"] for r in keep], cache_dir)
    by_name = None
    for r in keep:
        r["ticker"] = tickers.get(r["cusip"])
        if not r["ticker"]:                              # fall back to the issuer's name
            by_name = by_name if by_name is not None else _names_to_tickers(cache_dir)
            r["ticker"] = by_name.get(_name_key(r.get("name", "")))
    fund = next((f for f in FUNDS if f[2] == cik), None)
    out = {"cik": cik, "fund": fund[0] if fund else fl[0]["name"], "manager": fund[1] if fund else "",
           "filer": fl[0]["name"], "period": fl[0]["period"], "filed": fl[0]["filed"],
           "prev_period": fl[1]["period"] if len(fl) > 1 else None,
           "total_value": sum(r["value"] for r in held), "positions": len(held),
           "holdings": held[:top], "sold_out": sold[:15],
           "counts": {k: sum(1 for r in rows if r["change"] == k) for k in ("New", "Added", "Trimmed", "Sold out")}}
    try:
        json.dump(out, open(path, "w"))
    except Exception:  # noqa: BLE001
        pass
    return out


def search_filers(query: str) -> list[dict]:
    """13F filers whose name matches ``query`` (EDGAR company search)."""
    q = (query or "").strip()
    if len(q) < 2:
        return []
    import urllib.parse
    text = _get_text("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=13F-HR"
                     f"&company={urllib.parse.quote(q)}&dateb=&owner=include&count=20&output=atom")
    if not text:
        return []
    out = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    for el in root.iter():
        tag = _NS.sub("", el.tag)
        if tag == "company-info":
            d = {_NS.sub("", c.tag): (c.text or "").strip() for c in el}
            if d.get("cik"):
                out.append({"cik": int(d["cik"]), "name": d.get("conformed-name", "")})
        if tag == "entry":
            cells = {_NS.sub("", c.tag): c for c in el}
            content = cells.get("content")
            if content is not None:
                d = {_NS.sub("", c.tag): (c.text or "").strip() for c in content.iter()}
                if d.get("cik"):
                    out.append({"cik": int(d["cik"]), "name": d.get("name") or d.get("conformed-name", "")})
    # the feed's names are broken ("ARRAY(0x...)"): take them from each filer's
    # submissions, which also confirms it actually files 13Fs
    seen, uniq = set(), []
    for r in out:
        if r["cik"] in seen or len(uniq) >= 8:
            continue
        seen.add(r["cik"])
        j = _get_json(f"https://data.sec.gov/submissions/CIK{r['cik']:010d}.json")
        if not j:
            continue
        rec = (j.get("filings") or {}).get("recent") or {}
        dates = [d for f, d in zip(rec.get("form", []), rec.get("reportDate", [])) if f == "13F-HR"]
        if dates:
            uniq.append({"cik": r["cik"], "name": j.get("name") or "", "latest": dates[0]})
    return uniq


def holders_of(ticker: str, cache_dir=None) -> list[dict]:
    """Tracked funds holding ``ticker`` in their latest cached 13F."""
    t = ticker.upper()
    out = []
    for name, mgr, cik in FUNDS:
        path = os.path.join(_dir(cache_dir), f"report_{cik}.json")
        try:
            rep = json.load(open(path))
        except Exception:  # noqa: BLE001
            continue
        for r in rep.get("holdings", []) + rep.get("sold_out", []):
            if r.get("ticker") == t and not r.get("put_call"):
                out.append({"fund": name, "manager": mgr, "cik": cik, "period": rep.get("period"),
                            "value": r["value"], "weight": r["weight"], "change": r["change"],
                            "share_change": r.get("share_change")})
    return sorted(out, key=lambda r: r["value"], reverse=True)


_WARM = {"running": False}


def warm_all(cache_dir=None) -> None:
    """Build every tracked fund's report in a background thread (first run
    takes a few minutes: two filings per fund plus ticker mapping)."""
    if _WARM["running"] or not _ua():
        return

    def run():
        try:
            for _name, _mgr, cik in FUNDS:
                try:
                    fund_report(cik, cache_dir)
                except Exception:  # noqa: BLE001
                    continue
        finally:
            _WARM["running"] = False
    _WARM["running"] = True
    threading.Thread(target=run, daemon=True).start()


def summaries(cache_dir=None) -> list[dict]:
    """Tracked funds with their cached report's headline numbers (None = not built yet)."""
    out = []
    for name, mgr, cik in FUNDS:
        rep = None
        try:
            rep = json.load(open(os.path.join(_dir(cache_dir), f"report_{cik}.json")))
        except Exception:  # noqa: BLE001
            rep = None
        out.append({"cik": cik, "fund": name, "manager": mgr,
                    "period": (rep or {}).get("period"), "total_value": (rep or {}).get("total_value"),
                    "positions": (rep or {}).get("positions"), "counts": (rep or {}).get("counts"),
                    "top": [h.get("ticker") or h.get("name") for h in (rep or {}).get("holdings", [])[:5]]})
    return out


# ------------------------------------------------------------------ history + copy performance

def quarter_label(period: str) -> str:
    """'2026-06-30' -> 'Q2 2026'."""
    try:
        y, m = int(period[:4]), int(period[5:7])
        return f"Q{(m - 1) // 3 + 1} {y}"
    except (TypeError, ValueError):
        return period or ""


def _long_stock(h: dict) -> dict:
    return {k: r for k, r in (h or {}).items() if not r.get("put_call") and r.get("value")}


def history_events(quarters: list[dict], top: int = 25) -> list[dict]:
    """Changes between consecutive quarters for positions that were ever in
    the top ``top``: New, Added, Trimmed, Sold out (Held is skipped).
    ``quarters``: oldest first, each {period, filed, holdings: {cusip: row}}."""
    watch = set()
    for q in quarters:
        rows = sorted(_long_stock(q["holdings"]).items(), key=lambda kv: kv[1]["value"], reverse=True)[:top]
        watch |= {k for k, _ in rows}
    out = []
    for prev, cur in zip(quarters, quarters[1:]):
        for r in diff(_long_stock(cur["holdings"]), _long_stock(prev["holdings"])):
            if r["key"] in watch and r["change"] != "Held":
                out.append({"period": cur["period"], "filed": cur["filed"], "cusip": r["cusip"], "name": r["name"],
                            "change": r["change"], "share_change": r.get("share_change"),
                            "value": r["value"] or r.get("prev_value") or 0})
    return out


def copy_performance(plan: list[tuple[str, dict]], prices: dict, bench: tuple, start_value: float = 10_000.0) -> dict | None:
    """Value of copying the reported portfolio: on each filing date (when the
    13F became public) move into its weights, hold until the next filing.
    ``plan``: [(filed iso date, {ticker: weight})] oldest first; ``prices``:
    {ticker: (dates, closes)}; ``bench``: (dates, closes) for the S&P 500."""
    bd, bc = bench
    if not plan or not bd:
        return None
    from bisect import bisect_left, bisect_right
    lookup = {t: dict(zip(d, c)) for t, (d, c) in prices.items()}
    start = plan[0][0]
    days = [d for d in bd if d >= start]
    if len(days) < 2:
        return None
    value, bench_v, dates, vals, bvals = start_value, start_value, [], [], []
    holdings: dict = {}
    last_px: dict = {}
    b0 = bc[bisect_left(bd, days[0])]
    k = 0
    for i, d in enumerate(days):
        # mark to market with today's closes (carry the last price over gaps)
        for t in holdings:
            px = lookup.get(t, {}).get(d)
            if px:
                last_px[t] = px
        if holdings:
            value = sum(sh * last_px.get(t, 0) for t, sh in holdings.items()) or value
        while k < len(plan) and plan[k][0] <= d:        # a new filing is public: rebalance at today's close
            w = {t: x for t, x in plan[k][1].items() if lookup.get(t, {}).get(d)}
            tot = sum(w.values())
            if tot > 0:
                holdings = {t: value * x / tot / lookup[t][d] for t, x in w.items()}
                last_px.update({t: lookup[t][d] for t in w})
            k += 1
        bench_v = start_value * bc[bisect_right(bd, d) - 1] / b0
        dates.append(d)
        vals.append(round(value, 2))
        bvals.append(round(bench_v, 2))
    years = max((len(dates) - 1) / 252, 1e-9)
    ret, bret = vals[-1] / start_value - 1, bvals[-1] / start_value - 1
    return {"dates": dates, "value": vals, "bench": bvals,
            "summary": {"return": ret, "bench_return": bret, "years": years,
                        "cagr": (1 + ret) ** (1 / years) - 1 if years >= 1 else None,
                        "bench_cagr": (1 + bret) ** (1 / years) - 1 if years >= 1 else None}}


def _download_prices(tickers: list[str], start: str, cache_dir) -> dict:
    """{ticker: ([iso dates], [closes])} from Yahoo, cached for the day."""
    path = os.path.join(_dir(cache_dir), f"px_{abs(hash((tuple(sorted(tickers)), start))) % 10**12}.json")
    try:
        if time.time() - os.path.getmtime(path) < 12 * 3600:
            return {t: tuple(v) for t, v in json.load(open(path)).items()}
    except OSError:
        pass
    out = {}
    try:
        import yfinance as yf
        df = yf.download(sorted(set(tickers)), start=start, interval="1d", group_by="ticker", auto_adjust=True,
                         progress=False, threads=True)
        for t in set(tickers):
            try:
                col = df[t]["Close"].dropna()
            except Exception:  # noqa: BLE001
                continue
            if len(col):
                out[t] = ([i.date().isoformat() for i in col.index], [float(v) for v in col.values])
    except Exception:  # noqa: BLE001
        return out
    try:
        json.dump(out, open(path, "w"))
    except Exception:  # noqa: BLE001
        pass
    return out


def fund_history(cik: int, cache_dir=None, quarters: int = 8, top: int = 20) -> dict | None:
    """Reported value by quarter, the position-change timeline, and what
    copying the top ``top`` holdings would have returned vs the S&P 500."""
    path = os.path.join(_dir(cache_dir), f"history_{cik}.json")
    try:
        if time.time() - os.path.getmtime(path) < 12 * 3600:
            return json.load(open(path))
    except OSError:
        pass
    fl = _filings(cik, quarters)
    qs = []
    for f in reversed(fl):
        h = _holdings(cik, f["acc"], cache_dir)
        if h:
            qs.append({"period": f["period"], "filed": f["filed"], "acc": f["acc"], "holdings": h})
    if not qs:
        return None
    events = history_events(qs, top=25)
    tops = []
    for q in qs:
        rows = sorted(_long_stock(q["holdings"]).values(), key=lambda r: r["value"], reverse=True)[:top]
        tops.append(rows)
    cusips = sorted({r["cusip"] for rows in tops for r in rows} | {e["cusip"] for e in events})
    tk = map_cusips(cusips, cache_dir)
    by_name = None
    for c in cusips:
        if not tk.get(c):
            by_name = by_name if by_name is not None else _names_to_tickers(cache_dir)

    def ticker(c, name):
        return tk.get(c) or ((by_name or {}).get(_name_key(name or "")))
    for e in events:
        e["ticker"] = ticker(e["cusip"], e["name"])
    plan = []
    for q, rows in zip(qs, tops):
        w = {}
        for r in rows:
            t = ticker(r["cusip"], r["name"])
            if t:
                w[t] = w.get(t, 0) + r["value"]
        plan.append((q["filed"], w))
    perf = None
    tickers = sorted({t for _, w in plan for t in w})
    if tickers:
        px = _download_prices(tickers + ["SPY"], qs[0]["filed"], cache_dir)
        spy = px.pop("SPY", None)
        if spy:
            perf = copy_performance(plan, px, spy)
    out = {"cik": cik, "quarters": [{"period": q["period"], "label": quarter_label(q["period"]), "filed": q["filed"],
                                     "value": sum(r["value"] for r in _long_stock(q["holdings"]).values()),
                                     "positions": len(_long_stock(q["holdings"]))} for q in qs],
           "events": events, "performance": perf, "copied_top": top}
    try:
        json.dump(out, open(path, "w"))
    except Exception:  # noqa: BLE001
        pass
    return out
