"""Multi-ticker watchlist: parse a ticker file, fetch in parallel, build rows,
render a table/card/heatmap dashboard. Built on the technicals + signals layers.
"""

from .tickers import parse_tickers, parse_tickers_text, detect_categories
from .pipeline import TickerData, fetch_one, fetch_all
from .row import TickerRow, build_row
from .render import render_watchlist
from .build import build_watchlist_html
from .dynamic import (
    Candidate, build_smart_universe, write_sectioned, PINNED, PINNED_FUNDS, CANDIDATES,
)

__all__ = [
    "parse_tickers", "parse_tickers_text", "detect_categories",
    "TickerData", "fetch_one", "fetch_all",
    "TickerRow", "build_row",
    "render_watchlist", "build_watchlist_html",
    "Candidate", "build_smart_universe", "write_sectioned",
    "PINNED", "PINNED_FUNDS", "CANDIDATES",
]
