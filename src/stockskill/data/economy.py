"""Economic calendar and the Treasury yield curve, from official free sources.

* Release dates and times: the BLS and BEA iCalendar feeds (CPI, jobs, PPI,
  JOLTS, GDP, PCE...), the Fed's FOMC meeting calendar, and the Labor
  Department's weekly jobless-claims release (every Thursday, 8:30am ET).
* Latest readings: FRED series (the same numbers the agencies publish).
  No consensus forecasts: those are not free, so none are shown.
* Yield curve: the Treasury's daily par yield curve.

BLS and FRED ask automated clients to identify themselves, so requests carry
``SEC_USER_AGENT`` (name + email); without it those sources are skipped.
Parsers are pure (tested); fetchers cache on disk.
"""

from __future__ import annotations

import csv
import io
import os
import re
from datetime import date, datetime, timedelta

_BLS_ICS = "https://www.bls.gov/schedule/news_release/bls.ics"
_BEA_ICS = "https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics"
_FOMC = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
_TREASURY = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
             "{y}/all?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv")
_BROWSER = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")

# release title pattern -> (short name, importance 1-3, FRED series, transform, display format)
# transform: yoy (% vs a year ago), mom (% vs last period), chg (level change), level
EVENTS = [
    (r"^Consumer Price Index", "CPI inflation", 3, "CPIAUCSL", "yoy", "pct_yoy"),
    (r"^Employment Situation", "Jobs report", 3, "PAYEMS", "chg", "jobs"),
    (r"^(GDP|Gross Domestic Product)\b(?! by State)", "GDP", 3, "A191RL1Q225SBEA", "level", "pct_ann"),
    (r"^Personal Income and Outlays", "PCE inflation", 3, "PCEPILFE", "yoy", "pct_core"),
    (r"^Producer Price Index", "PPI", 2, "PPIFID", "mom", "pct_mom"),
    (r"^Job Openings and Labor Turnover", "Job openings (JOLTS)", 2, "JTSJOL", "level", "openings"),
    (r"^Employment Cost Index", "Employment cost index", 2, "ECIALLCIV", "yoy", "pct_yoy"),
    (r"^(U\.S\. )?International Trade in Goods and Services", "Trade balance", 1, "BOPGSTB", "level", "usd_m"),
    (r"^Real Earnings", "Real earnings", 1, None, None, None),
    (r"^(U\.S\. )?Import and Export Price", "Import prices", 1, None, None, None),
    (r"^Productivity and Costs", "Productivity", 1, None, None, None),
]
CLAIMS = ("Jobless claims", 2, "ICSA", "level", "claims")
FOMC = ("Fed rate decision", 3, "DFEDTARU", "level", "rate")


def display(v: float | None, fmt: str | None) -> str | None:
    """A reading as people quote it: "3.4% a year", "+162K jobs"."""
    if v is None or fmt is None:
        return None
    if fmt == "pct_yoy":
        return f"{v:.1f}% a year"
    if fmt == "pct_core":
        return f"{v:.1f}% a year (core)"
    if fmt == "pct_ann":
        return f"{v:+.1f}% annualized"
    if fmt == "pct_mom":
        return f"{v:+.1f}% a month"
    if fmt == "jobs":
        return f"{v:+,.0f}K jobs"
    if fmt == "openings":
        return f"{v / 1000:.2f}M openings"
    if fmt == "usd_m":
        return f"{'-' if v < 0 else ''}${abs(v) / 1000:,.1f}B"
    if fmt == "claims":
        return f"{v / 1000:,.0f}K claims"
    if fmt == "rate":
        return f"{v:.2f}%"
    return f"{v:,.2f}"


def period_label(iso: str, series: str | None) -> str:
    d = date.fromisoformat(iso)
    if series in ("A191RL1Q225SBEA", "ECIALLCIV"):
        return f"Q{(d.month - 1) // 3 + 1} {d.year}"
    if series == "ICSA":
        return "week to " + d.strftime("%b %-d")
    if series in ("DFEDTARU",):
        return "current"
    return d.strftime("%b %Y")


# --- pure parsing -------------------------------------------------------------

def parse_ics(text: str) -> list[dict]:
    """VEVENTs -> [{title, start (naive ET datetime or date)}]. Handles folded
    lines and TZID/UTC/all-day forms."""
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    out, cur = [], None
    for ln in lines:
        if ln == "BEGIN:VEVENT":
            cur = {}
        elif ln == "END:VEVENT" and cur is not None:
            if cur.get("title") and cur.get("start"):
                out.append(cur)
            cur = None
        elif cur is not None and ":" in ln:
            k, v = ln.split(":", 1)
            name = k.split(";")[0]
            if name == "SUMMARY":
                cur["title"] = v.replace("\\,", ",").replace("\\;", ";").strip()
            elif name == "DTSTART":
                cur["start"] = _ics_time(v.strip(), k)
    return out


def _ics_time(v: str, key: str):
    try:
        if len(v) == 8:
            return datetime.strptime(v, "%Y%m%d").date()
        if v.endswith("Z"):
            from zoneinfo import ZoneInfo
            t = datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC"))
            return t.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
        return datetime.strptime(v[:15], "%Y%m%dT%H%M%S")      # TZID given: already Eastern
    except ValueError:
        return None


def classify(title: str) -> tuple | None:
    for pat, name, imp, series, tf, unit in EVENTS:
        if re.search(pat, title, re.I):
            return name, imp, series, tf, unit
    return None


def parse_fomc(html: str) -> list[date]:
    """Decision days (the last day of each meeting) from the Fed's calendar page."""
    out = []
    months = "January|February|March|April|May|June|July|August|September|October|November|December"
    for ym in re.finditer(r"(\d{4}) FOMC Meetings(.*?)(?=\d{4} FOMC Meetings|$)", html, re.S):
        year, block = int(ym.group(1)), ym.group(2)
        for m in re.finditer(r"fomc-meeting__month[^>]*>\s*<strong>(%s)(?:/(%s))?</strong>.*?fomc-meeting__date[^>]*>(\d{1,2})(?:-(\d{1,2}))?"
                             % (months, months), block, re.S):
            mon = m.group(2) or m.group(1)          # "April/May" meetings end in May
            day = int(m.group(4) or m.group(3))
            try:
                out.append(datetime.strptime(f"{year} {mon} {day}", "%Y %B %d").date())
            except ValueError:
                pass
    return sorted(set(out))


def parse_fred(text: str) -> list[tuple[date, float]]:
    rows = []
    for r in csv.reader(io.StringIO(text)):
        if len(r) < 2 or not re.match(r"\d{4}-\d{2}-\d{2}", r[0]):
            continue
        try:
            rows.append((date.fromisoformat(r[0]), float(r[1])))
        except ValueError:
            continue
    return rows


def reading(rows: list[tuple[date, float]], tf: str) -> dict | None:
    """Latest and previous value after a transform, with the period date."""
    if not rows:
        return None

    def val(i):
        d, v = rows[i]
        if tf == "level":
            return v
        if tf == "chg":
            return v - rows[i - 1][1] if i >= 1 else None
        if tf == "mom":
            return (v / rows[i - 1][1] - 1) * 100 if i >= 1 and rows[i - 1][1] else None
        if tf == "yoy":
            target = date(d.year - 1, d.month, min(d.day, 28))
            prior = [x for x in rows[:i + 1] if x[0] <= target]
            return (v / prior[-1][1] - 1) * 100 if prior and prior[-1][1] else None
        return None
    last, prev = val(len(rows) - 1), val(len(rows) - 2) if len(rows) > 1 else None
    return {"value": last, "prev": prev, "period": rows[-1][0].isoformat()}


def parse_treasury(text: str) -> list[dict]:
    """[{date, '1 Mo': 4.01, ...}] newest first."""
    out = []
    rd = csv.DictReader(io.StringIO(text))
    for r in rd:
        try:
            d = datetime.strptime(r.pop("Date"), "%m/%d/%Y").date()
        except (KeyError, ValueError):
            continue
        row = {"date": d.isoformat()}
        for k, v in r.items():
            try:
                row[k.strip()] = float(v)
            except (TypeError, ValueError):
                pass
        out.append(row)
    return sorted(out, key=lambda x: x["date"], reverse=True)


TENORS = ["1 Mo", "2 Mo", "3 Mo", "4 Mo", "6 Mo", "1 Yr", "2 Yr", "3 Yr", "5 Yr", "7 Yr", "10 Yr", "20 Yr", "30 Yr"]


def curve_summary(rows: list[dict]) -> dict:
    """Today's curve vs 1 month and 1 year ago, and the 10y-2y / 10y-3m
    spreads over time. ``rows`` newest first."""
    if not rows:
        return {}
    now = rows[0]
    d0 = date.fromisoformat(now["date"])

    def at(days):
        t = (d0 - timedelta(days=days)).isoformat()
        return next((r for r in rows if r["date"] <= t), None)
    snaps = {"now": now, "1m": at(30), "1y": at(365)}
    curves = {k: {"date": r["date"], "y": [r.get(t) for t in TENORS]} for k, r in snaps.items() if r}
    spread = [{"date": r["date"], "s10_2": _sub(r.get("10 Yr"), r.get("2 Yr")), "s10_3m": _sub(r.get("10 Yr"), r.get("3 Mo"))}
              for r in reversed(rows)]
    key = {}
    for t in ("3 Mo", "2 Yr", "10 Yr", "30 Yr"):
        key[t] = {"now": now.get(t), "1w": _sub(now.get(t), (at(7) or {}).get(t)),
                  "1m": _sub(now.get(t), (snaps["1m"] or {}).get(t)), "1y": _sub(now.get(t), (snaps["1y"] or {}).get(t))}
    return {"tenors": TENORS, "curves": curves, "spread": spread, "key": key}


def _sub(a, b):
    return round(a - b, 3) if a is not None and b is not None else None


def weekly_claims(start: date, end: date) -> list[date]:
    d = start + timedelta(days=(3 - start.weekday()) % 7)      # next Thursday
    out = []
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out


# --- fetching -----------------------------------------------------------------

def _ua() -> str | None:
    return (os.environ.get("SEC_USER_AGENT") or "").strip().strip('"') or None


def _get(url: str, contact: bool) -> str | None:
    ua = _ua() if contact else _BROWSER
    if not ua:
        return None
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": ua}, timeout=30)
        return r.text if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None


def _cached_text(cache_dir, name: str, ttl: float, fetch) -> str | None:
    import time
    d = os.path.join(cache_dir or ".cache", "_econ")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < ttl:
        return open(p).read()
    txt = fetch()
    if txt:
        with open(p, "w") as f:
            f.write(txt)
        return txt
    return open(p).read() if os.path.exists(p) else None


def fred(series: str, cache_dir) -> list[tuple[date, float]]:
    return parse_fred(_cached_text(cache_dir, f"fred_{series}.csv", 6 * 3600,
                                   lambda: _get(_FRED.format(series), True)) or "")


def calendar(cache_dir, days_back: int = 7, days_ahead: int = 35) -> list[dict]:
    """Releases from a week ago to five weeks ahead, oldest first."""
    today = date.today()
    lo, hi = today - timedelta(days=days_back), today + timedelta(days=days_ahead)
    events = []
    for src, url, contact in (("BLS", _BLS_ICS, True), ("BEA", _BEA_ICS, False)):
        txt = _cached_text(cache_dir, f"{src.lower()}.ics", 12 * 3600, lambda u=url, c=contact: _get(u, c))
        for ev in parse_ics(txt or ""):
            st = ev["start"]
            d = st.date() if isinstance(st, datetime) else st
            if not (lo <= d <= hi):
                continue
            c = classify(ev["title"])
            name, imp, series, tf, fmt = c if c else (ev["title"], 1, None, None, None)
            events.append({"date": d.isoformat(), "time": st.strftime("%H:%M") if isinstance(st, datetime) else None,
                           "name": name, "title": ev["title"], "importance": imp, "source": src,
                           "series": series, "tf": tf, "fmt": fmt})
    fomc_html = _cached_text(cache_dir, "fomc.html", 7 * 86400, lambda: _get(_FOMC, False))
    fomc_days = parse_fomc(fomc_html or "")
    if not fomc_days:
        from .macro import FOMC_2026
        fomc_days = [date.fromisoformat(x) for x in FOMC_2026]
    for d in fomc_days:
        if lo <= d <= hi:
            events.append({"date": d.isoformat(), "time": "14:00", "name": FOMC[0], "title": "FOMC statement and rate decision",
                           "importance": FOMC[1], "source": "Fed", "series": FOMC[2], "tf": FOMC[3], "fmt": FOMC[4]})
    for d in weekly_claims(lo, hi):
        events.append({"date": d.isoformat(), "time": "08:30", "name": CLAIMS[0], "title": "Unemployment Insurance Weekly Claims",
                       "importance": CLAIMS[1], "source": "DOL", "series": CLAIMS[2], "tf": CLAIMS[3], "fmt": CLAIMS[4]})
    # the latest reading for each indicator (one FRED download per series)
    cache: dict = {}
    for e in events:
        s, tf, fmt = e.pop("series"), e.pop("tf"), e.pop("fmt")
        if s and s not in cache:
            cache[s] = reading(fred(s, cache_dir), tf)
        r = cache.get(s) if s else None
        e["last"] = None
        if r and r.get("value") is not None:
            e["last"] = {"text": display(r["value"], fmt), "prev": display(r.get("prev"), fmt),
                         "period": period_label(r["period"], s)}
            if s == "DFEDTARU":                                   # show the target range
                lo_ = reading(fred("DFEDTARL", cache_dir), "level")
                if lo_ and lo_.get("value") is not None:
                    e["last"] = {"text": f"{lo_['value']:.2f}% to {r['value']:.2f}%", "prev": None, "period": "current target"}
    events.sort(key=lambda e: (e["date"], e["time"] or "99", -e["importance"]))
    return events


def yield_curve(cache_dir) -> dict:
    y = date.today().year
    rows = []
    for yr, ttl in ((y, 6 * 3600), (y - 1, 30 * 86400), (y - 2, 30 * 86400)):
        txt = _cached_text(cache_dir, f"treasury_{yr}.csv", ttl, lambda yr=yr: _get(_TREASURY.format(y=yr), False))
        rows += parse_treasury(txt or "")
    rows.sort(key=lambda r: r["date"], reverse=True)
    return curve_summary(rows)
