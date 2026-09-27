"""Market calendar: exchange holidays and early closes, monthly options
expiration, and one merged list of dated events for a person (their
watchlist's earnings, economic releases, Fed decisions, IPOs).

Holidays follow NYSE's published schedule; extend the tables each year.
"""

from __future__ import annotations

import time
from datetime import date, timedelta

# NYSE full-day closures
HOLIDAYS = {
    "2026-01-01": "New Year's Day", "2026-01-19": "Martin Luther King Jr. Day", "2026-02-16": "Presidents' Day",
    "2026-04-03": "Good Friday", "2026-05-25": "Memorial Day", "2026-06-19": "Juneteenth",
    "2026-07-03": "Independence Day (observed)", "2026-09-07": "Labor Day", "2026-11-26": "Thanksgiving Day",
    "2026-12-25": "Christmas Day",
    "2027-01-01": "New Year's Day", "2027-01-18": "Martin Luther King Jr. Day", "2027-02-15": "Presidents' Day",
    "2027-03-26": "Good Friday", "2027-05-31": "Memorial Day", "2027-06-18": "Juneteenth (observed)",
    "2027-07-05": "Independence Day (observed)", "2027-09-06": "Labor Day", "2027-11-25": "Thanksgiving Day",
    "2027-12-24": "Christmas Day (observed)",
}
# 1:00 pm ET closes
EARLY_CLOSES = {"2026-11-27": "Day after Thanksgiving", "2026-12-24": "Christmas Eve",
                "2027-11-26": "Day after Thanksgiving"}


def is_holiday(d: date) -> str | None:
    return HOLIDAYS.get(d.isoformat())


def early_close(d: date) -> str | None:
    return EARLY_CLOSES.get(d.isoformat())


def monthly_expirations(start: date, end: date) -> list[tuple[date, bool]]:
    """(date, quarterly) for standard monthly options expiration: the third
    Friday, or the Thursday before when that Friday is a holiday. Quarterly
    months (Mar, Jun, Sep, Dec) are the "triple witching" days."""
    out = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        first = date(y, m, 1)
        d = first + timedelta(days=(4 - first.weekday()) % 7 + 14)      # third Friday
        if is_holiday(d):
            d -= timedelta(days=1)
        if start <= d <= end:
            out.append((d, m in (3, 6, 9, 12)))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def events(watchlist: list[str], start: date, end: date, earnings: list[dict], econ: list[dict],
           ipos: list[dict]) -> list[dict]:
    """One list, oldest first: {date, time, kind, title, detail, ticker, url, importance}.
    ``earnings``/``econ``/``ipos`` come from the data modules (passed in, so this is pure)."""
    mine = {t.upper() for t in watchlist}
    out: list[dict] = []
    wmap = {"pre": "before the open", "post": "after the close", "during": "during the day"}
    for e in earnings:
        if e.get("ticker") in mine and start.isoformat() <= e.get("date", "") <= end.isoformat():
            est = e.get("eps_est")
            out.append({"date": e["date"], "time": {"pre": "08:00", "post": "16:05"}.get(e.get("timing") or ""),
                        "kind": "earnings", "ticker": e["ticker"], "importance": 3,
                        "title": f"{e['ticker']} earnings", "url": f"/earnings?t={e['ticker']}",
                        "detail": " · ".join(x for x in (wmap.get(e.get("timing") or "", ""),
                                                        f"EPS estimate ${est:.2f}" if isinstance(est, (int, float)) else "") if x)})
    for e in econ:
        if not (start.isoformat() <= e.get("date", "") <= end.isoformat()) or (e.get("importance") or 0) < 2:
            continue
        fed = e.get("source") == "Fed"
        last = e.get("last") or {}
        out.append({"date": e["date"], "time": e.get("time"), "kind": "fed" if fed else "economy",
                    "title": e.get("name") or e.get("title"), "importance": e.get("importance") or 2,
                    "url": "/economy", "detail": (f"last: {last['text']}" + (f" ({last['period']})" if last.get("period") else ""))
                    if last.get("text") else (e.get("title") or "")})
    for r in ipos:
        if start.isoformat() <= (r.get("date") or "") <= end.isoformat():
            rng = ("" if r.get("low") is None else f"${r['low']:,.2f}" if r.get("low") == r.get("high")
                   else f"${r['low']:,.2f}-{r['high']:,.2f}")
            out.append({"date": r["date"], "time": None, "kind": "ipo", "ticker": r.get("symbol"), "importance": 1,
                        "title": f"IPO: {r.get('name') or r.get('symbol')}", "url": "/ipos",
                        "detail": " · ".join(x for x in (r.get("symbol") or "", rng, r.get("exchange") or "") if x)})
    d = start
    while d <= end:
        if is_holiday(d):
            out.append({"date": d.isoformat(), "time": None, "kind": "market", "importance": 3,
                        "title": "Market closed", "detail": is_holiday(d)})
        elif early_close(d):
            out.append({"date": d.isoformat(), "time": "13:00", "kind": "market", "importance": 2,
                        "title": "Market closes early (1:00 pm ET)", "detail": early_close(d)})
        d += timedelta(days=1)
    for d, q in monthly_expirations(start, end):
        out.append({"date": d.isoformat(), "time": "16:00", "kind": "options", "importance": 2 if q else 1,
                    "title": "Quarterly options expiration (triple witching)" if q else "Monthly options expiration",
                    "detail": "Stock options, index options and futures expire" if q else "Standard monthly options expire"})
    out.sort(key=lambda e: (e["date"], e.get("time") or "99", -e["importance"]))
    return out


_EARN: dict = {}


def market_earnings(days: int = 90) -> list[dict]:
    """Every company's upcoming reports (Finnhub), cached 6 hours for all users."""
    key = (date.today().isoformat(), days)
    hit = _EARN.get(key)
    if hit and time.time() - hit[0] < 6 * 3600:
        return hit[1]
    from . import finnhub
    from .earnings import _HOUR
    from concurrent.futures import ThreadPoolExecutor
    today = date.today()

    def week(s):                              # Finnhub caps a reply at 1,500 rows: a week at a time
        a, b = today + timedelta(days=s), today + timedelta(days=min(s + 6, days))
        j = finnhub._get("/calendar/earnings", **{"from": str(a), "to": str(b)})
        return (j or {}).get("earningsCalendar") or []
    with ThreadPoolExecutor(max_workers=6) as ex:
        rows = [r for part in ex.map(week, range(0, days + 1, 7)) for r in part]
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: (x.get("date") or "", x.get("symbol") or "")):
        s = (r.get("symbol") or "").upper()
        if s and s not in seen and r.get("date"):
            seen.add(s)
            out.append({"ticker": s, "date": r["date"], "timing": _HOUR.get(r.get("hour") or ""),
                        "eps_est": r.get("epsEstimate")})
    if out:
        _EARN.clear()
        _EARN[key] = (time.time(), out)
    return out


def to_ics(evts: list[dict], name: str = "SM Investments") -> str:
    """The events as an iCalendar file (all-day, or timed in New York time)."""
    def esc(s):
        return str(s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SM Investments//Calendar//EN", f"X-WR-CALNAME:{esc(name)}",
             "CALSCALE:GREGORIAN"]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    for i, e in enumerate(evts):
        d = e["date"].replace("-", "")
        lines += ["BEGIN:VEVENT", f"UID:{d}-{e['kind']}-{i}@sminvestments", f"DTSTAMP:{stamp}"]
        if e.get("time"):
            hh, mm = e["time"].split(":")
            lines.append(f"DTSTART;TZID=America/New_York:{d}T{hh}{mm}00")
            lines.append(f"DURATION:PT30M")
        else:
            nxt = (date.fromisoformat(e["date"]) + timedelta(days=1)).strftime("%Y%m%d")
            lines += [f"DTSTART;VALUE=DATE:{d}", f"DTEND;VALUE=DATE:{nxt}"]
        lines += [f"SUMMARY:{esc(e['title'])}", f"DESCRIPTION:{esc(e.get('detail'))}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
