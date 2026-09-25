"""Major customers from a company's latest 10-K (XBRL customer-concentration tags).

US companies must disclose any customer that is 10% or more of revenue. In the
filing's XBRL these are ``ConcentrationRiskPercentage1`` facts on the
``MajorCustomersAxis``: sometimes named (``MicrosoftMember``), often anonymous
(``CustomerOneMember``, ``ResellerAMember``). ``extract_concentration`` is pure
(tested); ``major_customers`` finds the filing and caches the result.
"""

from __future__ import annotations

import json
import os
import re

_REVENUE = ("Revenue", "SalesRevenue", "Revenues")
_ANON = re.compile(r"^(customer|reseller|distributor|partner|client|oem|odm|channel|direct|indirect|"
                   r"end|major|largest|significant|one|two|three|four|five|a|b|c|d|e|\d+)$", re.I)
_WORDNUM = {"One": "1", "Two": "2", "Three": "3", "Four": "4", "Five": "5", "Six": "6"}


def _humanize(member: str) -> str:
    """"nvda:CustomerOneMember" -> "Customer One"; "crwv:MicrosoftMember" -> "Microsoft"."""
    local = member.split(":")[-1]
    local = re.sub(r"Member$", "", local)
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\b|\d)|[A-Z]?[a-z]+|\d+|[A-Z]+", local)
    return " ".join(words).strip()


def is_anonymous(label: str) -> bool:
    low = label.lower()
    if low.startswith(("customer", "reseller", "distributor", "undisclosed", "largest", "major customer")):
        return True
    toks = label.split()
    return bool(toks) and all(_ANON.match(t) for t in toks)


def short_label(label: str) -> str:
    """Compact node label: "Customer One" -> "Cust 1", "Reseller A" -> "Resl A"."""
    label = re.sub(r"(?i)^(customer|reseller|distributor)(one|two|three|four|five|six)$",
                   lambda m: f"{m.group(1).capitalize()} {m.group(2).capitalize()}", label)
    toks = label.split()
    if is_anonymous(label) and len(toks) == 1:
        return toks[0][:6]
    if len(toks) >= 2 and is_anonymous(label):
        head = {"customer": "Cust", "reseller": "Resl", "distributor": "Dist"}.get(toks[0].lower(), toks[0][:4])
        return f"{head} {_WORDNUM.get(toks[-1], toks[-1])}"
    return label.split()[0][:6]


def extract_concentration(xml_bytes: bytes) -> dict:
    """{period_end, customers: [{member, label, pct, segment, anonymous}]} for the
    latest fiscal year's revenue concentration (receivables ignored)."""
    from lxml import etree
    root = etree.fromstring(xml_bytes)
    ns = {"xbrli": "http://www.xbrl.org/2003/instance", "xbrldi": "http://xbrl.org/2006/xbrldi"}
    ctx = {}
    for c in root.findall(".//xbrli:context", ns):
        dims = {m.get("dimension"): m.text for m in c.findall(".//xbrldi:explicitMember", ns)}
        end = c.findtext(".//xbrli:endDate", namespaces=ns) or c.findtext(".//xbrli:instant", namespaces=ns)
        ctx[c.get("id")] = (dims, end)
    rows = []
    for el in root.iter():
        if not (isinstance(el.tag, str) and el.tag.endswith("}ConcentrationRiskPercentage1")):
            continue
        dims, end = ctx.get(el.get("contextRef"), ({}, None))
        member = next((v for k, v in dims.items() if k.endswith("MajorCustomersAxis")), None)
        bench = next((v for k, v in dims.items() if k.endswith("ConcentrationRiskByBenchmarkAxis")), "") or ""
        if not member or not any(r in bench for r in _REVENUE) or any(k.endswith("StatementGeographicalAxis") for k in dims):
            continue
        try:
            pct = float(el.text)
        except (TypeError, ValueError):
            continue
        seg = next((v for k, v in dims.items() if k.endswith("StatementBusinessSegmentsAxis")), None)
        rows.append({"member": member, "end": end, "pct": pct, "segment": _humanize(seg) if seg else None})
    if not rows:
        return {"period_end": None, "customers": []}
    latest = max(r["end"] or "" for r in rows)
    best: dict = {}
    for r in rows:
        if r["end"] != latest:
            continue
        key = (r["member"], r["segment"])
        if key not in best or r["pct"] > best[key]["pct"]:
            best[key] = r
    out = []
    for r in sorted(best.values(), key=lambda r: r["pct"], reverse=True):
        label = re.sub(r"(?i)^(customer|reseller|distributor)(one|two|three|four|five|six)$",
                       lambda m: f"{m.group(1).capitalize()} {m.group(2).capitalize()}", _humanize(r["member"]))
        out.append({"member": r["member"], "label": label, "pct": r["pct"], "segment": r["segment"],
                    "anonymous": is_anonymous(label), "short": short_label(label)})
    return {"period_end": latest, "customers": out}


def major_customers(ticker: str, cache_dir=None) -> dict | None:
    """Latest 10-K's major customers, cached per filing. None without SEC access."""
    from .sec import _cache_dir, _get_json, _get_text_bytes, cik_for
    cik = cik_for(ticker, cache_dir)
    if not cik:
        return None
    sub = _get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    if not sub:
        return None
    rec = sub["filings"]["recent"]
    try:
        i = next(k for k, f in enumerate(rec["form"]) if f in ("10-K", "10-K/A"))
    except StopIteration:
        return {"period_end": None, "customers": [], "filed": None, "none_filed": True}
    acc = rec["accessionNumber"][i]
    path = os.path.join(_cache_dir(cache_dir), f"cust_{acc}.json")
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except Exception:  # noqa: BLE001
            pass
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
    idx = _get_json(f"{base}/index.json")
    names = [it["name"] for it in ((idx or {}).get("directory") or {}).get("item", [])]
    inst = next((n for n in names if n.endswith("_htm.xml")), None) or \
        next((n for n in names if n.endswith(".xml") and not re.search(r"(FilingSummary|_cal|_def|_lab|_pre)", n)), None)
    if not inst:
        return None
    raw = _get_text_bytes(f"{base}/{inst}")
    if not raw:
        return None
    try:
        out = extract_concentration(raw)
    except Exception:  # noqa: BLE001
        return None
    out.update({"filed": rec["filingDate"][i], "url": f"{base}/"})
    try:
        json.dump(out, open(path, "w"))
    except Exception:  # noqa: BLE001
        pass
    return out
