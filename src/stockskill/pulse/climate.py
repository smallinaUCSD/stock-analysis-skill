"""Market climate from commodities -- known macro tells, made explicit.

* Copper ("Dr. Copper") rising -> real economic demand -> pro-growth.
* Gold rising -> a fear bid -> risk-off / caution.
* The copper/gold ratio rising -> risk-on (it tracks growth & yields).

Combined into a simple climate score/label. Pure and tested. This is also the
macro input Phase 7's Monte Carlo can lean its drift on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..technicals.changes import pct_change


@dataclass
class Climate:
    copper_1m: float | None
    gold_1m: float | None
    copper_gold_1m: float | None    # trend of the copper/gold ratio
    score: int
    label: str
    notes: list = field(default_factory=list)


def market_climate(price_map: dict[str, list[float]], n: int = 21) -> Climate:
    cu = pct_change(price_map.get("HG=F", []), n)   # copper
    au = pct_change(price_map.get("GC=F", []), n)   # gold
    cu_s, au_s = price_map.get("HG=F", []), price_map.get("GC=F", [])

    ratio = None
    if len(cu_s) > n and len(au_s) > n and au_s[-1] and au_s[-1 - n]:
        r_now = cu_s[-1] / au_s[-1]
        r_past = cu_s[-1 - n] / au_s[-1 - n]
        if r_past:
            ratio = r_now / r_past - 1.0

    score = 0
    notes: list[str] = []
    if cu is not None:
        if cu > 0.02:
            score += 1; notes.append(f"copper {cu:+.0%} → economic strength")
        elif cu < -0.02:
            score -= 1; notes.append(f"copper {cu:+.0%} → demand softening")
    if au is not None:
        if au > 0.03:
            score -= 1; notes.append(f"gold {au:+.0%} → fear bid")
        elif au < -0.03:
            score += 1; notes.append(f"gold {au:+.0%} → fear easing")
    if ratio is not None:
        if ratio > 0.02:
            score += 1; notes.append(f"copper/gold {ratio:+.0%} → risk-on")
        elif ratio < -0.02:
            score -= 1; notes.append(f"copper/gold {ratio:+.0%} → risk-off")

    label = ("Risk-on (pro-growth)" if score >= 2 else
             "Risk-off / caution" if score <= -2 else "Mixed / neutral")
    return Climate(cu, au, ratio, score, label, notes)
