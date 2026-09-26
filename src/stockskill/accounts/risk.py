"""Is a sign-in unusual for this person? Compares it with their own recent
sign-ins (pure; tested). Reasons, most serious first:

* ``failed attempts``: it came right after several wrong passwords or codes
* ``impossible travel``: too far from the last sign-in to have got there
* ``new country``: a country they haven't signed in from before
* ``new device``: a browser and system they haven't used before

No history means nothing to compare with (a new account, or the first
sign-in after history started being kept), so nothing is flagged; places are
only compared when both sides have one (a private or unknown address isn't).
"""

from __future__ import annotations

import math

FAILED_BEFORE = 5            # wrong passwords/codes in the last hour
TRAVEL_KMH = 900.0           # faster than a plane
TRAVEL_MIN_KM = 500.0        # nearby jumps are usually the IP database, not travel

TEXT = {"failed attempts": "it came right after several wrong passwords or codes",
        "impossible travel": "it was too far from your last sign-in to have travelled there in time",
        "new country": "it's from a country you haven't signed in from before",
        "new device": "it's from a browser and device you haven't used before"}


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def assess(new: dict, history: list[dict], failures_last_hour: int = 0, where=None) -> list[str]:
    """``new``: the sign-in (cc, lat, lon, browser, os, device, ts). ``history``:
    their earlier sign-ins (newest first), each with cc/browser/os/device, ip and
    last_seen. ``where(ip)`` gives {"lat", "lon"} for an earlier sign-in's address."""
    if not history:
        return []
    out = []
    if failures_last_hour >= FAILED_BEFORE:
        out.append("failed attempts")
    if new.get("lat") is not None and where:
        for h in history:                         # the most recent sign-in with a known place
            g = where(h.get("ip")) or {}
            if g.get("lat") is None:
                continue
            d = km((g["lat"], g["lon"]), (new["lat"], new["lon"]))
            hours = max((new["ts"] - (h.get("last_seen") or new["ts"])) / 3600.0, 0.25)
            if d >= TRAVEL_MIN_KM and d / hours > TRAVEL_KMH:
                out.append("impossible travel")
            break
    seen_cc = {h.get("cc") for h in history if h.get("cc")}
    if new.get("cc") and seen_cc and new["cc"] not in seen_cc:
        out.append("new country")
    seen_dev = {(h.get("browser"), h.get("os"), h.get("device")) for h in history if h.get("browser")}
    if seen_dev and (new.get("browser"), new.get("os"), new.get("device")) not in seen_dev:
        out.append("new device")
    return out


def explain(reasons: list[str]) -> str:
    parts = [TEXT[r] for r in reasons if r in TEXT]
    if not parts:
        return ""
    return "We're letting you know because " + (parts[0] if len(parts) == 1 else
                                                 ", ".join(parts[:-1]) + " and " + parts[-1]) + "."
