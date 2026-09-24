"""Knowledge graph around one company: who supplies it, who buys from it, what
it has invested in, who competes with it, and which watchlist companies name it
in their annual reports.

Four sources, each labeled on the page:
* curated supplier/customer links (data/relationships.json), each with where
  it's documented;
* the company's own SEC 13F filing (stakes it holds in listed companies);
* SEC full-text search: watchlist companies whose latest 10-K mentions it;
* industry peers from SEC industry codes.

``neighbors`` is pure (tested); the rest fetch and cache.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import date, timedelta

_REL_PATH = "data/relationships.json"


def load_relationships(path: str = _REL_PATH) -> dict:
    try:
        return json.load(open(path))
    except Exception:  # noqa: BLE001
        return {"names": {}, "edges": []}


def neighbors(center: str, rel: dict) -> dict:
    """{suppliers, customers, investments} from the curated edges for ``center``."""
    names = rel.get("names") or {}
    out = {"suppliers": [], "customers": [], "investments": []}
    for e in rel.get("edges") or []:
        node = None
        if e.get("to") == center and e.get("kind", "supplies") == "supplies":
            node, group = e["from"], "suppliers"
        elif e.get("from") == center and e.get("kind", "supplies") == "supplies":
            node, group = e["to"], "customers"
        elif e.get("from") == center and e.get("kind") == "invests":
            node, group = e["to"], "investments"
        if node is None:
            continue
        is_ticker = bool(re.fullmatch(r"[A-Z]{1,5}", node))
        out[group].append({"ticker": node if is_ticker else None, "name": names.get(node, node),
                           "what": e.get("what", ""), "basis": e.get("basis", ""), "source": "curated"})
    return out


def short_name(name: str) -> str:
    """"NVIDIA Corp" -> "NVIDIA"; "Taiwan Semiconductor Manufacturing Co Ltd" ->
    "Taiwan Semiconductor"; used as the phrase for the filings search."""
    toks = re.sub(r"[,.]", " ", name or "").split()
    stop = {"inc", "corp", "corporation", "co", "company", "ltd", "limited", "plc", "holdings", "group",
            "class", "a", "b", "the", "nv", "n", "v", "sa", "ag", "technologies", "manufacturing"}
    keep = [t for t in toks if t.lower() not in stop]
    return " ".join(keep[:2]) if keep else (name or "")


def filing_mentions(name: str, watch_ciks: dict, cache_dir=None, months: int = 15) -> list[dict]:
    """Watchlist companies whose recent 10-K mentions ``name`` (SEC full-text
    search), cached a week. ``watch_ciks``: {cik: ticker}."""
    from .sec import _cache_dir, _get_json
    phrase = short_name(name)
    if len(phrase) < 3:
        return []
    path = os.path.join(_cache_dir(cache_dir), f"mentions_{re.sub(r'[^A-Za-z0-9]', '_', phrase)}.json")
    hits = None
    try:
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < 7 * 86400:
            hits = json.load(open(path))
    except Exception:  # noqa: BLE001
        hits = None
    if hits is None:
        import urllib.parse
        hits = []
        start = (date.today() - timedelta(days=months * 30)).isoformat()
        for frm in (0, 100, 200):
            q = urllib.parse.urlencode({"q": f'"{phrase}"', "forms": "10-K", "dateRange": "custom",
                                        "startdt": start, "enddt": date.today().isoformat(), "from": frm})
            j = _get_json(f"https://efts.sec.gov/LATEST/search-index?{q}")
            rows = ((j or {}).get("hits") or {}).get("hits") or []
            for h in rows:
                src = h.get("_source") or {}
                for c in src.get("ciks") or []:
                    hits.append({"cik": int(c), "filed": src.get("file_date"), "adsh": src.get("adsh"),
                                 "name": (src.get("display_names") or [""])[0]})
            if len(rows) < 100:
                break
        try:
            json.dump(hits, open(path, "w"))
        except Exception:  # noqa: BLE001
            pass
    out, seen = [], set()
    for h in hits:
        tk = watch_ciks.get(h["cik"])
        if tk and tk not in seen:
            seen.add(tk)
            acc = (h.get("adsh") or "").replace("-", "")
            out.append({"ticker": tk, "name": re.sub(r"\s+\(.*$", "", h.get("name") or tk),
                        "what": f"Names {phrase} in its annual report", "basis": f"10-K filed {h.get('filed')}",
                        "url": f"https://www.sec.gov/Archives/edgar/data/{h['cik']}/{acc}/" if acc else None,
                        "source": "filings"})
    return out
