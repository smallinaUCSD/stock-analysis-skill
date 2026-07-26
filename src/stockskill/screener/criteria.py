"""Pure scoring engine for the screener.

Given raw per-name metrics, rank each metric cross-sectionally (percentile
within the universe), flip "lower is better" metrics, and combine into a
weighted composite. Percentile ranking is robust to outliers and to metrics on
wildly different scales (a P/E of 400 doesn't blow up the score the way raw
min-max would). Missing values are excluded from that name's weighted average
and reflected in a coverage figure -- never guessed.

Deterministic: same rows + specs -> same ranking. Fully unit-tested.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass


@dataclass(frozen=True)
class MetricSpec:
    name: str
    weight: float
    higher_is_better: bool


def percentile_ranks(values: list[float | None]) -> list[float | None]:
    """Percentile rank in [0,1] for each present value; None stays None.

    Ties share the average rank. With one present value, it gets 0.5.
    """
    present = [(i, v) for i, v in enumerate(values) if v is not None and v == v]
    ranks: list[float | None] = [None] * len(values)
    if not present:
        return ranks
    sorted_vals = sorted(v for _, v in present)
    n = len(sorted_vals)
    for i, v in present:
        lo = bisect.bisect_left(sorted_vals, v)
        hi = bisect.bisect_right(sorted_vals, v)
        avg_rank = (lo + hi - 1) / 2.0     # 0-indexed average position among ties
        ranks[i] = avg_rank / (n - 1) if n > 1 else 0.5
    return ranks


@dataclass
class ScoredName:
    ticker: str
    score: float
    coverage: float                       # weight-share of metrics that were present
    components: dict[str, float | None]   # per-metric normalized [0,1] (direction-adjusted)
    raw: dict                             # original metric row


def score_universe(rows: list[dict], specs: list[MetricSpec]) -> list[ScoredName]:
    """Score and rank ``rows`` (each a dict with 'ticker' + metric keys).

    Each metric is percentile-ranked across the universe, inverted if
    ``higher_is_better`` is False, then combined as a weighted average over the
    metrics actually present for that name. Returns names sorted best-first.
    """
    normalized: dict[str, list[float | None]] = {}
    for spec in specs:
        col = [r.get(spec.name) for r in rows]
        pr = percentile_ranks(col)
        if not spec.higher_is_better:
            pr = [None if x is None else (1.0 - x) for x in pr]
        normalized[spec.name] = pr

    total_weight = sum(s.weight for s in specs) or 1.0
    out: list[ScoredName] = []
    for idx, r in enumerate(rows):
        num = den = 0.0
        components: dict[str, float | None] = {}
        for spec in specs:
            x = normalized[spec.name][idx]
            components[spec.name] = x
            if x is None:
                continue
            num += spec.weight * x
            den += spec.weight
        score = num / den if den > 0 else float("nan")
        out.append(ScoredName(
            ticker=r.get("ticker", "?"),
            score=score,
            coverage=den / total_weight,
            components=components,
            raw=r,
        ))
    out.sort(key=lambda s: (s.score if s.score == s.score else -1.0), reverse=True)
    return out
