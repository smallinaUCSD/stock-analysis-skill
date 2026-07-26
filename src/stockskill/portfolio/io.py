"""Load holdings from a simple CSV: ticker,market_value,account."""

from __future__ import annotations

import csv
from pathlib import Path

from .lookthrough import Holding


def load_holdings_csv(path: str | Path) -> list[Holding]:
    """Read holdings from CSV with header ``ticker,market_value,account``.

    Rows whose ticker is blank or starts with '#' are skipped (comments).
    ``account`` is optional. Cash rows (ticker CASH) are kept as plain
    exposure to themselves.
    """
    holdings: list[Holding] = []
    with open(path, newline="") as f:
        # Drop leading/comment lines so the real header row is used.
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
        reader = csv.DictReader(lines)
        for row in reader:
            ticker = (row.get("ticker") or "").strip()
            if not ticker or ticker.startswith("#"):
                continue
            try:
                mv = float(str(row.get("market_value", "")).replace(",", "").strip())
            except (TypeError, ValueError):
                continue
            holdings.append(Holding(ticker.upper(), mv, (row.get("account") or "").strip()))
    return holdings
