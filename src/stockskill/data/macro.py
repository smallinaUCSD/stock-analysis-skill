"""Macro / market-event alerts.

Two sources, both cheap and honest:

* **Scheduled** — the 2026 FOMC decision dates (Fed policy announcements) are a
  fixed, published calendar; we surface a countdown to the next one. (CPI / jobs
  release dates aren't hardcoded — their exact days need the BLS schedule — so we
  let the news scan catch them when they're topical instead of guessing a date.)
* **Event-driven** — a keyword scan over recent market-news headlines flags
  layoffs, Fed news, jobs/inflation prints, tariffs, etc. Pure given the titles.

Nothing here forecasts; it reports a known date and matches text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# FOMC statement is released on the SECOND day of each meeting (14:00 ET).
# Verified against the Fed's published 2026 schedule.
FOMC_2026 = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]

# headline keyword -> (kind, emoji). Checked against a lowercased title.
_KEYWORDS: list[tuple[tuple[str, ...], str, str]] = [
    (("layoff", "job cut", "jobs cut", "cuts jobs", "cutting jobs",
      "workforce reduction", "slash jobs", "slashing jobs"), "layoffs", "⚠️"),
    (("fomc", "federal reserve", "fed rate", "rate cut", "rate hike",
      "interest rate", "powell", "fed decision", "fed holds", "fed cuts"), "fed", "🏛️"),
    (("jobs report", "nonfarm", "payroll", "unemployment rate",
      "employment situation"), "jobs", "📊"),
    (("cpi", "inflation", "consumer price", "pce ", "producer price"), "inflation", "📈"),
    (("tariff", "trade war", "trade deal"), "tariff", "🌐"),
    (("recession", "downgrade u.s.", "credit downgrade"), "macro", "⚠️"),
]


@dataclass
class MacroAlert:
    kind: str
    emoji: str
    message: str


def next_fomc(today: date | None = None, calendar=FOMC_2026) -> tuple[str, int] | None:
    """Return (iso_date, days_until) for the next FOMC decision, or None."""
    today = today or date.today()
    best = None
    for iso in calendar:
        try:
            y, m, d = (int(x) for x in iso.split("-"))
            delta = (date(y, m, d) - today).days
        except Exception:
            continue
        if delta >= 0 and (best is None or delta < best[1]):
            best = (iso, delta)
    return best


def _countdown(days: int) -> str:
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"in {days}d"


def fomc_alert(today: date | None = None, within_days: int = 10) -> MacroAlert | None:
    nxt = next_fomc(today)
    if nxt is None or nxt[1] > within_days:
        return None
    return MacroAlert("fed", "🏛️", f"Fed decision (FOMC) {_countdown(nxt[1])}")


def scan_headlines(titles, limit: int = 5) -> list[MacroAlert]:
    """Flag high-signal macro/event headlines. Pure given the list of titles."""
    out: list[MacroAlert] = []
    seen: set[str] = set()
    for title in titles:
        if not title:
            continue
        low = title.lower()
        for words, kind, emoji in _KEYWORDS:
            if any(w in low for w in words):
                key = title.strip()
                if key in seen:
                    break
                seen.add(key)
                out.append(MacroAlert(kind, emoji, title.strip()))
                break
        if len(out) >= limit:
            break
    return out
