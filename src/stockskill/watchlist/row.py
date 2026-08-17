"""TickerRow: everything the dashboard shows for one ticker, computed from its
fetched data. Pure given a TickerData + SignalConfig -- the LLM computes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import technicals as ta
from ..signals import (SignalConfig, build_snapshot, active_signal,
                       all_strategy_signals, trend, signal_confidence)
from .pipeline import TickerData
from .tickers import detect_categories


@dataclass
class TickerRow:
    ticker: str
    name: str = ""
    price: float | None = None
    changes: dict = field(default_factory=dict)          # 1d/5d/1m/6m/1y (decimals)
    sparkline: list = field(default_factory=list)
    # indicators
    rsi: float | None = None
    bb_position: float | None = None
    bb_squeeze: bool = False
    macd_state: str | None = None
    atr: float | None = None
    adx: float | None = None
    golden_death: str | None = None
    ichimoku: str | None = None                          # above|below|in_cloud
    volume_bias: float | None = None
    vol_spike: bool = False
    # signals
    signal: str = "HOLD"
    trend_arrow: str = "→"
    trend_label: str = "neutral"
    trend_score: float = 0.0
    confidence: str | None = None                        # STRONG/MODERATE/WEAK
    # fundamentals
    market_cap: float | None = None
    pe: float | None = None
    eps: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    sector: str | None = None
    # range
    week52_high: float | None = None
    week52_low: float | None = None
    week52_position: float | None = None                 # 0..1 within the 52w range
    next_earnings: str | None = None                     # ISO date of next earnings
    # annualized drift + volatility (for the barrier win-probability / Kelly sizing)
    drift_annual: float | None = None
    vol_annual: float | None = None
    # extended-hours (pre/post-market)
    market_state: str | None = None
    ext_price: float | None = None
    ext_change: float | None = None
    # flags & tags
    flags: set = field(default_factory=set)
    categories: set = field(default_factory=set)
    sections: set = field(default_factory=set)
    # embedded stock-analyzer detail (valuation + consensus), for card expansion
    valuation: dict = field(default_factory=dict)
    price_history: dict = field(default_factory=dict)   # {"d": [iso...], "c": [close...]}
    # cross-sectional factor scores (0-100 percentiles) + plain-English read
    factor: dict = field(default_factory=dict)          # {label, composite, value, quality, momentum}
    error: str | None = None


def _downsample_history(dates, closes, daily_bars: int = 130, older_step: int = 5) -> dict:
    """Compact a (dates, closes) series for the card chart.

    Keeps the most recent ``daily_bars`` (~6 months) at full daily resolution so
    the short timeframes (1M/3M) are crisp, and samples older history every
    ``older_step`` bars (~weekly) to keep the embedded payload small. The chart
    slices by calendar date, so uneven spacing is fine.
    """
    L = len(closes)
    if L == 0:
        return {}
    cut = max(0, L - daily_bars)
    idx = sorted(set(range(0, cut, older_step)) | set(range(cut, L)))
    return {"d": [dates[i].isoformat() for i in idx],
            "c": [round(float(closes[i]), 2) for i in idx]}


def build_row(td: TickerData, cfg: SignalConfig | None = None,
              section_tags: set | None = None) -> TickerRow:
    cfg = cfg or SignalConfig()
    row = TickerRow(ticker=td.ticker, sections=set(section_tags or ()))
    if td.error:
        row.error = td.error

    o = td.ohlcv or {}
    highs, lows, closes, vols = o.get("high", []), o.get("low", []), o.get("close", []), o.get("volume", [])
    snap = td.snapshot

    if closes:
        row.price = closes[-1]
        row.changes = ta.change_metrics(closes)
        row.sparkline = ta.sparkline(closes, 30)
        row.rsi = ta.rsi(closes)
        bb = ta.bollinger(closes)
        if bb:
            row.bb_position, row.bb_squeeze = bb.position_pct, bb.squeeze
        m = ta.macd(closes)
        row.macd_state = m.state if m else None
        row.atr = ta.atr(highs, lows, closes)
        row.adx = ta.adx(highs, lows, closes)
        row.golden_death = ta.golden_death_cross(closes)
        ich = ta.ichimoku(highs, lows, closes)
        row.ichimoku = ich.price_vs_cloud if ich else None
        row.volume_bias = ta.volume_bias(closes, vols) if vols else None
        row.vol_spike = ta.volume_spike(vols)[0] if vols else False
        dates = o.get("dates") or []
        if dates and len(dates) == len(closes):
            row.price_history = _downsample_history(dates, closes)

        # annualized drift + vol from trailing ~1y daily returns (win-prob / Kelly)
        window = closes[-253:]
        rets = [b / a - 1.0 for a, b in zip(window[:-1], window[1:]) if a]
        if len(rets) > 20:
            import math as _math
            mean = sum(rets) / len(rets)
            var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
            row.drift_annual = mean * 252
            row.vol_annual = (var ** 0.5) * _math.sqrt(252)

        # signals
        s = build_snapshot(highs, lows, closes, vols)
        row.signal = active_signal(s, cfg)
        tr = trend(s, row.signal, cfg)
        row.trend_arrow, row.trend_label, row.trend_score = tr.arrow, tr.label, tr.score
        conf = signal_confidence(all_strategy_signals(s, cfg), row.signal)
        row.confidence = conf.level if conf else None

    if snap:
        row.name = snap.name or td.ticker
        row.sector = snap.sector
        row.price = row.price if row.price is not None else snap.price
        row.market_cap = snap.market_cap
        row.eps = snap.eps
        if snap.eps and snap.eps > 0 and row.price:
            row.pe = row.price / snap.eps
        row.beta = snap.beta
        if snap.dividend_annual and row.price:
            row.dividend_yield = snap.dividend_annual / row.price
        row.week52_high = snap.fifty_two_week_high
        row.week52_low = snap.fifty_two_week_low
        if row.price and snap.fifty_two_week_high and snap.fifty_two_week_low:
            rng = snap.fifty_two_week_high - snap.fifty_two_week_low
            if rng > 0:
                row.week52_position = (row.price - snap.fifty_two_week_low) / rng
        row.next_earnings = snap.next_earnings
        row.market_state = snap.market_state
        row.ext_price = snap.ext_price
        row.ext_change = snap.ext_change
        row.categories = detect_categories(td.ticker, snap.name, snap.sector,
                                            snap.quote_type, snap.dividend_annual)
        # Embed the analyzer valuation (reuses the fetched snapshot -- no network).
        try:
            from ..analyze import analyze_ticker
            row.valuation = analyze_ticker(td.ticker, snapshot=snap, with_options=False)
        except Exception:
            row.valuation = {}

    row.flags = _flags(row, cfg)
    return row


def _flags(r: TickerRow, cfg: SignalConfig) -> set:
    f: set = set()
    day = r.changes.get("1d")
    if r.rsi is not None and r.rsi <= cfg.rsi_oversold:
        f.add("oversold")
    if r.rsi is not None and r.rsi >= cfg.rsi_overbought:
        f.add("overbought")
    if day is not None and day >= 0.10:
        f.add("surge")
    if day is not None and day <= -0.10:
        f.add("crash")
    if r.bb_squeeze:
        f.add("squeeze")
    if r.vol_spike:
        f.add("vol_spike")
    if r.price and r.week52_high and r.price >= 0.99 * r.week52_high:
        f.add("near_52w_high")
    if r.price and r.week52_low and r.price <= 1.01 * r.week52_low:
        f.add("near_52w_low")
    if earnings_days(r.next_earnings) is not None and earnings_days(r.next_earnings) <= 7:
        f.add("earnings_soon")
    return f


def earnings_days(iso: str | None) -> int | None:
    """Whole days from today until the ISO earnings date (None if unknown/past)."""
    if not iso:
        return None
    try:
        from datetime import date
        y, m, d = (int(x) for x in iso.split("-"))
        delta = (date(y, m, d) - date.today()).days
        return delta if delta >= 0 else None
    except Exception:
        return None
