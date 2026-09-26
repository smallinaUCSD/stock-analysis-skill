"""Stock trades by members of Congress (STOCK Act periodic transaction reports).

Official, free sources:
* House: the Clerk's yearly index (a zip of XML) lists every filing; each
  periodic transaction report (PTR) is a PDF. Electronically filed PDFs carry
  text we can parse; scanned paper filings don't and are skipped.
* Senate: the eFD search site returns filings as JSON after accepting its
  terms, and each electronic PTR is an HTML table.

Members must report within 45 days, amounts are ranges, and research finds no
market-beating returns on average after the STOCK Act (Belmont, Sacerdote,
Sehgal & Van Hoek, 2022, Journal of Public Economics). Note: federal law bars
using these reports for commercial purposes (other than news media).

The parsers are pure and tested; fetching is cached on disk and polite.
"""

from __future__ import annotations

import io
import json
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timedelta

_UA = "Mozilla/5.0 (Macintosh; stockskill research tool)"
_HOUSE_ZIP = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{y}FD.zip"
_HOUSE_PDF = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{y}/{doc}.pdf"
_SENATE = "https://efdsearch.senate.gov"

_TX_TYPES = {"P": "Buy", "S": "Sell", "S (partial)": "Sell (partial)", "E": "Exchange",
             "Purchase": "Buy", "Sale (Full)": "Sell", "Sale (Partial)": "Sell (partial)",
             "Exchange": "Exchange", "Sale": "Sell"}
_OWNERS = {"SP": "Spouse", "JT": "Joint", "DC": "Child", "": "Self", "Self": "Self"}


def _amount_range(text: str):
    """"$1,001 - $15,000" -> (1001, 15000); "Over $50,000,000" -> (50000000, None)."""
    nums = [int(x.replace(",", "")) for x in re.findall(r"\$([\d,]+)", text or "")]
    if not nums:
        return None, None
    if (text or "").strip().lower().startswith("over"):
        return nums[0], None
    return nums[0], (nums[1] if len(nums) > 1 else nums[0])


def _mdy(s: str) -> str | None:
    try:
        return datetime.strptime(s.strip(), "%m/%d/%Y").date().isoformat()
    except (ValueError, AttributeError):
        return None


# one transaction in a House PTR's extracted text, after its lines are joined:
#   [owner] <asset ...> [ST] P 08/12/2026 09/15/2026 $1,001 - $15,000
_HOUSE_TX = re.compile(
    r"(?:(?P<owner>SP|JT|DC)\s+)?(?P<asset>.+?)\s*\[(?P<atype>[A-Z]{2})\]\s+"
    r"(?P<tx>P|S \(partial\)|S|E)\s+(?P<d1>\d{2}/\d{2}/\d{4})\s+(?P<d2>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<amt>(?:Over\s+)?\$[\d,]+(?:\s*-\s*\$[\d,]+)?)")
# the PDFs' field labels ("Filing Status:", "Subholding Of:") lose their glyphs:
# a capital letter, runs of spaces, then a colon
_LABEL_LINE = re.compile(r"^\s*[A-Z](?:\s{2,}[A-Za-z]?)+\s*:")


def parse_house_ptr_text(text: str) -> list[dict]:
    """Transactions from the extracted text of an electronic House PTR."""
    lines = (text or "").replace("\x00", " ").splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip().startswith("$200?")) + 1
    except StopIteration:
        start = 0
    body = []
    for ln in lines[start:]:
        if ln.startswith("* For the complete list") or ln.startswith("I          V"):
            break
        if _LABEL_LINE.match(ln):
            body.append("\n")                  # a label line ends the previous transaction
            continue
        body.append(ln.strip())
    joined = " ".join(body)
    out = []
    for chunk in joined.split("\n"):
        for m in _HOUSE_TX.finditer(" ".join(chunk.split())):
            asset = m.group("asset").strip()
            tk = re.search(r"\(([A-Z][A-Z.\-]{0,5})\)", asset)
            lo, hi = _amount_range(m.group("amt"))
            out.append({"owner": _OWNERS.get(m.group("owner") or "", "Self"),
                        "asset": re.sub(r"\s*\([A-Z.\-]{1,6}\)\s*$", "", asset),
                        "ticker": tk.group(1) if tk else None,
                        "asset_type": m.group("atype"),
                        "type": _TX_TYPES.get(m.group("tx"), m.group("tx")),
                        "traded": _mdy(m.group("d1")), "notified": _mdy(m.group("d2")),
                        "amount": m.group("amt").replace("  ", " "), "amount_low": lo, "amount_high": hi})
    return out


def parse_senate_ptr_html(html_text: str) -> list[dict]:
    """Transactions from an electronic Senate PTR page (an HTML table)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_text or "", "lxml")
    tbl = soup.find("table")
    if tbl is None or tbl.find("tbody") is None:
        return []
    heads = [th.get_text(" ", strip=True).lower() for th in tbl.find_all("th")]
    out = []
    for tr in tbl.find("tbody").find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        row = dict(zip(heads, cells))
        tk = row.get("ticker", "")
        lo, hi = _amount_range(row.get("amount", ""))
        out.append({"owner": row.get("owner") or "Self",
                    "asset": row.get("asset name", ""),
                    "ticker": tk if re.fullmatch(r"[A-Z][A-Z.\-]{0,5}", tk or "") else None,
                    "asset_type": row.get("asset type", ""),
                    "type": _TX_TYPES.get(row.get("type", ""), row.get("type", "")),
                    "traded": _mdy(row.get("transaction date", "")), "notified": None,
                    "amount": row.get("amount", ""), "amount_low": lo, "amount_high": hi})
    return out


def parse_house_index(xml_bytes: bytes) -> list[dict]:
    """PTR filings from the Clerk's yearly XML index."""
    root = ET.fromstring(xml_bytes)
    out = []
    for m in root.findall("Member"):
        if (m.findtext("FilingType") or "") != "P":
            continue
        first, last = (m.findtext("First") or "").strip(), (m.findtext("Last") or "").strip()
        out.append({"chamber": "House", "member": f"{first} {last}".strip(),
                    "state": (m.findtext("StateDst") or "").strip(),
                    "filed": _mdy(m.findtext("FilingDate") or ""), "doc": (m.findtext("DocID") or "").strip(),
                    "year": (m.findtext("Year") or "").strip()})
    return out


# ------------------------------------------------------------------ fetching
_LOCK = threading.Lock()
_STATE: dict = {"loading": False, "error": None}


def _dir(cache_dir):
    d = os.path.join(cache_dir or ".cache", "_congress")
    os.makedirs(d, exist_ok=True)
    return d


def _http():
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = _UA
    return s


def _house(days: int, cache_dir, s) -> list[dict]:
    today = date.today()
    filings = []
    for y in sorted({today.year, (today - timedelta(days=days)).year}):
        r = s.get(_HOUSE_ZIP.format(y=y), timeout=30)
        if r.status_code != 200:
            continue
        z = zipfile.ZipFile(io.BytesIO(r.content))
        xml_name = next((n for n in z.namelist() if n.endswith(".xml")), None)
        if xml_name:
            filings += parse_house_index(z.read(xml_name))
    since = (today - timedelta(days=days)).isoformat()
    filings = [f for f in filings if (f["filed"] or "") >= since]
    trades = []
    for f in filings:
        path = os.path.join(_dir(cache_dir), f"house_{f['doc']}.json")
        rows = None
        if os.path.exists(path):
            try:
                rows = json.load(open(path))
            except Exception:  # noqa: BLE001
                rows = None
        if rows is None:
            try:
                from pypdf import PdfReader
                time.sleep(0.2)
                pr = s.get(_HOUSE_PDF.format(y=f["year"], doc=f["doc"]), timeout=30)
                text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pr.content)).pages) \
                    if pr.status_code == 200 else ""
                rows = parse_house_ptr_text(text)
                json.dump(rows, open(path, "w"))
            except Exception:  # noqa: BLE001
                continue
        url = _HOUSE_PDF.format(y=f["year"], doc=f["doc"])
        for t in rows:
            trades.append({**t, "chamber": "House", "member": f["member"], "state": f["state"],
                           "filed": f["filed"], "url": url})
    return trades


def _senate(days: int, cache_dir, s) -> list[dict]:
    r = s.get(f"{_SENATE}/search/home/", timeout=20)
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text or "")
    if not tok:
        return []
    s.post(f"{_SENATE}/search/home/", data={"prohibition_agreement": "1", "csrfmiddlewaretoken": tok.group(1)},
           headers={"Referer": f"{_SENATE}/search/home/"}, timeout=20)
    csrf = s.cookies.get("csrftoken")
    since = (date.today() - timedelta(days=days)).strftime("%m/%d/%Y")
    reports, start = [], 0
    while True:
        data = {"start": str(start), "length": "100", "report_types": "[11]", "filer_types": "[]",
                "submitted_start_date": f"{since} 00:00:00", "submitted_end_date": "",
                "candidate_state": "", "senator_state": "", "office_id": "",
                "first_name": "", "last_name": "", "csrfmiddlewaretoken": csrf}
        j = s.post(f"{_SENATE}/search/report/data/", data=data,
                   headers={"Referer": f"{_SENATE}/search/", "X-CSRFToken": csrf}, timeout=20).json()
        rows = j.get("data") or []
        reports += rows
        start += 100
        if start >= (j.get("recordsFiltered") or 0) or not rows:
            break
    trades = []
    for first, last, _full, link, filed in reports:
        m = re.search(r'href="(/search/view/ptr/([0-9a-f\-]+)/)"', link)
        if not m:                                    # paper filings: scanned images, skipped
            continue
        path = os.path.join(_dir(cache_dir), f"senate_{m.group(2)}.json")
        rows = None
        if os.path.exists(path):
            try:
                rows = json.load(open(path))
            except Exception:  # noqa: BLE001
                rows = None
        if rows is None:
            time.sleep(0.2)
            pr = s.get(_SENATE + m.group(1), timeout=20)
            rows = parse_senate_ptr_html(pr.text) if pr.status_code == 200 else []
            json.dump(rows, open(path, "w"))
        name = f"{first} {last}".replace(", Jr.", " Jr.").strip()
        for t in rows:
            trades.append({**t, "chamber": "Senate", "member": name, "state": "",
                           "filed": _mdy(filed), "url": _SENATE + m.group(1)})
    return trades


def _refresh(days: int, cache_dir) -> None:
    import sys
    errors = []
    try:
        s = _http()
        trades = []
        for fn in (_house, _senate):
            try:
                trades += fn(days, cache_dir, s)
            except Exception as e:  # noqa: BLE001 - one chamber failing keeps the other
                errors.append(f"{fn.__name__.strip('_')}: {e}")
        congress = len(trades)
        try:                                     # the President's OGE 278-T reports
            from .politicians import trump_trades
            trades += trump_trades(cache_dir)
        except Exception as e:  # noqa: BLE001
            errors.append(f"president: {e}")
        if errors:
            print(f"congress refresh: {'; '.join(errors)}", file=sys.stderr, flush=True)
        if not congress:
            # nothing from either chamber (offline, blocked, site change): keep
            # whatever we had and try again on the next request
            _STATE["error"] = "; ".join(errors) or "no House or Senate filings were returned"
            _STATE["retry_after"] = time.time() + 300
            return
        trades.sort(key=lambda t: (t.get("filed") or "", t.get("traded") or ""), reverse=True)
        path = os.path.join(_dir(cache_dir), "trades.json")
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump({"as_of": datetime.now().isoformat(timespec="minutes"), "days": days,
                       "trades": trades}, f)
        os.replace(tmp, path)
        _STATE["error"] = "; ".join(errors) or None
    except Exception as e:  # noqa: BLE001
        _STATE["error"] = str(e)
        _STATE["retry_after"] = time.time() + 300
        print(f"congress refresh failed: {e}", file=sys.stderr, flush=True)
    finally:
        _STATE["loading"] = False


_PARSED: dict[str, tuple[float, dict]] = {}     # trades.json is several MB: parse once per change


def recent_trades(cache_dir=None, days: int = 730, max_age: float = 6 * 3600) -> dict:
    """{"trades": [...], "as_of", "loading"}: the cached set, refreshed in the
    background when older than ``max_age`` (the first build takes a minute)."""
    path = os.path.join(_dir(cache_dir), "trades.json")
    data = None
    try:
        mt = os.path.getmtime(path)
        hit = _PARSED.get(path)
        if hit and hit[0] == mt:                    # parsed copy still matches the file
            data = hit[1]
        else:
            data = json.load(open(path))
            _PARSED[path] = (mt, data)
    except Exception:  # noqa: BLE001
        data = None
    stale = (data is None or time.time() - os.path.getmtime(path) > max_age
             or (data.get("days") or 0) < days)          # the window was widened
    with _LOCK:
        if stale and not _STATE["loading"] and time.time() >= _STATE.get("retry_after", 0):
            _STATE["loading"] = True
            threading.Thread(target=_refresh, args=(days, cache_dir), daemon=True).start()
    return {**(data or {"trades": []}), "loading": _STATE["loading"], "error": _STATE["error"]}
