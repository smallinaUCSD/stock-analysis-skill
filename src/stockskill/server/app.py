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

    return app
