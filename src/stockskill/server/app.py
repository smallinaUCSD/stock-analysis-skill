"""Flask app for the interactive analyzer.

Routes:
  GET /                     -> the analyzer page (search UI)
  GET /api/stock/<ticker>   -> JSON analysis (price, valuation, scenarios,
                               consensus, options) from analyze_ticker
  GET /healthz              -> liveness

The server only exposes the tested analysis engine over HTTP; it computes no
numbers of its own, and emits analysis, not buy/sell/hold advice.
"""

from __future__ import annotations

import re

from flask import Flask, jsonify, request

from ..analyze import analyze_ticker
from .page import analyzer_html

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-\^]{1,12}$")


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return analyzer_html()

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/api/search")
    def search():
        from ..data.search import search_symbols
        return jsonify({"results": search_symbols(request.args.get("q", ""))})

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
