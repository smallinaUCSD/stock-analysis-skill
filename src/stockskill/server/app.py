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
from .holdings_service import HoldingsService
from .holdings_page import holdings_html

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-\^]{1,12}$")


def create_app(tickers_path: str = "data/tickers.csv", cache_dir: str | None = None,
               holdings_path: str = "holdings.csv", public: bool | None = None,
               bmc_url: str | None = None) -> Flask:
    """Build the Flask app.

    ``public=True`` (or env ``STOCKSKILL_PUBLIC=1``) is the SAFE mode for a shared
    deployment: it does NOT register the holdings routes or the watchlist-mutation
    routes, and the board is rendered without the Holdings button or add-ticker box,
    so a public visitor can never see or change personal data. ``bmc_url`` (or env
    ``STOCKSKILL_BMC_URL``) adds a "Buy me a coffee" link.
    """
    import os
    if public is None:
        public = os.environ.get("STOCKSKILL_PUBLIC", "").lower() in ("1", "true", "yes")
    bmc_url = bmc_url or os.environ.get("STOCKSKILL_BMC_URL") or None
    tickers_path = os.environ.get("STOCKSKILL_TICKERS") or tickers_path
    cache_dir = os.environ.get("STOCKSKILL_CACHE_DIR") or cache_dir
    # shorter history = a lighter, faster first build (important on small hosts).
    period = os.environ.get("STOCKSKILL_PERIOD") or ("1y" if public else "5y")
    # a long cache TTL serves a committed data snapshot without refetching — useful
    # when the host IP is rate-limited (STOCKSKILL_CACHE_TTL in seconds).
    try:
        cache_ttl = float(os.environ.get("STOCKSKILL_CACHE_TTL") or 1800.0)
    except ValueError:
        cache_ttl = 1800.0

    app = Flask(__name__)
    board = WatchlistService(tickers_path=tickers_path, cache_dir=cache_dir,
                             public=public, bmc_url=bmc_url, period=period,
                             cache_ttl=cache_ttl)
    board.wait_ready(0)   # start building the board in the background at startup

    @app.get("/")
    def index():
        return board.html()

    @app.get("/analyze")
    def analyze():
        return analyzer_html()

    @app.get("/indicators")
    def indicators_page():
        from .indicators_page import indicators_html
        return indicators_html(request.args.get("t", ""))

    if not public:
        # personal, local-only features — omitted entirely in public mode so a
        # shared deployment can never expose or mutate personal data.
        holdings = HoldingsService(path=holdings_path)

        @app.get("/holdings")
        def holdings_page():
            from datetime import datetime
            from ..marketclock import ET
            return holdings_html(holdings.snapshot(),
                                 updated=datetime.now(ET).strftime("%a %b %d, %I:%M %p") + " ET")

        @app.get("/api/holdings")
        def holdings_json():
            return jsonify(holdings.snapshot())

        @app.post("/api/holdings/trade")
        def holdings_trade():
            amt = request.args.get("amount", type=float)
            price = request.args.get("price", type=float)
            settle = request.args.get("settle", "1") not in ("0", "false", "no")
            res = holdings.trade(request.args.get("ticker", ""), request.args.get("account", ""),
                                 request.args.get("side", ""), amt or 0.0,
                                 settle_cash=settle, price=price)
            return jsonify(res), (200 if res.get("ok") else 400)

        @app.post("/api/holdings/cash")
        def holdings_cash():
            amt = request.args.get("amount", type=float)
            res = holdings.cash(request.args.get("account", ""),
                                request.args.get("direction", ""), amt or 0.0)
            return jsonify(res), (200 if res.get("ok") else 400)

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
        return {"ok": True, "public": public}

    @app.get("/api/search")
    def search():
        from ..data.search import search_symbols
        return jsonify({"results": search_symbols(request.args.get("q", ""))})

    @app.get("/api/news/<ticker>")
    def news(ticker: str):
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        from ..data.news import fetch_news
        limit = request.args.get("limit", default=6, type=int) or 6
        name = request.args.get("name")
        return jsonify({"ticker": ticker.upper(),
                        "items": fetch_news(ticker.upper(), limit=max(1, min(12, limit)), name=name)})

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
        if p is not None:
            con = sorted(p.constituents.items(), key=lambda kv: kv[1], reverse=True)
            return jsonify({
                "ok": True, "ticker": p.ticker, "name": p.name, "kind": p.kind,
                "multiplier": p.multiplier, "verify": p.verify, "as_of": p.as_of,
                "constituents": [{"underlying": u, "weight": w} for u, w in con],
            })
        # Not a leveraged product — try a plain ETF/fund (VOO, QQQ, XLK…).
        from ..data.funds import etf_holdings
        eh = etf_holdings(ticker.upper())
        if eh and eh.get("holdings"):
            return jsonify({
                "ok": True, "ticker": ticker.upper(),
                "name": eh.get("name") or ticker.upper(), "kind": "etf",
                "multiplier": 1.0, "verify": False, "as_of": None,
                "constituents": [{"underlying": h["underlying"], "weight": h["weight"]}
                                 for h in eh["holdings"]],
                "sectors": eh.get("sectors"),
                "note": "Top holdings (not the full basket); live from the fund.",
            })
        return jsonify({"ok": False,
                        "error": f"{ticker.upper()} isn't a tracked product",
                        "note": "Look-through works for leveraged ETFs/ETNs "
                                "(FNGU, BULZ, AAPU…) and index/sector ETFs (VOO, QQQ, XLK…)."}), 404

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

    @app.get("/api/indicators/<ticker>")
    def indicators(ticker: str):
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        period = request.args.get("period", "1y")
        if period not in ("3mo", "6mo", "1y", "2y", "5y"):
            period = "1y"
        from ..data.prices import ohlcv
        from ..technicals import series as S
        try:
            o = ohlcv(ticker.upper(), period)
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": str(e)}), 502
        closes = o.get("close") or []
        highs, lows = o.get("high") or [], o.get("low") or []
        vols = o.get("volume") or []
        if len(closes) < 30:
            return jsonify({"error": f"not enough history for {ticker.upper()}"}), 404
        mid, up, lo = S.bollinger_series(closes)
        macd_line, sig, hist = S.macd_series(closes)
        k, dk = S.stochastic_series(highs, lows, closes)
        adx, plus_di, minus_di = S.adx_series(highs, lows, closes)
        ich = S.ichimoku_series(highs, lows, closes)
        return jsonify({
            "ticker": ticker.upper(), "period": period,
            "dates": [d.isoformat() for d in o.get("dates", [])],
            "close": [round(c, 4) for c in closes],
            "sma20": S.sma_series(closes, 20), "sma50": S.sma_series(closes, 50),
            "bb_upper": up, "bb_mid": mid, "bb_lower": lo,
            "rsi": S.rsi_series(closes), "macd": macd_line, "signal": sig, "hist": hist,
            "atr": S.atr_series(highs, lows, closes),
            "stoch_k": k, "stoch_d": dk,
            "adx": adx, "plus_di": plus_di, "minus_di": minus_di,
            "obv": S.obv_series(closes, vols),
            "ichimoku": ich,
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
