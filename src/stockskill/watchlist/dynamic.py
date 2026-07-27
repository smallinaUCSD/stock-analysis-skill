"""Dynamic ("smart") watchlist: pinned core + rotating growth/value/sector picks.

Pinned staples are ALWAYS kept (never rotated out). Around ~25 rotating slots
are filled from a curated candidate pool by growth (revenue growth) and value
(undervalued -- positive margin of safety), plus the leading sectors. For every
selected company/sector we also add its 2x/3x leveraged ETF where one exists.

The selection (`build_smart_universe`) is pure and unit-tested; the CLI fetches
the fundamentals/valuations that feed it.
"""

from __future__ import annotations

from dataclasses import dataclass

# Core staples / holdings that must always be on the board.
PINNED = ["COST", "AAPL", "META", "MSFT", "GOOGL", "AMZN", "NVDA", "PEP", "WMT", "V", "LLY"]

# Single-stock leveraged (mostly 2x). underlying -> leveraged ticker.
LEVERAGED_FOR = {
    "AAPL": "AAPU", "MSFT": "MSFU", "META": "METU", "TSLA": "TSLL",
    "NVDA": "NVDU", "AMZN": "AMZU", "GOOGL": "GGLL", "COIN": "CONL",
    "PLTR": "PTIR", "AVGO": "AVL", "NFLX": "NFXL", "MSTR": "MSTU",
}
# Sector SPDR -> 3x leveraged (Direxion).
SECTOR_LEVERAGED = {
    "XLK": "TECL", "XLF": "FAS", "XLE": "ERX", "XLV": "CURE",
    "XLY": "WANT", "XLU": "UTSL", "XLRE": "DRN",
}

# Funds that are always kept on the board (never rotated out).
PINNED_FUNDS = ["FCNTX", "FDGRX", "WSMNX", "VOO", "QQQ", "SCHD"]

# Curated candidate pool the rotating picks are drawn from.
CANDIDATES = [
    # mega-cap / software
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "AMD", "NFLX",
    "CRM", "ORCL", "ADBE", "NOW", "PLTR", "SNOW", "MDB", "UBER", "SHOP", "COIN", "MSTR",
    # semiconductors / equipment
    "MU", "QCOM", "TXN", "INTC", "ARM", "SMCI", "DELL", "PANW", "CRWD", "DDOG",
    "ASML", "TSM", "KLAC", "LRCX", "AMAT", "ADI", "NXPI", "MRVL", "ON", "MCHP",
    # AI infrastructure / data centers / power
    "NBIS", "EQIX", "DLR", "VRT", "ANET", "CIEN", "CEG", "VST", "SMR", "OKLO", "TLN", "BE",
    # consumer / financials
    "COST", "WMT", "PEP", "KO", "PG", "MCD", "SBUX", "NKE", "HD", "LOW",
    "V", "MA", "JPM", "BAC", "GS", "MS", "BLK", "SCHW", "AXP", "PYPL",
    # healthcare
    "UNH", "LLY", "JNJ", "ABBV", "MRK", "PFE", "TMO", "ISRG", "VRTX", "REGN",
    "AMGN", "GILD", "BMY", "MDT", "ZTS", "SYK", "VEEV", "DXCM", "MCK", "MRNA",
    # energy
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "FANG",
    # industrials / materials / space-defense
    "CAT", "DE", "GE", "BA", "HON", "LMT", "RTX", "NOC", "ETN", "GLW", "CMI",
    "RKLB", "LUNR", "ASTS", "PL",
    # other
    "DIS", "CMCSA", "TMUS", "ABNB", "BKNG", "MAR", "LULU", "CMG",
]


@dataclass
class Candidate:
    ticker: str
    growth: float | None = None    # revenue (or earnings) growth, decimal
    mos: float | None = None       # margin of safety; >0 == undervalued
    sector: str | None = None


def _dedup(seq):
    out, seen = [], set()
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def build_smart_universe(candidates: list[Candidate], sector_leaders: list[str],
                         pinned: list[str] | None = None,
                         n_growth: int = 10, n_value: int = 10,
                         n_sectors: int = 3, funds: list[str] | None = None) -> dict:
    """Assemble the sectioned smart universe. Pure given scored candidates."""
    pinned = list(pinned if pinned is not None else PINNED)
    funds = list(funds if funds is not None else PINNED_FUNDS)
    pinned_set = set(pinned) | set(funds)

    growth = sorted((c for c in candidates if c.growth is not None and c.ticker not in pinned_set),
                    key=lambda c: c.growth, reverse=True)
    growth_picks = _dedup(c.ticker for c in growth[:n_growth])

    value = sorted((c for c in candidates if c.mos is not None and c.mos > 0
                    and c.ticker not in pinned_set and c.ticker not in growth_picks),
                   key=lambda c: c.mos, reverse=True)
    value_picks = _dedup(c.ticker for c in value[:n_value])

    sector_syms = []
    for etf in sector_leaders[:n_sectors]:
        sector_syms.append(etf)
        if etf in SECTOR_LEVERAGED:
            sector_syms.append(SECTOR_LEVERAGED[etf])
    sector_syms = _dedup(sector_syms)

    lev_picks = _dedup(LEVERAGED_FOR[tk] for tk in (pinned + growth_picks + value_picks)
                       if tk in LEVERAGED_FOR)

    sections = {
        "PINNED": _dedup(pinned),
        "FUNDS": _dedup(funds),
        "LEVERAGED": lev_picks,
        "GROWTH": growth_picks,
        "VALUE": value_picks,
        "SECTOR": sector_syms,
    }
    all_tickers = _dedup(pinned + funds + lev_picks + growth_picks + value_picks + sector_syms)
    return {"sections": sections, "all": all_tickers}


def write_sectioned(path, universe: dict) -> None:
    """Write the smart universe to a sectioned tickers.csv."""
    order = ["PINNED", "FUNDS", "LEVERAGED", "GROWTH", "VALUE", "SECTOR"]
    lines = ["# Auto-generated smart watchlist. Regenerate with `stockskill smart-watchlist`.",
             "# Pinned staples are always kept; GROWTH/VALUE/SECTOR rotate.", ""]
    for sec in order:
        tks = universe["sections"].get(sec, [])
        if not tks:
            continue
        lines.append(f"[{sec}]")
        lines.append(", ".join(tks))
        lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))
