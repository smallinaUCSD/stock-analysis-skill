"""Who the politicians are, and President Trump's trades.

* Members of Congress: party, first day in office, committees and official
  photos from the public-domain congress-legislators project
  (theunitedstates.io), matched to the names on their trade filings.
* The President: OGE Form 278-T periodic transaction reports. They are scanned
  PDFs with an OCR text layer, so the row parser (``parse_278t_line``) is
  tolerant of OCR noise and company names are fuzzy-matched to tickers.

Pure parsers are tested; fetches are cached on disk.
"""

from __future__ import annotations

import difflib
import io
import json
import os
import re
import time
from datetime import date, timedelta

_LEG = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
_COMM = "https://unitedstates.github.io/congress-legislators/committee-membership-current.json"
_COMMS = "https://unitedstates.github.io/congress-legislators/committees-current.json"
PHOTO = "https://unitedstates.github.io/images/congress/225x275/{bioguide}.jpg"
TRUMP_ID = "trump"
TRUMP = {"id": TRUMP_ID, "name": "Donald J. Trump", "party": "Republican", "chamber": "President",
         "state": "", "office": "47th President of the United States",
         "since": "2025-01-20", "since_note": "also 45th President, 2017-2021",
         "photo": "https://commons.wikimedia.org/wiki/Special:FilePath/"
                  "Official_Presidential_Portrait_of_President_Donald_J._Trump_(2025).jpg?width=225",
         "committees": []}

_STD_LOW = [1001, 15001, 50001, 100001, 250001, 500001, 1000001, 5000001, 25000001, 50000001]
_STD_HIGH = {1001: 15000, 15001: 50000, 50001: 100000, 100001: 250000, 250001: 500000,
             500001: 1000000, 1000001: 5000000, 5000001: 25000000, 25000001: 50000000, 50000001: None}


def _dir(cache_dir):
    d = os.path.join(cache_dir or ".cache", "_congress")
    os.makedirs(d, exist_ok=True)
    return d


def _cached_json(path, url, ttl):
    try:
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl:
            return json.load(open(path))
    except Exception:  # noqa: BLE001
        pass
    try:
        import requests
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            data = r.json()
            json.dump(data, open(path, "w"))
            return data
    except Exception:  # noqa: BLE001
        pass
    try:
        return json.load(open(path))
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ members
def directory(cache_dir=None) -> list[dict]:
    """Current members of Congress: [{id, name, first, last, party, chamber,
    state, district, since, photo, committees}]."""
    d = _dir(cache_dir)
    leg = _cached_json(os.path.join(d, "legislators.json"), _LEG, 7 * 86400) or []
    memb = _cached_json(os.path.join(d, "committee_membership.json"), _COMM, 7 * 86400) or {}
    comms = _cached_json(os.path.join(d, "committees.json"), _COMMS, 30 * 86400) or []
    cname = {}
    for c in comms:
        cname[c.get("thomas_id")] = c.get("name")
    by_bio: dict = {}
    for code, members in (memb or {}).items():
        if len(code) != 4:                     # top-level committees only (subcommittees are longer)
            continue
        for m in members:
            by_bio.setdefault(m.get("bioguide"), []).append(
                {"name": cname.get(code, code), "role": m.get("title") or ""})
    out = []
    for p in leg:
        bio = (p.get("id") or {}).get("bioguide")
        terms = p.get("terms") or []
        if not bio or not terms:
            continue
        cur = terms[-1]
        nm = p.get("name") or {}
        chamber = "Senate" if cur.get("type") == "sen" else "House"
        # continuous service in the current chamber
        # unbroken service in the current chamber: walk back while each earlier
        # term ended when the next began (a gap in office starts the count over)
        since = cur.get("start")
        for t in reversed(terms[:-1]):
            if t.get("type") == cur.get("type") and (t.get("end") or "")[:7] >= (since or "")[:7] \
                    or (t.get("type") == cur.get("type") and _months_between(t.get("end"), since) <= 1):
                since = t.get("start")
            else:
                break
        out.append({"id": bio, "name": nm.get("official_full") or f"{nm.get('first', '')} {nm.get('last', '')}",
                    "first": nm.get("first", ""), "last": nm.get("last", ""), "nickname": nm.get("nickname", ""),
                    "party": cur.get("party", ""), "chamber": chamber, "state": cur.get("state", ""),
                    "district": cur.get("district"), "since": since, "first_elected": terms[0].get("start"),
                    "photo": PHOTO.format(bioguide=bio), "committees": by_bio.get(bio, [])})
    return out


def _months_between(a: str | None, b: str | None) -> int:
    try:
        ya, ma = int(a[:4]), int(a[5:7])
        yb, mb = int(b[:4]), int(b[5:7])
        return abs((yb - ya) * 12 + (mb - ma))
    except (TypeError, ValueError):
        return 99


def _norm(s: str) -> str:
    return re.sub(r"[^a-z ]", "", (s or "").lower().replace(".", " ")).strip()


def match_member(filing_name: str, chamber: str, state: str, members: list[dict]) -> dict | None:
    """The directory entry for a name as written on a filing ("Richard W.
    Allen", "A. Mitchell McConnell, Jr."), using chamber and state to break ties."""
    toks = _norm(filing_name.replace(",", " ")).split()
    toks = [t for t in toks if t not in {"jr", "sr", "ii", "iii", "hon", "dr"}]
    if not toks:
        return None
    pool = [m for m in members if m["chamber"] == chamber] or members
    st = (state or "")[:2].upper()
    cands = [m for m in pool if _norm(m["last"]).replace(" ", "") in {t for t in toks}
             or _norm(m["last"]) in " ".join(toks)]
    if st:
        cands = [m for m in cands if m["state"] == st] or cands
    if len(cands) > 1:
        firsts = {_norm(m["first"]).split()[0] if m["first"] else "" for m in cands}
        pick = [m for m in cands if (_norm(m["first"]).split() or [""])[0] in toks
                or (m.get("nickname") and _norm(m["nickname"]) in toks)]
        cands = pick or cands
        del firsts
    return cands[0] if len(cands) == 1 else (cands[0] if cands else None)


# ------------------------------------------------------------------ Trump 278-T
_YESNO = {"yes", "no", "vos", "ves", "yos", "n0", "no."}


def _std_amount(text: str):
    """Snap an OCR'd "$1 000 001 - $5 000 000" to the form's standard bands."""
    first = re.split(r"[-•:~]", text, maxsplit=1)[0]
    digits = re.sub(r"\D", "", first)
    if not digits:
        return None, None
    v = int(digits)
    if "over" in text.lower():
        return 50000001, None
    lo = min(_STD_LOW, key=lambda x: abs(x - v) / x)
    return lo, _STD_HIGH[lo]


def _parse_date(tokens: list[str], filed: str) -> str | None:
    """OCR dates lose slashes ("717/2026" = 7/7/2026); pick the reading that
    falls within the six months before the filing."""
    raw = "".join(tokens).replace("I", "1").replace("l", "1").replace("O", "0")
    m = re.search(r"(20\d\d)$", re.sub(r"[^\d/]", "", raw))
    if not m:
        return None
    year = int(m.group(1))
    head = re.sub(r"[^\d/]", "", raw)[:-4].rstrip("/")
    try:
        fd = date.fromisoformat(filed)
    except ValueError:
        fd = date.today()
    cands = []
    parts = [p for p in head.split("/") if p]
    if len(parts) == 2:
        cands.append((int(parts[0]), int(parts[1])))
    digits = head.replace("/", "")
    for i in (1, 2):
        if 0 < i < len(digits):
            cands.append((int(digits[:i]), int(digits[i:])))
    # a slash read as "1" ("7/812026" = 7/8/2026): try dropping one "1"
    for k, ch in enumerate(head):
        if ch == "1":
            alt = head[:k] + "/" + head[k + 1:]
            ps = [x for x in alt.split("/") if x]
            if len(ps) == 2:
                cands.append((int(ps[0]), int(ps[1])))
    best = None
    for mo, dy in cands:
        try:
            d = date(year, mo, dy)
        except ValueError:
            continue
        if fd - timedelta(days=200) <= d <= fd + timedelta(days=1):
            if best is None or abs((fd - d).days) < abs((fd - best).days):
                best = d
    return best.isoformat() if best else None


def parse_278t_line(line: str, filed: str) -> dict | None:
    """One transaction row of an OCR'd OGE 278-T (None for anything else)."""
    toks = line.replace("$ ", "$").replace("·", "-").replace("Ye s", "Yes").split()
    if len(toks) < 5 or not re.match(r"^[-.,']?\d{1,4}$", toks[0]):
        return None
    while toks and not re.search(r"[\dA-Za-z]", toks[-1]):      # trailing OCR junk ",. - '~"
        toks.pop()
    # the amount is the trailing run of money-ish tokens ("$1 000 001 - $5 000 000",
    # OCR sometimes reads "$" as "S"); scanning from the right skips a "$.01" par value
    i_amt = len(toks)
    while i_amt > 1 and re.fullmatch(r"[\$Ss]?[\dOoD.,]*[-•:~]?[\$Ss]?[\dOoD.,]*|[-•:~]|Over",
                                     toks[i_amt - 1]) and not (re.fullmatch(r"[A-Za-z]{2,}", toks[i_amt - 1])
                                                and not re.fullmatch(r"[OoD]+", toks[i_amt - 1])):
        i_amt -= 1
    if i_amt < len(toks) and not re.search(r"\d", toks[i_amt]) and i_amt + 1 < len(toks):
        i_amt += 1                                      # a stray "s" before the amount
    if i_amt >= len(toks) or not re.search(r"\d", " ".join(toks[i_amt:])):
        return None
    amt = re.sub(r"(?<=[\d\s$])[OoD](?=[\dOoD\s,]|$)", "0", " ".join(toks[i_amt:]))
    lo, hi = _std_amount(amt.replace("S", "$").replace("s", "$"))
    j = i_amt - 1
    # the "over 30 days" column: Yes/No, often OCR'd as "Vos", "vns", "VO$", '"""'
    skipped = 0
    while j > 0 and skipped < 2 and not re.fullmatch(r"[\dIlO/]+", toks[j]) and len(toks[j]) <= 4:
        j -= 1
        skipped += 1
    date_toks = []
    while j > 0 and re.fullmatch(r"[\dIlO/]+", toks[j]) and len(date_toks) < 3:
        date_toks.insert(0, toks[j])
        j -= 1
    if not date_toks or j <= 0:
        return None
    ttok = re.sub(r"[^a-z]", "", toks[j].lower().replace("0", "o").replace("1", "l"))
    if j > 1 and len(toks[j - 1]) == 1 and not toks[j - 1].isdigit():
        j -= 1                                   # "I Purchase", "l ourchaso"
    # OCR mangles the type word ("lourchaso", "curchasc", "salo", "sato"): closest match
    scores = {k: difflib.SequenceMatcher(None, ttok, w).ratio()
              for k, w in (("Buy", "purchase"), ("Sell", "sale"), ("Exchange", "exchange"))}
    if "urch" in ttok or "chas" in ttok:
        scores["Buy"] = 1.0
    kind = max(scores, key=scores.get)
    if scores[kind] < 0.5:
        return None
    if kind == "Sell" and "partial" in line.lower():
        kind = "Sell (partial)"
    desc = " ".join(toks[1:j]).strip(" ,.-")
    traded = _parse_date(date_toks, filed)
    if not desc or not traded:
        return None
    bond = bool(re.search(r"\bDue\b|\d+\.\d+\s*%", desc))
    return {"asset": desc, "type": kind, "traded": traded, "amount_low": lo, "amount_high": hi,
            "amount": (f"${lo:,} - ${hi:,}" if hi else f"Over ${lo - 1:,}") if lo else "",
            "asset_type": "Bond" if bond else "Stock/fund", "owner": "Self (trust-managed)"}


_SUFFIXES = {"INC", "CORP", "CO", "CL", "A", "B", "C", "PLC", "LTD", "LIMITED", "HOLDINGS", "HLDGS",
             "GROUP", "THE", "NV", "SA", "AG", "IRELAND", "NON", "VOTING", "NEW", "COM", "SHS", "ADR",
             "SPONSORED", "PAR", "01", "ORD", "COMPANY", "CORPORATION", "INCORPORATED", "LP"}


def _squash(s: str) -> str:
    toks = re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper()).split()
    toks = [t for t in toks if t not in _SUFFIXES and not re.fullmatch(r"\d+", t)]
    return "".join(toks)


def name_index(cache_dir=None) -> dict:
    """{squashed company name: ticker} from the SEC's ticker list (largest first)."""
    from .sec import _cache_dir as sec_dir
    try:
        data = json.load(open(os.path.join(sec_dir(cache_dir), "company_tickers.json")))
    except Exception:  # noqa: BLE001
        return {}
    out: dict = {}
    for k in sorted(data, key=lambda x: int(x) if str(x).isdigit() else 0):
        v = data[k]
        key = _squash(v.get("title", ""))
        if key:
            out.setdefault(key, v.get("ticker"))
    return out


def ticker_for(desc: str, index: dict) -> str | None:
    """Best-effort ticker for an OCR'd security name (exact, then close match)."""
    key = _squash(desc.replace("INC", " INC").replace("CORP", " CORP"))
    if not key:
        return None
    if key in index:
        return index[key]
    close = difflib.get_close_matches(key, index.keys(), n=1, cutoff=0.85)
    return index[close[0]] if close else None


def trump_trades(cache_dir=None, config: str = "data/trump_278t.json") -> list[dict]:
    """All rows from the listed 278-T filings (parsed once per filing, cached)."""
    try:
        filings = json.load(open(config)).get("filings", [])
    except Exception:  # noqa: BLE001
        return []
    idx = None
    out = []
    for f in filings:
        key = re.sub(r"[^A-Za-z0-9]", "", f["url"].split("/")[-1])[:60]
        path = os.path.join(_dir(cache_dir), f"oge_{f['filed']}_{key}.json")
        rows = None
        if os.path.exists(path):
            try:
                rows = json.load(open(path))
            except Exception:  # noqa: BLE001
                rows = None
        if rows is None:
            try:
                import requests
                from pypdf import PdfReader
                r = requests.get(f["url"].replace(" ", "%20"), timeout=120,
                                 headers={"User-Agent": "Mozilla/5.0 (stockskill research tool)"})
                if r.status_code != 200:
                    continue
                text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages)
                rows = [x for x in (parse_278t_line(ln, f["filed"]) for ln in text.splitlines()) if x]
                idx = idx if idx is not None else name_index(cache_dir)
                for x in rows:
                    x["ticker"] = None if x["asset_type"] == "Bond" else ticker_for(x["asset"], idx)
                json.dump(rows, open(path, "w"))
            except Exception:  # noqa: BLE001
                continue
        for x in rows:
            out.append({**x, "chamber": "President", "member": TRUMP["name"], "state": "",
                        "filed": f["filed"], "url": f["url"], "notified": None})
    return out


def trump_coverage(cache_dir=None, config: str = "data/trump_278t.json") -> dict:
    """How many of the listed 278-T filings could be read (scanned PDFs vary)."""
    try:
        filings = json.load(open(config)).get("filings", [])
    except Exception:  # noqa: BLE001
        return {"filings": 0, "read": 0}
    read = 0
    for f in filings:
        key = re.sub(r"[^A-Za-z0-9]", "", f["url"].split("/")[-1])[:60]
        try:
            if json.load(open(os.path.join(_dir(cache_dir), f"oge_{f['filed']}_{key}.json"))):
                read += 1
        except Exception:  # noqa: BLE001
            pass
    return {"filings": len(filings), "read": read}
