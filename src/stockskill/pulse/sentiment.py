"""Market sentiment: CVR3 (computed), CNN Fear & Greed and AAII (best-effort).

CVR3 is a pure, tested function over the VIX series. Fear & Greed and AAII are
fetched from external sources and may be unavailable -- they return None rather
than failing the whole pulse.
"""

from __future__ import annotations

from dataclasses import dataclass


def cvr3_signal(vix_closes, ma_period: int = 10, threshold: float = 0.10) -> str:
    """Connors-style VIX reversal. A VIX spike far above its average is fear
    (contrarian BUY for equities); VIX far below is complacency (SELL).

    Returns BUY / SELL / NEUTRAL. Pure and deterministic.
    """
    c = list(vix_closes)
    if len(c) < ma_period:
        return "NEUTRAL"
    ma = sum(c[-ma_period:]) / ma_period
    if ma == 0:
        return "NEUTRAL"
    last = c[-1]
    if last >= ma * (1.0 + threshold):
        return "BUY"
    if last <= ma * (1.0 - threshold):
        return "SELL"
    return "NEUTRAL"


@dataclass
class FearGreed:
    score: float
    rating: str


def fetch_fear_greed() -> FearGreed | None:
    """CNN Fear & Greed index (0-100). Best-effort; None on failure."""
    import requests

    try:
        r = requests.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={
                "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/120.0 Safari/537.36"),
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.cnn.com/markets/fear-and-greed",
                "Origin": "https://www.cnn.com",
            }, timeout=8)
        d = r.json().get("fear_and_greed", {})
        score = d.get("score")
        if score is None:
            return None
        return FearGreed(float(score), str(d.get("rating", "")).title())
    except Exception:
        return None


@dataclass
class AAII:
    bullish: float
    bearish: float
    spread: float   # bullish - bearish


def fetch_aaii() -> AAII | None:
    """AAII bull/bear survey. No stable free API -- best-effort, often None.

    Kept as a stub so the dashboard degrades gracefully; wire a source in later.
    """
    return None
