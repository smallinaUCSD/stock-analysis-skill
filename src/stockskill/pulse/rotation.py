"""Early rotation detection via short-term momentum inflection.

For each index/sector, compare the 3-day daily rate to the 5-day daily rate:
if the 3-day rate is higher, momentum is *accelerating*. The rotation leader is
the accelerating name with the strongest recent (3-day) move -- an early tell
that money is flowing toward it. Pure and tested.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..technicals.changes import pct_change
from .market_bar import ROTATION


@dataclass
class RotationLeader:
    ticker: str
    label: str
    ret_3d: float
    ret_5d: float
    acceleration: float   # 3d daily rate - 5d daily rate (>0 = accelerating)


def detect_rotation(price_map: dict[str, list[float]],
                    labels: dict[str, str] | None = None) -> RotationLeader | None:
    """Return the accelerating leader, or None if nothing is inflecting up."""
    labels = labels or ROTATION
    candidates = []
    for tk, label in labels.items():
        c = price_map.get(tk, [])
        r3, r5 = pct_change(c, 3), pct_change(c, 5)
        if r3 is None or r5 is None:
            continue
        accel = r3 / 3.0 - r5 / 5.0
        candidates.append(RotationLeader(tk, label, r3, r5, accel))
    accelerating = [c for c in candidates if c.acceleration > 0]
    if not accelerating:
        return None
    return max(accelerating, key=lambda c: c.ret_3d)
