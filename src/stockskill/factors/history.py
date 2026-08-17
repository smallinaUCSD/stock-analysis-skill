"""Point-in-time fundamentals store — the missing piece for a value backtest.

The live board only has *today's* fundamentals; a value backtest needs to know
each name's P/E, FCF yield, etc. as they were on past dates. There's no free
historical-fundamentals feed, so we build one going forward: record a dated
snapshot of every name's fundamentals each day. After a few months this is a
real point-in-time panel that plugs into :mod:`factors.backtest` unchanged.

One JSON file per date (``store/2026-08-17.json`` = {ticker: snapshot dict}), so
reading "the fundamentals as of date D" is a single file load.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date

from ..data.fundamentals import FundamentalSnapshot


def record_snapshots(snapshots, store_dir: str, as_of: str | None = None) -> int:
    """Write today's (or ``as_of``) fundamentals for every named snapshot.

    Returns the number of names recorded. Overwrites that date's file so a re-run
    is idempotent.
    """
    as_of = as_of or date.today().isoformat()
    rows = {s.ticker: asdict(s) for s in snapshots if s and getattr(s, "name", None)}
    if not rows:
        return 0
    os.makedirs(store_dir, exist_ok=True)
    with open(os.path.join(store_dir, f"{as_of}.json"), "w") as f:
        json.dump(rows, f)
    return len(rows)


def load_history(store_dir: str) -> dict[str, dict[str, dict]]:
    """Load the whole store as {date_str: {ticker: snapshot dict}}, dates ascending."""
    out: dict[str, dict[str, dict]] = {}
    if not os.path.isdir(store_dir):
        return out
    for fn in sorted(os.listdir(store_dir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(store_dir, fn)) as f:
                out[fn[:-5]] = json.load(f)
        except Exception:  # noqa: BLE001
            continue
    return out


def snapshot_at(history: dict, ticker: str, as_of: str) -> FundamentalSnapshot | None:
    """Most recent recorded snapshot for ``ticker`` on or before ``as_of``."""
    best = None
    for d in sorted(history):
        if d > as_of:
            break
        row = history[d].get(ticker)
        if row:
            best = row
    return FundamentalSnapshot(**best) if best else None
