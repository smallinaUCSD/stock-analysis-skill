"""Maintain holdings.csv from trades: buy / sell / reprice.

Holdings are tracked in SHARES (what a trade changes); market_value is kept in
sync by repricing at a given or fetched price. Rows that predate share-tracking
(dollar-only) get their shares inferred from market_value / price on first trade.
The pure logic (apply_trade) is unit-tested; price fetching lives in the CLI.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class HoldingRow:
    ticker: str
    account: str
    shares: float | None
    market_value: float | None
    cost_basis: float | None = None   # average price paid per share (optional)


def _num(v):
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def read_rows(path: str | Path) -> list[HoldingRow]:
    rows: list[HoldingRow] = []
    with open(path) as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    for r in csv.DictReader(lines):
        tk = (r.get("ticker") or "").strip().upper()
        if not tk:
            continue
        rows.append(HoldingRow(tk, (r.get("account") or "").strip(),
                               _num(r.get("shares")), _num(r.get("market_value")),
                               _num(r.get("cost_basis"))))
    return rows


def write_rows(path: str | Path, rows: list[HoldingRow]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "market_value", "account", "shares", "cost_basis"])
        for r in rows:
            w.writerow([
                r.ticker,
                "" if r.market_value is None else round(r.market_value, 2),
                r.account,
                "" if r.shares is None else round(r.shares, 4),
                "" if r.cost_basis is None else round(r.cost_basis, 4),
            ])


def find(rows, ticker: str, account: str | None):
    for r in rows:
        if r.ticker == ticker.upper() and (account is None or r.account == account):
            return r
    return None


def apply_trade(rows: list[HoldingRow], ticker: str, account: str,
                delta_shares: float, price: float | None) -> HoldingRow | None:
    """Buy (delta>0) or sell (delta<0). Repositions the row; removes it if the
    position goes to zero. Returns the updated row (or None if closed)."""
    ticker = ticker.upper()
    r = find(rows, ticker, account)
    if r is None:
        if delta_shares <= 0:
            raise ValueError(f"no {ticker} position in {account!r} to sell")
        r = HoldingRow(ticker, account, 0.0, 0.0)
        rows.append(r)
    # infer shares from dollar value on legacy rows
    if r.shares is None:
        r.shares = (r.market_value / price) if (r.market_value and price) else 0.0
    new_shares = r.shares + delta_shares
    if new_shares <= 1e-9:
        rows.remove(r)
        return None
    r.shares = new_shares
    if price:
        r.market_value = r.shares * price
    return r


def reprice(rows: list[HoldingRow], price_of) -> int:
    """Refresh market_value = shares * current price for every share-based row.
    ``price_of`` maps ticker -> price (None to skip). Returns # repriced."""
    n = 0
    for r in rows:
        if r.shares is None:
            continue
        p = price_of(r.ticker)
        if p:
            r.market_value = r.shares * p
            n += 1
    return n
