"""Earnings: past report dates and the stock's reaction, EPS surprises, the
next report with consensus estimates, and analyst recommendation trends.

* Report dates and times come from SEC 8-K filings with Item 2.02 ("Results
  of Operations"), which companies file as they release results. The filing's
  acceptance time says whether results came before the open or after the close,
  and so which trading day's move was the reaction.
* EPS estimates and surprises (last four quarters), the upcoming date and
  recommendation trends come from Finnhub's free tier.

``release_timing``, ``reaction`` and ``dedupe_releases`` are pure (tested).
"""

from __future__ import annotations

import bisect
import os
from datetime import date, datetime, time, timedelta

_OPEN, _CLOSE = time(9, 30), time(16, 0)


def release_timing(accepted: str) -> tuple[date, str] | None:
    """SEC acceptance timestamp (UTC) -> (date in New York, "pre"|"during"|"post")."""
    try:
        from zoneinfo import ZoneInfo
        t = datetime.fromisoformat(accepted.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
    except (ValueError, AttributeError):
        return None
    tt = t.time()
    return t.date(), ("pre" if tt < _OPEN else "post" if tt >= _CLOSE else "during")


def dedupe_releases(rows: list[dict], gap_days: int = 20) -> list[dict]:
    """Keep one release per quarter: a second Item 2.02 filing within
    ``gap_days`` of another (a correction, a preliminary) is dropped in favour
    of the earlier one. Rows newest first."""
    out: list[dict] = []
    for r in sorted(rows, key=lambda x: x["date"]):
        if out and (r["date"] - out[-1]["date"]).days < gap_days:
            continue
        out.append(r)
    return out[::-1]


def reaction(dates: list[date], closes: list[float], d: date, timing: str) -> dict | None:
    """The one-day price move that reacted to a release on ``d``: after the
    close -> next session vs that day's close; otherwise that session vs the
    prior close. A release on a non-trading day reacts on the next session."""
    i = bisect.bisect_left(dates, d)
    if i >= len(dates):
        return None
    if timing == "post" and dates[i] == d:
        a, b = i, i + 1
    else:
        a, b = i - 1, i
    if a < 0 or b >= len(dates) or not closes[a]:
        return None
    return {"move": closes[b] / closes[a] - 1, "day": dates[b].isoformat()}


def releases(ticker: str, cache_dir: str | None = None) -> list[dict] | None:
    """[{date, timing, accepted}] newest first, from SEC 8-K Item 2.02 filings."""
    from . import sec as SEC
    cik = SEC.cik_for(ticker, cache_dir)
    if not cik:
        return None

    def pick(r):
        return [{"accepted": r["acceptanceDateTime"][i], "filed": r["filingDate"][i],
                 "acc": r["accessionNumber"][i]}
                for i, f in enumerate(r["form"]) if f in ("8-K", "8-K/A") and "2.02" in (r["items"][i] or "")]

    def fetch():
        s = SEC._get_json(f"{SEC._BASE_DATA}/submissions/CIK{cik:010d}.json")
        if not s:
            return None
        out = pick(s["filings"]["recent"])
        if len(out) < 12:
            # heavy filers (banks issuing thousands of notes a year) push older
            # 8-Ks off the recent list; full-text search finds them (date only)
            have = {x["acc"] for x in out}
            start = (date.today() - timedelta(days=4 * 365)).isoformat()
            j = SEC._get_json("https://efts.sec.gov/LATEST/search-index?q=%22results%20of%20operations%22"
                              f"&forms=8-K&ciks={cik:010d}&dateRange=custom&startdt={start}"
                              f"&enddt={date.today().isoformat()}")   # the range is ignored without enddt
            for h in ((j or {}).get("hits") or {}).get("hits") or []:
                src = h.get("_source") or {}
                acc = src.get("adsh")
                if acc and acc not in have and "2.02" in (src.get("items") or []) and src.get("file_date"):
                    out.append({"accepted": None, "filed": src["file_date"], "acc": acc})
                    have.add(acc)
        return out

    raw = SEC._cached(os.path.join(SEC._cache_dir(cache_dir), f"rel_{cik}.json"), 86400, fetch)
    if raw is None:
        return None
    rows = []
    for x in raw:
        rt = release_timing(x["accepted"]) if x.get("accepted") else None
        if rt is None and x.get("filed"):
            rt = (date.fromisoformat(x["filed"]), None)
        if rt:
            rows.append({"date": rt[0], "timing": rt[1], "accepted": x.get("accepted"),
                         "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{x['acc'].replace('-', '')}/"})
    known = [r["timing"] for r in rows if r["timing"]]
    usual = max(set(known), key=known.count) if known else "pre"
    for r in rows:
        if r["timing"] is None:
            r["timing"], r["timing_inferred"] = usual, True
    return dedupe_releases(rows)


_HOUR = {"bmo": "pre", "amc": "post", "dmh": "during"}


def upcoming(ticker: str) -> dict | None:
    """Next scheduled report {date, timing, eps_est, rev_est, quarter, year}."""
    from . import finnhub
    today = date.today()
    j = finnhub._get("/calendar/earnings", symbol=ticker,
                     **{"from": str(today), "to": str(today + timedelta(days=150))})
    rows = [r for r in ((j or {}).get("earningsCalendar") or []) if r.get("date")]
    if not rows:
        return None
    r = min(rows, key=lambda x: x["date"])
    return {"date": r["date"], "timing": _HOUR.get(r.get("hour") or ""), "eps_est": r.get("epsEstimate"),
            "rev_est": r.get("revenueEstimate"), "quarter": r.get("quarter"), "year": r.get("year")}


def surprises(ticker: str) -> list[dict]:
    """Last four quarters (free tier) newest first: estimate, actual, surprise."""
    from . import finnhub
    j = finnhub._get("/stock/earnings", symbol=ticker)
    out = []
    for r in j or []:
        if r.get("actual") is None:
            continue
        out.append({"quarter": r.get("quarter"), "year": r.get("year"), "estimate": r.get("estimate"),
                    "actual": r.get("actual"), "surprise_pct": r.get("surprisePercent")})
    return out


def recommendations(ticker: str, months: int = 6) -> list[dict]:
    """Monthly analyst rating counts, oldest first."""
    from . import finnhub
    j = finnhub._get("/stock/recommendation", symbol=ticker)
    rows = [{"period": r["period"], "strong_buy": r.get("strongBuy", 0), "buy": r.get("buy", 0),
             "hold": r.get("hold", 0), "sell": r.get("sell", 0), "strong_sell": r.get("strongSell", 0)}
            for r in (j or []) if r.get("period")]
    return sorted(rows, key=lambda r: r["period"])[-months:]


def history(rel: list[dict], ohlcv: dict | None, spy: dict | None, surp: list[dict], n: int = 12) -> list[dict]:
    """Past releases (newest first) with the stock's and the market's reaction.
    The latest four carry Finnhub's EPS surprise, matched newest-to-newest."""
    today = date.today()
    past = [r for r in rel if r["date"] <= today][:n]
    out = []
    for k, r in enumerate(past):
        row = {"date": r["date"].isoformat(), "timing": r["timing"], "url": r.get("url")}
        if ohlcv:
            rx = reaction(ohlcv["dates"], ohlcv["close"], r["date"], r["timing"])
            if rx:
                row.update(move=rx["move"], day=rx["day"])
                if spy:
                    m = reaction(spy["dates"], spy["close"], r["date"], r["timing"])
                    row["market"] = m["move"] if m and m["day"] == rx["day"] else None
        if k < len(surp):
            row.update({f"eps_{x}": surp[k][y] for x, y in (("est", "estimate"), ("act", "actual"),
                                                            ("surprise", "surprise_pct"))})
            row["fq"] = f"Q{surp[k]['quarter']} FY{surp[k]['year']}"
        out.append(row)
    return out


def stats(hist: list[dict], surp: list[dict]) -> dict:
    moves = [h["move"] for h in hist if h.get("move") is not None]
    beats = [s for s in surp if s.get("actual") is not None and s.get("estimate") is not None]
    return {
        "n": len(moves),
        "avg_abs_move": sum(abs(m) for m in moves) / len(moves) if moves else None,
        "up": sum(1 for m in moves if m > 0),
        "max_move": max(moves, key=abs) if moves else None,
        "beats": sum(1 for s in beats if s["actual"] > s["estimate"]),
        "beat_n": len(beats),
    }


def calendar(tickers: list[str], days: int = 30) -> list[dict]:
    """Upcoming reports for ``tickers`` in the next ``days``. Finnhub caps a
    response at 1,500 rows (dropping the earliest dates), so ask a week at a time."""
    from . import finnhub
    today = date.today()
    rows: list[dict] = []
    for start in range(0, days + 1, 7):
        a, b = today + timedelta(days=start), today + timedelta(days=min(start + 6, days))
        j = finnhub._get("/calendar/earnings", **{"from": str(a), "to": str(b)})
        rows += (j or {}).get("earningsCalendar") or []
    want = {t.upper() for t in tickers}
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: (x.get("date") or "", x.get("symbol") or "")):
        s = (r.get("symbol") or "").upper()
        if s in want and s not in seen:
            seen.add(s)
            out.append({"ticker": s, "date": r["date"], "timing": _HOUR.get(r.get("hour") or ""),
                        "eps_est": r.get("epsEstimate"), "rev_est": r.get("revenueEstimate"),
                        "quarter": r.get("quarter"), "year": r.get("year")})
    return out
