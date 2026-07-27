"""Parse a (optionally sectioned) ticker file and detect categories.

Sectioned format:
    [MEME]
    GME, AMC, KOSS
    [M7]
    AAPL, MSFT, GOOGL, ...
    [TICKERS]
    ...
Simple format (no headers) is also supported. Tickers are deduped in
first-seen order; sections drive the MEME / M7 filter chips.
"""

from __future__ import annotations

from ..leverage import registry

_LEVERAGED_WORDS = ("2x", "3x", "bull", "bear", "leveraged", "ultra", "ultrapro",
                    "inverse", "-1x", "1.5x", "daily")


def parse_tickers_text(text: str) -> dict:
    """Parse sectioned ticker text -> {'sections': {NAME: [tickers]}, 'all': [...]}."""
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    seen: set[str] = set()
    current = "TICKERS"
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().upper()
            sections.setdefault(current, [])
            continue
        for tok in line.replace(",", " ").split():
            t = tok.strip().upper()
            if not t:
                continue
            sections.setdefault(current, [])
            if t not in sections[current]:
                sections[current].append(t)
            if t not in seen:
                seen.add(t)
                order.append(t)
    return {"sections": sections, "all": order}


def parse_tickers(path: str) -> dict:
    """Return {'sections': {NAME: [tickers]}, 'all': [deduped, ordered]} from a file."""
    with open(path) as f:
        return parse_tickers_text(f.read())


def detect_categories(ticker: str, name: str | None = None,
                      sector: str | None = None, quote_type: str | None = None,
                      dividend: float | None = None) -> set[str]:
    """Fundamental-derived category tags (section tags like MEME/M7 are separate)."""
    cats: set[str] = set()
    nm = (name or "").lower()
    leveraged = registry.is_leveraged(ticker) or any(w in nm for w in _LEVERAGED_WORDS)
    if leveraged:
        cats.add("leveraged")
    if quote_type == "ETF" and not leveraged:
        cats.add("etf")
    if sector == "Technology":
        cats.add("tech")
    if dividend and dividend > 0:
        cats.add("dividend")
    return cats
