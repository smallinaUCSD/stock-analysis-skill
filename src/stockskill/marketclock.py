"""US market clock. Pure and testable: pass a datetime, get the session state.

Uses America/New_York so it's correct regardless of the machine's timezone.
Regular session is 09:30-16:00 ET, Mon-Fri. Pre (04:00-09:30) and after
(16:00-20:00) are labeled too. Exchange holidays are NOT handled -- a holiday
reads as a normal weekday here; note that when it matters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
PRE_OPEN = time(4, 0)
AFTER_CLOSE = time(20, 0)


@dataclass(frozen=True)
class MarketStatus:
    label: str          # "open" | "pre-market" | "after-hours" | "closed" | "weekend"
    is_open: bool       # regular session in progress
    is_weekday: bool
    et: datetime        # the moment, in ET

    @property
    def badge(self) -> str:
        return {
            "open": "OPEN",
            "pre-market": "PRE-MARKET",
            "after-hours": "AFTER HOURS",
            "closed": "CLOSED",
            "weekend": "WEEKEND",
        }.get(self.label, self.label.upper())


def market_status(now: datetime | None = None) -> MarketStatus:
    """Classify the current (or given) moment into a session state.

    ``now`` may be naive (assumed ET) or timezone-aware (converted to ET).
    """
    if now is None:
        now = datetime.now(ET)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    et = now.astimezone(ET)

    is_weekday = et.weekday() < 5  # Mon=0 .. Sun=6
    if not is_weekday:
        return MarketStatus("weekend", False, False, et)

    t = et.time()
    if REGULAR_OPEN <= t < REGULAR_CLOSE:
        return MarketStatus("open", True, True, et)
    if PRE_OPEN <= t < REGULAR_OPEN:
        return MarketStatus("pre-market", False, True, et)
    if REGULAR_CLOSE <= t < AFTER_CLOSE:
        return MarketStatus("after-hours", False, True, et)
    return MarketStatus("closed", False, True, et)


def refresh_seconds_for(status: "MarketStatus", base_interval: float | None = None) -> int:
    """Auto-refresh cadence: brisk when the market is open, slow when closed.

    This interval is also the server's data-refetch TTL, so it's kept modest to
    avoid hammering the free data source (a whole board of tickers plus the
    market/macro panels refetches each cycle). ``base_interval`` (minutes)
    overrides the adaptive schedule when given.
    """
    if base_interval:
        return max(60, int(base_interval * 60))
    # 15 min whenever a trading session is active (pre-market 4:00 ET -> after-
    # hours close 8:00 PM ET); effectively no updates overnight or on weekends.
    if status.label in ("open", "pre-market", "after-hours"):
        return 900          # 15 min
    return 21600            # 6h (closed after 8pm ET / weekend -> no live updates)
