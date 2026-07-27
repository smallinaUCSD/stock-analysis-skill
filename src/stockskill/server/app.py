"""Flask app for the live dashboard.

Routes:
  GET  /                       -> the live watchlist board (cards/table/heatmap)
  GET  /analyze                -> the analyzer page (search any ticker)
  POST /api/watchlist/add      -> add a ticker to the board, live
  POST /api/watchlist/remove   -> remove a user-added ticker
  GET  /api/stock/<ticker>     -> JSON analysis from analyze_ticker
  GET  /api/search             -> symbol search (autocomplete)
  GET  /healthz                -> liveness

The server only exposes the tested analysis engine over HTTP; it computes no
numbers of its own, and emits analysis, not buy/sell/hold advice.
"""

from __future__ import annotations

import re

from flask import Flask, jsonify, request

from ..analyze import analyze_ticker
from .page import analyzer_html
from .watchlist_service import WatchlistService

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-\^]{1,12}$")


def create_app(tickers_path: str = "data/tickers.csv", cache_dir: str | None = None) -> Flask:
    app = Flask(__name__)
    board = WatchlistService(tickers_path=tickers_path, cache_dir=cache_dir)

    @app.get("/")
    def index():
        return board.html()

    @app.get("/analyze")
    def analyze():
        return analyzer_html()

    @app.post("/api/watchlist/add")
    def watchlist_add():
        res = board.add(request.args.get("ticker", ""))
        return jsonify(res), (200 if res.get("ok") else 400)

    @app.post("/api/watchlist/remove")
    def watchlist_remove():
        res = board.remove(request.args.get("ticker", ""))
        return jsonify(res), (200 if res.get("ok") else 400)

    @app.get("/api/watchlist/added")
    def watchlist_added():
        return jsonify({"added": board.added()})

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/api/search")
    def search():
        from ..data.search import search_symbols
        return jsonify({"results": search_symbols(request.args.get("q", ""))})

    @app.get("/api/climate")
    def climate():
        from ..data.prices import closing_prices
        from ..pulse import market_climate
        pm = {"HG=F": closing_prices("HG=F", "3mo"), "GC=F": closing_prices("GC=F", "3mo")}
        c = market_climate(pm)
        return jsonify({
            "label": c.label, "score": c.score, "notes": c.notes,
            "copper_1m": c.copper_1m, "gold_1m": c.gold_1m,
            "copper_gold_1m": c.copper_gold_1m,
        })

    @app.get("/api/evaluate/<ticker>")
    def evaluate(ticker: str):
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        action = request.args.get("action", "buy")
        if action not in ("buy", "sell", "short"):
            return jsonify({"error": "action must be buy|sell|short"}), 400
        args_f = {k: request.args.get(k, type=float) for k in ("price", "stop", "target")}
        try:
            from ..analyze import evaluate_ticker
            ev = evaluate_ticker(ticker.upper(), action, args_f["price"],
                                 args_f["stop"], args_f["target"])
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 502
        if ev.price is None:
            return jsonify({"error": f"no price for {ticker.upper()}"}), 404
        return jsonify({
            "ticker": ev.ticker, "action": ev.action, "price": ev.price,
            "alignment": ev.alignment, "rr": ev.rr,
            "n_support": ev.n_support, "n_against": ev.n_against,
            "factors": [{"name": f.name, "stance": f.stance, "detail": f.detail}
                        for f in ev.factors],
        })

    @app.get("/api/stock/<ticker>")
    def stock(ticker: str):
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        g = request.args.get("growth", type=float)
        try:
            data = analyze_ticker(ticker.upper(), growth=g)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 502
        if data.get("price") is None:
            return jsonify({"error": f"no data for {ticker.upper()} (unknown ticker?)"}), 404
        return jsonify(data)

    @app.get("/api/lookthrough/<ticker>")
    def lookthrough(ticker: str):
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        from ..leverage import registry
        p = registry.get(ticker.upper())
        if p is None:
            return jsonify({"ok": False,
                            "error": f"{ticker.upper()} isn't a tracked leveraged product",
                            "note": "Look-through applies to leveraged ETFs/ETNs "
                                    "(e.g. FNGU, BULZ, AAPU, TSLL, SOXL, ORCX)."}), 404
        con = sorted(p.constituents.items(), key=lambda kv: kv[1], reverse=True)
        return jsonify({
            "ok": True, "ticker": p.ticker, "name": p.name, "kind": p.kind,
            "multiplier": p.multiplier, "verify": p.verify,
            "constituents": [{"underlying": u, "weight": w} for u, w in con],
        })

    @app.get("/api/montecarlo/<ticker>")
    def montecarlo_route(ticker: str):
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        days = request.args.get("days", default=63, type=int) or 63
        method = request.args.get("method", "gbm")
        if method not in ("gbm", "bootstrap"):
            return jsonify({"error": "method must be gbm|bootstrap"}), 400
        gain = request.args.get("gain", default=0.10, type=float)
        loss = request.args.get("loss", default=0.10, type=float)
        days = max(5, min(756, days))
        from ..data.prices import closing_prices
        from ..montecarlo import montecarlo
        try:
            closes = closing_prices(ticker.upper(), "2y")
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 502
        if not closes or len(closes) < 30:
            return jsonify({"error": f"not enough history for {ticker.upper()}"}), 404
        r = montecarlo(closes, days=days, method=method, gain=gain, loss=loss)
        return jsonify({
            "ticker": ticker.upper(), "spot": r.spot, "days": r.days,
            "n_paths": r.n_paths, "method": r.method,
            "drift_annual": r.drift_annual, "vol_annual": r.vol_annual,
            "expected_return": r.expected_return, "median_return": r.median_return,
            "prob_up": r.prob_up, "prob_gain": r.prob_gain, "prob_loss": r.prob_loss,
            "gain_threshold": r.gain_threshold, "loss_threshold": r.loss_threshold,
            "var_95": r.var_95, "pctiles": r.pctiles,
        })

    @app.get("/api/pulse")
    def pulse():
        from ..data.prices import price_map, closing_prices
        from ..pulse import (SECTOR_ETFS, sector_table, market_climate,
                             detect_rotation, ROTATION, fetch_fear_greed)
        out: dict = {}
        try:
            sec_pm = price_map(list(SECTOR_ETFS), period="3mo")
            secs = sector_table(sec_pm, "1m")
            ranked = [{"name": s.name, "ticker": s.ticker,
                       "ret": s.returns.get("1m")} for s in secs
                      if s.returns.get("1m") is not None]
            ranked.sort(key=lambda x: x["ret"], reverse=True)
            out["sectors_top"] = ranked[:3]
            out["sectors_bottom"] = ranked[-3:][::-1]
        except Exception:  # noqa: BLE001
            out["sectors_top"] = out["sectors_bottom"] = []
        try:
            rot_pm = price_map(list(ROTATION), period="1mo")
            leader = detect_rotation(rot_pm, ROTATION)
            out["rotation"] = leader.name if leader else None
        except Exception:  # noqa: BLE001
            out["rotation"] = None
        try:
            cpm = {"HG=F": closing_prices("HG=F", "3mo"),
                   "GC=F": closing_prices("GC=F", "3mo")}
            c = market_climate(cpm)
            out["climate"] = {"label": c.label, "score": c.score, "notes": c.notes}
        except Exception:  # noqa: BLE001
            out["climate"] = None
        try:
            fg = fetch_fear_greed()
            out["fear_greed"] = {"value": fg.value, "label": fg.label} if fg else None
        except Exception:  # noqa: BLE001
            out["fear_greed"] = None
        return jsonify(out)

    return app
