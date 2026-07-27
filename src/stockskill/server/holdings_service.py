"""Live holdings state for the served dashboard.

PRIVACY: this reads/writes holdings.csv (real balances, gitignored) and is only
ever served by the local `serve` app — it is NEVER written to a static file and
NEVER published to GitHub Pages. Trades here are BOOKKEEPING to mirror what the
user already did in their brokerage; nothing is sent to any broker.

Holdings here are dollar-based (market_value), matching the CSV. A buy adds
dollars to a position and (optionally) debits that account's cash; a sell does
the reverse. Deposit/withdraw adjust an account's CASH row.
"""

from __future__ import annotations

import re
import threading

from ..portfolio.manage import read_rows, write_rows, HoldingRow

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-\^]{1,12}$")
CASH = "CASH"

# display labels for the known account keys (free-form otherwise)
ACCOUNT_LABELS = {"brokerage": "Brokerage", "roth": "Roth IRA", "401k": "401(k)"}
ACCOUNT_ORDER = ["brokerage", "roth", "401k"]


def account_label(key: str) -> str:
    return ACCOUNT_LABELS.get(key, key or "(unlabeled)")


class HoldingsService:
    def __init__(self, path: str = "holdings.csv"):
        self._path = path
        self._lock = threading.Lock()

    # --- read ----------------------------------------------------------
    def _rows(self) -> list[HoldingRow]:
        try:
            return read_rows(self._path)
        except OSError:
            return []

    def snapshot(self) -> dict:
        rows = self._rows()
        accounts: dict[str, dict] = {}
        for r in rows:
            acct = r.account or "(unlabeled)"
            a = accounts.setdefault(acct, {"key": acct, "label": account_label(acct),
                                           "positions": [], "cash": 0.0})
            mv = r.market_value or 0.0
            if r.ticker == CASH:
                a["cash"] += mv
            else:
                a["positions"].append({"ticker": r.ticker, "market_value": mv,
                                       "shares": r.shares})
        # order + totals
        def akey(k):
            return (ACCOUNT_ORDER.index(k) if k in ACCOUNT_ORDER else 99, k)
        out_accounts = []
        grand_pos = grand_cash = 0.0
        for k in sorted(accounts, key=akey):
            a = accounts[k]
            a["positions"].sort(key=lambda p: p["market_value"], reverse=True)
            pos_total = sum(p["market_value"] for p in a["positions"])
            a["positions_total"] = pos_total
            a["total"] = pos_total + a["cash"]
            grand_pos += pos_total
            grand_cash += a["cash"]
            out_accounts.append(a)
        return {
            "accounts": out_accounts,
            "grand_total": grand_pos + grand_cash,
            "grand_positions": grand_pos,
            "grand_cash": grand_cash,
        }

    # --- write helpers -------------------------------------------------
    def _find(self, rows, ticker, account):
        for r in rows:
            if r.ticker == ticker and r.account == account:
                return r
        return None

    def _cash_row(self, rows, account) -> HoldingRow:
        r = self._find(rows, CASH, account)
        if r is None:
            r = HoldingRow(CASH, account, None, 0.0)
            rows.append(r)
        if r.market_value is None:
            r.market_value = 0.0
        return r

    # --- mutations -----------------------------------------------------
    def trade(self, ticker: str, account: str, side: str, amount: float,
              settle_cash: bool = True) -> dict:
        ticker = (ticker or "").strip().upper()
        account = (account or "").strip()
        if not _TICKER_RE.match(ticker) or ticker == CASH:
            return {"ok": False, "error": f"invalid ticker '{ticker}'"}
        if not account:
            return {"ok": False, "error": "account is required"}
        if side not in ("buy", "sell"):
            return {"ok": False, "error": "side must be buy|sell"}
        if not amount or amount <= 0:
            return {"ok": False, "error": "amount must be a positive dollar value"}
        with self._lock:
            rows = self._rows()
            pos = self._find(rows, ticker, account)
            if side == "buy":
                if pos is None:
                    pos = HoldingRow(ticker, account, None, 0.0)
                    rows.append(pos)
                pos.market_value = (pos.market_value or 0.0) + amount
            else:  # sell
                if pos is None or (pos.market_value or 0.0) <= 0:
                    return {"ok": False, "error": f"no {ticker} position in {account_label(account)} to sell"}
                pos.market_value = (pos.market_value or 0.0) - amount
                if pos.market_value <= 1e-6:
                    rows.remove(pos)
            note = ""
            if settle_cash:
                cash = self._cash_row(rows, account)
                cash.market_value += amount if side == "sell" else -amount
                if cash.market_value < 0:
                    note = "cash is now negative — deposit to reconcile"
            write_rows(self._path, rows)
        return {"ok": True, "ticker": ticker, "account": account, "side": side,
                "amount": amount, "note": note}

    def cash(self, account: str, direction: str, amount: float) -> dict:
        account = (account or "").strip()
        if not account:
            return {"ok": False, "error": "account is required"}
        if direction not in ("deposit", "withdraw"):
            return {"ok": False, "error": "direction must be deposit|withdraw"}
        if not amount or amount <= 0:
            return {"ok": False, "error": "amount must be a positive dollar value"}
        with self._lock:
            rows = self._rows()
            cash = self._cash_row(rows, account)
            cash.market_value += amount if direction == "deposit" else -amount
            note = ""
            if cash.market_value < 0:
                note = "cash is now negative"
            write_rows(self._path, rows)
        return {"ok": True, "account": account, "direction": direction,
                "amount": amount, "balance": cash.market_value, "note": note}
