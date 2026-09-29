"""Forgiving name matching for search boxes: "pelosi", "Nancy P", "palosi"
and "pelosy" all find Nancy Pelosi. Pure and fast (names are a few hundred)."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


def score(query: str, name: str) -> float:
    """0..1: 1 for a substring, high for word prefixes, then close spellings."""
    q, n = _norm(query), _norm(name)
    if not q or not n:
        return 0.0
    if q in n:
        return 1.0 if n.startswith(q) or f" {q}" in f" {n}" else 0.9
    words, qw = n.split(), q.split()
    if all(any(w.startswith(x) for w in words) for x in qw):
        return 0.85                                        # "nan pel"
    best = 0.0
    for x in qw:                                           # each typed word vs the closest word in the name
        if len(x) < 3:
            continue
        m = max((SequenceMatcher(None, x, w).ratio() for w in words), default=0.0)
        best = max(best, m)
    whole = SequenceMatcher(None, q, n).ratio()
    return max(best * 0.8, whole * 0.8)


def rank(query: str, items: list, key, limit: int = 8, floor: float = 0.62) -> list:
    """The best-matching items, best first."""
    scored = [(score(query, key(it)), i, it) for i, it in enumerate(items)]
    return [it for s, i, it in sorted((x for x in scored if x[0] >= floor), key=lambda x: (-x[0], x[1]))[:limit]]
