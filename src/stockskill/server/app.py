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

import html
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

    @app.get("/interpret")
    def interpret_page():
        from .interpret_page import interpret_html
        return interpret_html()

    def _peers_for(tk: str, hist: dict | None):
        """Industry peer context for one ticker from the board's cached data."""
        if not hist or not hist.get("sic"):
            return None
        try:
            from ..data import sec as SEC
            from ..performance.benchmarks import load_benchmarks, risk_vs_benchmarks
            from ..valuation.peers import group_of, peer_context
            from ..watchlist.pipeline import _load_cached
            from ..watchlist.tickers import parse_tickers
            sics = {tk: hist["sic"]}
            for t in parse_tickers(tickers_path)["all"]:
                h = SEC.annual_history(t, cache_dir, offline=True) if t != tk else None
                if h and h.get("sic"):
                    sics[t] = h["sic"]
            members, _ = group_of(tk, sics)
            if not members:
                return None
            spy = load_benchmarks(cache_dir, period, cache_ttl, fetch=False).get("SPY")
            snaps, betas = {}, {}
            for t in members:
                td_ = _load_cached(cache_dir, t) if cache_dir else None
                if td_ and td_.snapshot:
                    snaps[t] = td_.snapshot
                    if spy:
                        betas[t] = (risk_vs_benchmarks(td_, {"SPY": spy}).get("SPY") or {}).get("beta")
            return peer_context(tk, sics, snaps, betas)
        except Exception:  # noqa: BLE001
            return None

    @app.get("/analysis/<ticker>")
    def analysis_page(ticker: str):
        from .analysis_page import analysis_html
        from ..watchlist.pipeline import fetch_one
        from ..watchlist import build_row
        from ..watchlist.build import _overlay_live_prices, _apply_ext_prices
        from ..signals import SignalConfig
        from ..marketclock import market_status, refresh_seconds_for
        td = fetch_one(ticker.upper(), period=period, cache_dir=cache_dir, ttl=cache_ttl)
        if not td or not (td.ohlcv or {}).get("close"):
            return (f"<p style='font-family:Georgia,serif;padding:24px'>No data for "
                    f"{html.escape(ticker)}.</p>", 404)
        try:                              # beta/alpha vs SPY and QQQ (cached benchmarks)
            from ..performance.benchmarks import load_benchmarks, risk_vs_benchmarks
            risk = risk_vs_benchmarks(td, load_benchmarks(cache_dir, period, cache_ttl, fetch=True))
        except Exception:  # noqa: BLE001
            risk = {}
        from ..data import sec as SEC
        try:
            hist = SEC.annual_history(ticker.upper(), cache_dir)
            if not (hist and hist.get("years")):
                hist = SEC.yahoo_revenue_history(ticker.upper(), cache_dir)
        except Exception:  # noqa: BLE001
            hist = None
        row = build_row(td, SignalConfig.from_env(),
                        beta=(risk.get("SPY") or {}).get("beta"), sec=hist,
                        peers=_peers_for(ticker.upper(), hist))
        row.risk = risk
        if (risk.get("SPY") or {}).get("beta") is not None:
            row.beta = risk["SPY"]["beta"]
        # Overlay the live price (Finnhub) + extended-hours (Yahoo) so the page
        # shows the current price, not the days-old committed snapshot.
        status = market_status()
        _overlay_live_prices([row], status)   # Finnhub: fast, reliable, one symbol
        # NOT live=True: that fetches Yahoo extended-hours synchronously, which
        # stalls on the host's datacenter IP and hangs the page (and the worker).
        # live=False clears any stale snapshot ext price without a network call;
        # the board still shows after-hours via its background build.
        _apply_ext_prices([row], status, live=False)
        return analysis_html(row, (td.ohlcv or {}).get("close", []),
                             refresh_seconds_for(status))

    # Add-ticker stays available in public mode (shared, resets on restart);
    # only HOLDINGS is gated, since that's the personal/private data.
    @app.post("/api/watchlist/add")
    def watchlist_add():
        res = board.add(request.args.get("ticker", ""))
        return jsonify(res), (200 if res.get("ok") else 400)

    @app.post("/api/watchlist/add_bulk")
    def watchlist_add_bulk():
        # One or many tickers ("NET, OKTA CHKP" or a JSON list). Returns at once
        # with a job id; verification + the board update run in the background.
        body = request.get_json(silent=True) or {}
        tickers = body.get("tickers") or request.args.get("tickers") or request.form.get("tickers") or ""
        res = board.add_bulk(tickers)
        return jsonify(res), (200 if res.get("ok") else 400)

    @app.get("/api/watchlist/add_status/<job_id>")
    def watchlist_add_status(job_id: str):
        st = board.job_status(job_id)
        if st is None:
            return jsonify({"ok": False, "error": "unknown or expired job"}), 404
        return jsonify({"ok": True, **st})

    @app.post("/api/watchlist/remove")
    def watchlist_remove():
        res = board.remove(request.args.get("ticker", ""))
        return jsonify(res), (200 if res.get("ok") else 400)

    @app.get("/api/watchlist/added")
    def watchlist_added():
        return jsonify({"added": board.added()})

    if not public:
        # personal, local-only — omitted in public mode so a shared deployment
        # can never expose or mutate holdings.
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

        _HEDGES = {"SPY": [("SPY", "Short the S&P 500 (SPY)"), ("SH", "Inverse S&P 500, -1x (SH)"),
                           ("SPXU", "Inverse S&P 500, -3x (SPXU)")],
                   "QQQ": [("QQQ", "Short the Nasdaq-100 (QQQ)"), ("PSQ", "Inverse Nasdaq-100, -1x (PSQ)"),
                           ("SQQQ", "Inverse Nasdaq-100, -3x (SQQQ)")]}
        _MULT = {"SH": -1.0, "SPXU": -3.0, "PSQ": -1.0, "SQQQ": -3.0}
        _RISK_CACHE: dict = {}

        @app.get("/api/holdings/risk")
        def holdings_risk():
            """Portfolio beta, where the market risk sits, look-through exposure,
            and hedge sizing for ``pct`` percent of it. Local only (holdings)."""
            import time as _t
            from ..performance.metrics import align_closes, risk_stats
            from ..portfolio.hedge import hedge_plan, portfolio_beta, put_contracts, reset_drag
            from ..portfolio.lookthrough import Holding, expand
            bench = request.args.get("bench", "SPY").upper()
            if bench not in _HEDGES:
                bench = "SPY"
            pct = max(0.0, min(100.0, request.args.get("pct", default=50.0, type=float) or 0.0))
            snap = holdings.snapshot()
            positions = [(p["ticker"], p["market_value"]) for a in snap["accounts"]
                         for p in a["positions"] if p.get("market_value")]
            held = sorted({t for t, _ in positions})
            key = (bench, tuple(held))
            hit = _RISK_CACHE.get(key)
            if not hit or _t.time() - hit[0] > 600:
                tks = sorted(set(held) | {bench} | {h for h, _ in _HEDGES[bench]})
                data = _fetch_many(tks)
                bo = (data.get(bench).ohlcv if data.get(bench) else None) or {}
                betas, prices, drag = {bench: 1.0}, {}, {}
                for t, td in data.items():
                    o = td.ohlcv or {}
                    if o.get("close"):
                        prices[t] = o["close"][-1]
                    if t != bench and o.get("close") and bo.get("close"):
                        rs = risk_stats(o.get("dates"), o["close"], bo.get("dates"), bo["close"],
                                        benchmark=bench)
                        betas[t] = rs.beta if rs else None
                        if t in _MULT:
                            _, f, i = align_closes(o.get("dates"), o["close"], bo.get("dates"), bo["close"])
                            drag[t] = reset_drag(f[-253:], i[-253:], _MULT[t])
                hit = (_t.time(), {"betas": betas, "prices": prices, "drag": drag})
                _RISK_CACHE[key] = hit
            cached = hit[1]
            port = portfolio_beta(positions, cached["betas"], snap.get("grand_cash") or 0.0)
            lt = expand([Holding(t, v) for t, v in positions])
            top = [{"underlying": u, "dollars": d, "share": (d / lt.total_notional) if lt.total_notional else 0}
                   for u, d in lt.top(10)]
            plan = hedge_plan(port["exposure"], pct / 100.0,
                              [{"ticker": h, "label": lbl, "beta": cached["betas"].get(h),
                                "price": cached["prices"].get(h)} for h, lbl in _HEDGES[bench]])
            for x in plan:
                x["drag_1y"] = cached["drag"].get(x["ticker"])
            return jsonify({
                "ok": True, "bench": bench, "bench_name": "S&P 500" if bench == "SPY" else "Nasdaq-100",
                "pct": pct, "portfolio": port,
                "lookthrough": {"leverage": lt.effective_leverage, "notional": lt.total_notional,
                                "top": top},
                "hedges": plan,
                "puts": {"contracts": put_contracts(port["exposure"], pct / 100.0,
                                                   cached["prices"].get(bench)),
                         "index_price": cached["prices"].get(bench), "delta": 0.5},
            })

        @app.post("/api/holdings/cash")
        def holdings_cash():
            amt = request.args.get("amount", type=float)
            res = holdings.cash(request.args.get("account", ""),
                                request.args.get("direction", ""), amt or 0.0)
            return jsonify(res), (200 if res.get("ok") else 400)

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

    _VAL_CACHE: dict = {}

    def _valuation_for(tk: str):
        """(price, valuation dict) built exactly as the board and analysis page
        build it (SEC history, peers, Welch beta). Cached 10 minutes."""
        import time as _t
        hit = _VAL_CACHE.get(tk)
        if hit and _t.time() - hit[0] < 600:
            return hit[1]
        from ..analyze import analyze_ticker
        from ..data import sec as SEC
        from ..performance.benchmarks import load_benchmarks, risk_vs_benchmarks
        from ..watchlist.pipeline import fetch_one
        td = fetch_one(tk, period=period, cache_dir=cache_dir, ttl=cache_ttl)
        if not td or not td.snapshot or not (td.ohlcv or {}).get("close"):
            return None
        hist = SEC.annual_history(tk, cache_dir) or SEC.yahoo_revenue_history(tk, cache_dir)
        risk = risk_vs_benchmarks(td, load_benchmarks(cache_dir, period, cache_ttl, fetch=False))
        v = analyze_ticker(tk, snapshot=td.snapshot, with_options=False,
                           beta=(risk.get("SPY") or {}).get("beta"), sec_history=hist,
                           peers=_peers_for(tk, hist))["valuation"]
        out = (td.ohlcv["close"][-1], v)
        _VAL_CACHE[tk] = (_t.time(), out)
        return out

    @app.get("/api/dcf/<ticker>")
    def dcf_calc(ticker: str):
        """Re-run the DCF with the user's growth (g) and discount rate (r)."""
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        from ..valuation.dcf import DCFInputs, two_stage_dcf
        from ..valuation.reverse_dcf import implied_stage1_growth
        g = request.args.get("g", type=float)
        r = request.args.get("r", type=float)
        if g is None or r is None or not (-0.2 <= g <= 1.0) or not (0.03 <= r <= 0.30):
            return jsonify({"error": "g must be -0.2..1.0 and r 0.03..0.30"}), 400
        got = _valuation_for(ticker.upper())
        base = (got[1].get("dcf_base") if got else None)
        if not base:
            return jsonify({"error": "no cash-flow basis for this ticker"}), 404
        price = got[0]
        inp = DCFInputs(fcf0=base["cash_flow"], shares=base["shares"], net_debt=base["net_debt"],
                        discount_rate=r, stage1_growth=g, stage1_years=base["years"],
                        terminal_growth=min(base["terminal_growth"], r - 0.01))
        try:
            fv = two_stage_dcf(inp).fair_value_per_share
        except ValueError as e:
            return jsonify({"error": str(e)}), 422
        try:
            ig = implied_stage1_growth(price, inp)
        except Exception:  # noqa: BLE001
            ig = None
        return jsonify({"ticker": ticker.upper(), "g": g, "r": r, "price": price,
                        "fair_value": fv, "gap": fv / price - 1.0 if price else None,
                        "implied_growth": ig})

    _VBT_CACHE: dict = {}

    @app.get("/api/valuation/backtest")
    def valuation_backtest():
        """Point-in-time track record of the DCF on the watchlist (cache-only)."""
        import time as _t
        hit = _VBT_CACHE.get("v")
        if hit and _t.time() - hit[0] < 12 * 3600:
            return jsonify(hit[1])
        from ..data import sec as SEC
        from ..leverage import registry
        from ..valuation.backtest import evaluate, observations
        from ..watchlist.pipeline import _load_cached
        from ..watchlist.tickers import parse_tickers
        try:
            tks = [t for t in parse_tickers(tickers_path)["all"] if registry.get(t) is None]
        except Exception:  # noqa: BLE001
            tks = []
        spy = _load_cached(cache_dir, "SPY") if cache_dir else None
        if not spy:
            return jsonify({"ok": False, "error": "no benchmark history cached"}), 503
        uni = {}
        for t in tks:
            td = _load_cached(cache_dir, t)
            h = SEC.annual_history(t, cache_dir, offline=True)
            if not td or not h or len(h.get("years") or []) < 3 or not (td.ohlcv or {}).get("close"):
                continue
            last_sh = next((y["shares"] for y in reversed(h["years"]) if y.get("shares")), None)
            sf, snap_sh = 1.0, (td.snapshot.shares if td.snapshot else None)
            if snap_sh and last_sh and snap_sh / last_sh >= 1.8 and abs(snap_sh / last_sh - round(snap_sh / last_sh)) < 0.15:
                sf = float(round(snap_sh / last_sh))       # a split since the last filing
            uni[t] = {"years": h["years"], "dates": td.ohlcv["dates"], "closes": td.ohlcv["close"],
                      "split_factor": sf}
        bench = {"dates": spy.ohlcv["dates"], "closes": spy.ohlcv["close"]}
        out = {"ok": True, "stocks": len(uni),
               "normalized": evaluate(observations(uni, bench, "normalized")),
               "one_year": evaluate(observations(uni, bench, "one_year"))}
        _VBT_CACHE["v"] = (_t.time(), out)
        return jsonify(out)

    _SIG_CACHE: dict = {}

    @app.get("/api/signals/<ticker>")
    def extra_signals(ticker: str):
        """Insider trades (Form 4), short interest and accounting quality."""
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        import time as _t
        from concurrent.futures import ThreadPoolExecutor
        from ..data import signals_extra as X
        from ..signals.insiders import summarize
        from ..valuation.quality import quality_read
        tk = ticker.upper()
        hit = _SIG_CACHE.get(tk)
        if hit and _t.time() - hit[0] < 6 * 3600:
            return jsonify(hit[1])

        def safe(fn):
            try:
                return fn(tk)
            except Exception:  # noqa: BLE001
                return None
        with ThreadPoolExecutor(max_workers=3) as ex:
            f_ins, f_si, f_st = (ex.submit(safe, fn) for fn in
                                 (X.insider_trades, X.short_interest, X.annual_statements))
            trades, si, st = f_ins.result(), f_si.result(), f_st.result()
        out = {"ticker": tk,
               "insiders": summarize(trades) if trades is not None else None,
               "short": si,
               "quality": quality_read(*st) if st else None}
        if any(out[k] is not None for k in ("insiders", "short", "quality")):
            _SIG_CACHE[tk] = (_t.time(), out)
        return jsonify(out)

    _OPT_CACHE: dict = {}

    @app.get("/api/options/<ticker>")
    def options_moves(ticker: str):
        """Options-implied expected moves (next week / ~month / through earnings)."""
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        import time as _t
        from ..data.options import expected_moves
        from ..watchlist.pipeline import fetch_one
        tk = ticker.upper()
        hit = _OPT_CACHE.get(tk)
        if hit and _t.time() - hit[0] < 600:
            return jsonify(hit[1])
        td = fetch_one(tk, period=period, cache_dir=cache_dir, ttl=cache_ttl)
        spot = None
        try:
            from ..data import finnhub
            q = finnhub.quote(tk) if finnhub.has_finnhub() else None
            spot = q["price"] if q else None
        except Exception:  # noqa: BLE001
            spot = None
        closes = (td.ohlcv or {}).get("close") or []
        spot = spot or (closes[-1] if closes else None)
        if not spot:
            return jsonify({"available": False, "moves": [], "note": "no price"}), 404
        earn = td.snapshot.next_earnings if td.snapshot else None
        out = expected_moves(tk, float(spot), earn)
        out.update({"ticker": tk, "spot": spot, "next_earnings": earn})
        if out.get("available"):
            _OPT_CACHE[tk] = (_t.time(), out)
        return jsonify(out)

    _IDEA_CACHE: dict = {}

    @app.get("/api/option-ideas/<ticker>")
    def option_ideas_api(ticker: str):
        """Priced option trade ideas for the ~35-day expiry (Yahoo chain)."""
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        import time as _t
        from ..data.options import chain_near
        from ..trade.expected_move import straddle_move
        from ..trade.option_ideas import ideas, nearest, view_from
        from ..watchlist import build_row
        from ..watchlist.pipeline import fetch_one
        from ..watchlist.row import earnings_days
        tk = ticker.upper()
        hit = _IDEA_CACHE.get(tk)
        if hit and _t.time() - hit[0] < 600:
            return jsonify(hit[1])
        td = fetch_one(tk, period=period, cache_dir=cache_dir, ttl=cache_ttl)
        closes = (td.ohlcv or {}).get("close") or []
        if not closes:
            return jsonify({"ok": False, "error": "no price history"}), 404
        spot = closes[-1]
        try:
            from ..data import finnhub
            q = finnhub.quote(tk) if finnhub.has_finnhub() else None
            spot = (q or {}).get("price") or spot
        except Exception:  # noqa: BLE001
            pass
        ch = chain_near(tk, spot)
        if not ch or not ch["calls"] or not ch["puts"]:
            return jsonify({"ok": False, "error": "no listed options near a month out"}), 404
        c0, p0 = nearest(ch["calls"], spot), nearest(ch["puts"], spot)
        mv = straddle_move(spot, c0["price"], p0["price"], ch["days"]) if (c0 and p0) else None
        iv = mv["iv"] if mv else None
        row = build_row(td)
        rv = row.vol_annual
        view = view_from(row.trend_score, (row.regime or {}).get("p_bull"))
        ed = earnings_days(td.snapshot.next_earnings if td.snapshot else None)
        earn = ed is not None and ed <= ch["days"]
        out = {"ok": True, "ticker": tk, "spot": spot, "expiry": ch["expiry"], "days": ch["days"],
               "iv": iv, "rv": rv, "view": view, "earnings_before_expiry": earn, "stale": ch["stale"],
               "ideas": ideas(ch["calls"], ch["puts"], spot, iv, rv, ch["days"], view, earn) if iv else []}
        _IDEA_CACHE[tk] = (_t.time(), out)
        return jsonify(out)

    @app.get("/api/forecast/<ticker>")
    def forecast_api(ticker: str):
        """Price-range forecast (1/3/6/12 months) and its historical coverage."""
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        from ..trade.forecast import cone, coverage, ranges, realized_vol
        from ..watchlist.pipeline import fetch_one
        tk = ticker.upper()
        td = fetch_one(tk, period=period, cache_dir=cache_dir, ttl=cache_ttl)
        closes = (td.ohlcv or {}).get("close") or []
        if len(closes) < 60:
            return jsonify({"ok": False, "error": "not enough price history"}), 404
        spot = closes[-1]
        rv = realized_vol(closes)
        iv, src = None, "realized"
        cached = _OPT_CACHE.get(tk) or _IDEA_CACHE.get(tk)
        if cached:
            d = cached[1]
            iv = d.get("iv") or next((m.get("iv") for m in d.get("moves", []) if m.get("label", "").startswith("About")), None)
        if iv:
            src = "implied"
        sigma = iv or rv
        if not sigma:
            return jsonify({"ok": False, "error": "no volatility estimate"}), 404
        return jsonify({"ok": True, "ticker": tk, "spot": spot, "sigma": sigma, "source": src,
                        "iv": iv, "rv": rv, "ranges": ranges(spot, sigma), "cone": cone(spot, sigma),
                        "coverage": coverage(closes)})

    @app.get("/api/ohlc/<ticker>")
    def ohlc(ticker: str):
        """Candlestick bars from the cached history (weekly for long periods)."""
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        per = request.args.get("period", "1y")
        from ..technicals.candles import PERIOD_BARS, chart_bars
        from ..watchlist.pipeline import fetch_one
        if per not in PERIOD_BARS:
            per = "1y"
        td = fetch_one(ticker.upper(), period=period, cache_dir=cache_dir, ttl=cache_ttl)
        o = td.ohlcv or {}
        if len(o.get("close") or []) < 5:
            return jsonify({"error": f"no price history for {ticker.upper()}"}), 404
        bars = chart_bars(o, per)
        bars.update({"ticker": ticker.upper(), "period": per})
        return jsonify(bars)

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
            "open": [round(x, 4) for x in (o.get("open") or [])],
            "high": [round(x, 4) for x in highs], "low": [round(x, 4) for x in lows],
            "sma20": S.sma_series(closes, 20), "sma50": S.sma_series(closes, 50),
            "bb_upper": up, "bb_mid": mid, "bb_lower": lo,
            "rsi": S.rsi_series(closes), "macd": macd_line, "signal": sig, "hist": hist,
            "atr": S.atr_series(highs, lows, closes),
            "stoch_k": k, "stoch_d": dk,
            "adx": adx, "plus_di": plus_di, "minus_di": minus_di,
            "obv": S.obv_series(closes, vols),
            "ichimoku": ich,
        })

    _BO_CACHE: dict = {}

    @app.get("/breakouts")
    def breakouts_page():
        from .breakouts_page import breakouts_html
        return breakouts_html()

    @app.get("/api/breakouts")
    def breakouts_api():
        """Today's breakouts on the watchlist and how breakouts have done here
        (cache-only, no network; refreshed every 30 minutes)."""
        import time as _t
        hit = _BO_CACHE.get("v")
        if hit and _t.time() - hit[0] < 1800:
            return jsonify(hit[1])
        from ..leverage import registry
        from ..signals import breakouts as BK
        from ..watchlist.pipeline import _load_cached
        from ..watchlist.tickers import parse_tickers
        spy = _load_cached(cache_dir, "SPY") if cache_dir else None
        try:
            tks = [t for t in parse_tickers(tickers_path)["all"] if registry.get(t) is None]
        except Exception:  # noqa: BLE001
            tks = []
        uni, last = {}, ""
        for t in tks:
            td = _load_cached(cache_dir, t) if cache_dir else None
            o = (td.ohlcv if td else None) or {}
            if not o.get("close"):
                continue
            uni[t] = {"close": o["close"], "high": o.get("high"), "volume": o.get("volume"),
                      "bench": (BK.bench_on(o["dates"], spy.ohlcv["dates"], spy.ohlcv["close"]) if spy else None)}
            d = o["dates"][-1]
            last = max(last, d.isoformat() if hasattr(d, "isoformat") else str(d))
        if not uni:
            return jsonify({"ok": False, "error": "no cached price history yet"}), 503
        bt = BK.backtest(uni)
        n_days = max(len(u["close"]) for u in uni.values())
        bt["years"] = round((n_days - 252 - 60) / 252, 1)
        out = {"ok": True, "as_of": last, "universe": len(uni), "candidates": BK.scan(uni), "backtest": bt}
        _BO_CACHE["v"] = (_t.time(), out)
        return jsonify(out)

    @app.get("/trades")
    def trades_page():
        from .trades_page import trades_html
        return trades_html(request.args.get("q", ""))

    @app.get("/api/congress")
    def congress_api():
        """Recent Congress stock trades (House + Senate PTRs), filterable."""
        from ..data.congress import recent_trades
        data = recent_trades(cache_dir)
        tr = data.get("trades") or []
        tk = (request.args.get("ticker") or "").upper().strip()
        who = (request.args.get("member") or "").lower().strip()
        ch = request.args.get("chamber") or ""
        kind = request.args.get("type") or ""
        window = request.args.get("days", type=int) or (730 if (tk or who) else 90)
        from datetime import date as _date, timedelta as _td
        since = (_date.today() - _td(days=window)).isoformat()
        tr = [t for t in tr if (t.get("filed") or "") >= since]
        recent = [t for t in (data.get("trades") or []) if (t.get("filed") or "") >= (_date.today() - _td(days=90)).isoformat()]
        if tk:
            tr = [t for t in tr if (t.get("ticker") or "") == tk]
        if who:
            tr = [t for t in tr if who in (t.get("member") or "").lower()]
        if ch in ("House", "Senate", "President"):
            tr = [t for t in tr if t.get("chamber") == ch]
        if kind == "buy":
            tr = [t for t in tr if (t.get("type") or "").startswith("Buy")]
        elif kind == "sell":
            tr = [t for t in tr if (t.get("type") or "").startswith("Sell")]
        from collections import Counter
        bought = Counter(t["ticker"] for t in recent
                         if t.get("ticker") and (t.get("type") or "").startswith("Buy"))
        members = Counter(t["member"] for t in recent)
        for t in tr[:400]:
            t["member_id"] = _member_id(t)
        return jsonify({"ok": True, "loading": data.get("loading"), "as_of": data.get("as_of"),
                        "days": window, "total": len(tr), "trades": tr[:400],
                        "most_bought": bought.most_common(12), "most_active": members.most_common(10)})

    _MEMBERS: dict = {"list": None, "t": 0.0, "map": {}}

    def _members():
        import time as _t
        from ..data.politicians import directory
        if _MEMBERS["list"] is None or _t.time() - _MEMBERS["t"] > 86400:
            _MEMBERS["list"] = directory(cache_dir)
            _MEMBERS["t"] = _t.time()
            _MEMBERS["map"] = {}
        return _MEMBERS["list"]

    def _member_id(t: dict) -> str | None:
        """Directory id for a trade's filer (the President is "trump")."""
        from ..data.politicians import TRUMP_ID, match_member
        if t.get("chamber") == "President":
            return TRUMP_ID
        key = (t.get("chamber"), t.get("member"), t.get("state"))
        mp = _MEMBERS["map"]
        if key not in mp:
            m = match_member(t.get("member") or "", t.get("chamber") or "", t.get("state") or "", _members())
            mp[key] = m["id"] if m else None
        return mp[key]

    def _person(pid: str):
        from ..data.politicians import TRUMP, TRUMP_ID
        if pid == TRUMP_ID:
            return TRUMP
        return next((m for m in _members() if m["id"] == pid), None)

    @app.get("/api/politicians")
    def politicians_api():
        """Everyone with reported trades in the window (default 1 year), with
        party, office, time in office, photo and trade counts. The President first."""
        from collections import Counter
        from datetime import date as _date, timedelta as _td
        from ..data.congress import recent_trades
        from ..data.politicians import TRUMP_ID
        days = request.args.get("days", type=int) or 365
        since = (_date.today() - _td(days=days)).isoformat()
        data = recent_trades(cache_dir)
        counts, last = Counter(), {}
        for t in data.get("trades") or []:
            if (t.get("filed") or "") < since:
                continue
            pid = _member_id(t)
            if pid:
                counts[pid] += 1
                last[pid] = max(last.get(pid, ""), t.get("filed") or "")
        people = []
        for pid, n in counts.items():
            p = _person(pid)
            if p:
                people.append({**{k: p.get(k) for k in ("id", "name", "party", "chamber", "state", "district",
                                                         "since", "photo", "office")},
                               "trades": n, "last_filed": last.get(pid)})
        people.sort(key=lambda p: (p["id"] != TRUMP_ID, -p["trades"]))
        return jsonify({"ok": True, "loading": data.get("loading"), "days": days, "people": people})

    @app.get("/politician/<pid>")
    def politician_page(pid: str):
        from .politician_page import politician_html
        return politician_html(pid)

    @app.get("/api/politician/<pid>")
    def politician_api(pid: str):
        """Profile: who they are, their trades, estimated positions, stats."""
        from ..data.congress import recent_trades
        from ..signals.politician import positions, stats
        p = _person(pid)
        if not p:
            return jsonify({"ok": False, "error": "unknown politician"}), 404
        tr = [t for t in (recent_trades(cache_dir).get("trades") or []) if _member_id(t) == pid]
        tr.sort(key=lambda t: (t.get("traded") or "", t.get("filed") or ""), reverse=True)
        extra = {}
        if pid == "trump":
            from ..data.politicians import trump_coverage
            extra["coverage"] = trump_coverage(cache_dir)
        return jsonify({"ok": True, "person": p, "stats": stats(tr), "positions": positions(tr)[:40],
                        "trades": tr[:1500], "total": len(tr), **extra})

    _PERF: dict = {}

    @app.get("/api/politician/<pid>/performance")
    def politician_perf(pid: str):
        """Copy-their-trades performance vs the S&P 500 (prices for the most
        traded tickers are fetched in the background the first time)."""
        import threading
        import time as _t
        from ..data.congress import recent_trades
        hit = _PERF.get(pid)
        if hit and (hit.get("running") or _t.time() - hit.get("t", 0) < 6 * 3600):
            return jsonify(hit.get("result") or {"ok": True, "working": True})
        p = _person(pid)
        if not p:
            return jsonify({"ok": False, "error": "unknown politician"}), 404
        tr = [t for t in (recent_trades(cache_dir).get("trades") or []) if _member_id(t) == pid]

        def run():
            from collections import Counter
            from ..performance.benchmarks import load_benchmarks
            from ..signals.politician import committee_overlap, simulate
            from ..watchlist.pipeline import fetch_one
            try:
                top = [tk for tk, _ in Counter(t["ticker"] for t in tr if t.get("ticker")).most_common(40)]
                prices, sectors = {}, {}
                for tk in top:
                    try:
                        td = fetch_one(tk, period="5y", cache_dir=cache_dir, ttl=cache_ttl)
                    except Exception:  # noqa: BLE001
                        continue
                    o = td.ohlcv or {}
                    if o.get("close"):
                        prices[tk] = ([d.isoformat() if hasattr(d, "isoformat") else str(d) for d in o["dates"]],
                                      o["close"])
                    if td.snapshot and td.snapshot.sector:
                        sectors[tk] = td.snapshot.sector
                spy = load_benchmarks(cache_dir, period, cache_ttl, fetch=True).get("SPY")
                bench = ([d.isoformat() for d in spy.ohlcv["dates"]], spy.ohlcv["close"]) if spy else None
                sim = simulate(tr, prices, bench) if bench else None
                over = committee_overlap(tr, p.get("committees") or [], sectors)
                _PERF[pid] = {"t": _t.time(), "running": False,
                              "result": {"ok": True, "working": False, "performance": sim,
                                         "priced_tickers": len(prices), "committee_trades": over[:50],
                                         "sectors": sectors}}
            except Exception as e:  # noqa: BLE001
                _PERF[pid] = {"t": _t.time(), "running": False, "result": {"ok": False, "error": str(e)}}
        _PERF[pid] = {"running": True, "t": _t.time()}
        threading.Thread(target=run, daemon=True).start()
        return jsonify({"ok": True, "working": True})

    @app.get("/financials")
    def financials_page():
        from .financials_page import financials_html
        return financials_html(request.args.get("t", ""))

    @app.get("/api/financials/<ticker>")
    def financials_api(ticker: str):
        """Ten fiscal years of statements and ratios from SEC 10-K XBRL."""
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        from ..data import financials as FIN
        from ..data import sec as SEC
        tk = ticker.upper()
        if not SEC.has_sec():
            return jsonify({"ok": False, "error": "SEC data is not configured on this server."})
        try:
            d = FIN.statements(tk, cache_dir)
        except Exception:  # noqa: BLE001
            d = None
        if not d:
            return jsonify({"ok": False, "error": f"No US-GAAP annual filings found for {tk} "
                                                  "(ETFs, funds and foreign filers don't file them)."})
        return jsonify({"ok": True, "ticker": tk, "name": d.get("name"), "years": d["years"],
                        "cagr": d.get("cagr"), "splits": d.get("splits"),
                        "layout": {k: [list(x) for x in v] for k, v in FIN.LAYOUT.items()},
                        "source": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={d.get('cik')}&type=10-K"})

    _EARN: dict = {}

    def _earn_company(tk: str, with_finnhub: bool = True) -> dict:
        """Releases with reactions (+ surprises/next/ratings when asked)."""
        from ..data import earnings as E
        from ..watchlist.pipeline import _load_cached
        td = _load_cached(cache_dir, tk) if cache_dir else None
        spy = _load_cached(cache_dir, "SPY") if cache_dir else None
        rel = E.releases(tk, cache_dir) or []
        surp = E.surprises(tk) if with_finnhub else []
        hist = E.history(rel, td.ohlcv if td else None, spy.ohlcv if spy else None, surp)
        timings = [r["timing"] for r in rel[:8]]
        usual = max(set(timings), key=timings.count) if timings else None
        out = {"ticker": tk, "name": (td.snapshot.name if td and td.snapshot and td.snapshot.name else tk),
               "history": hist, "stats": E.stats(hist, surp), "usual_timing": usual}
        if with_finnhub:
            out["next"] = E.upcoming(tk)
            out["ratings"] = E.recommendations(tk)
            if not out["next"] and td and td.snapshot and td.snapshot.next_earnings:
                out["next"] = {"date": td.snapshot.next_earnings, "timing": None}
        return out

    @app.get("/earnings")
    def earnings_page():
        from .earnings_page import earnings_html
        return earnings_html(request.args.get("t", ""))

    @app.get("/api/earnings/calendar")
    def earnings_calendar_api():
        """Watchlist companies reporting in the next five weeks, with how the
        stock has typically moved on its past reports."""
        import time as _t
        from concurrent.futures import ThreadPoolExecutor
        from ..data import earnings as E
        from ..data import finnhub
        from ..watchlist.tickers import parse_tickers
        hit = _EARN.get("_cal")
        if hit and _t.time() - hit[0] < 6 * 3600:
            return jsonify(hit[1])
        if not finnhub.has_finnhub():
            return jsonify({"ok": False, "error": "The earnings calendar needs a Finnhub key on this server."})
        try:
            wl = parse_tickers(tickers_path)["all"]
        except Exception:  # noqa: BLE001
            wl = []
        rows = E.calendar(wl, 35)

        def enrich(r):
            try:
                c = _earn_company(r["ticker"], with_finnhub=False)
            except Exception:  # noqa: BLE001
                c = {}
            st = c.get("stats") or {}
            return {**r, "name": c.get("name") or r["ticker"], "usual_timing": c.get("usual_timing"),
                    "avg_move": st.get("avg_abs_move"), "n": st.get("n"), "up": st.get("up")}

        with ThreadPoolExecutor(max_workers=4) as ex:
            rows = list(ex.map(enrich, rows))
        res = {"ok": True, "rows": rows}
        _EARN["_cal"] = (_t.time(), res)
        return jsonify(res)

    @app.get("/api/earnings/<ticker>")
    def earnings_api(ticker: str):
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        import time as _t
        tk = ticker.upper()
        hit = _EARN.get(tk)
        if hit and _t.time() - hit[0] < 6 * 3600:
            return jsonify(hit[1])
        res = {"ok": True, **_earn_company(tk)}
        if not res["history"] and not res.get("next"):
            return jsonify({"ok": False, "error": f"No earnings reports found for {tk} (ETFs and funds don't report)."})
        _EARN[tk] = (_t.time(), res)
        return jsonify(res)

    _GRAPH: dict = {}

    @app.get("/graph")
    def graph_page():
        from .graph_page import graph_html
        return graph_html(request.args.get("t", ""))

    @app.get("/api/graph/<ticker>")
    def graph_api(ticker: str):
        """Knowledge graph for one company: suppliers, customers, investments
        (its own 13F), competitors (SEC industry peers) and filing mentions."""
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        import time as _t
        tk = ticker.upper()
        hit = _GRAPH.get(tk)
        if hit and _t.time() - hit[0] < 6 * 3600:
            return jsonify(hit[1])
        from ..data import funds13f as F
        from ..data import graph as G
        from ..data import sec as SEC
        from ..leverage import registry
        from ..valuation.peers import group_of
        from ..watchlist.pipeline import _load_cached
        from ..watchlist.tickers import parse_tickers
        rel = G.load_relationships()
        out = G.neighbors(tk, rel)
        td = _load_cached(cache_dir, tk) if cache_dir else None
        snap = td.snapshot if td else None
        hist = SEC.annual_history(tk, cache_dir, offline=True) or {}
        name = (snap.name if snap and snap.name else None) or hist.get("name") or tk
        # stakes it holds, from its own 13F (if it files one)
        cik = SEC.cik_for(tk, cache_dir, offline=True)
        if cik:
            try:
                rep = F.fund_report(cik, cache_dir, top=15)
            except Exception:  # noqa: BLE001
                rep = None
            for h in (rep or {}).get("holdings", [])[:12]:
                if h.get("put_call"):
                    continue
                out["investments"].append({"ticker": h.get("ticker"), "name": h.get("name", "").title(),
                                           "what": f"${h['value']/1e6:,.0f}M stake ({h.get('change', '').lower()})",
                                           "basis": f"its 13F, quarter ended {rep.get('period')}", "source": "13F"})
        # customers that are 10%+ of revenue, from its latest 10-K (XBRL tags)
        out["customer_note"] = None
        try:
            from ..data.customers import major_customers
            from ..data.politicians import name_index, ticker_for
            mc = major_customers(tk, cache_dir)
        except Exception:  # noqa: BLE001
            mc = None
        if mc and mc.get("customers"):
            idx = None
            fy = (mc.get("period_end") or "")[:7]
            for c in mc["customers"][:8]:
                ctk = None
                if not c["anonymous"]:
                    idx = idx if idx is not None else name_index(cache_dir)
                    ctk = ticker_for(c["label"], idx)
                seg = " " + c["segment"].replace(" Segment", "").replace(" And ", " & ") if c.get("segment") else ""
                what = f"{c['pct']*100:.0f}% of{seg} revenue" + (" (not named in the filing)" if c["anonymous"] else "")
                hit_ = next((x for x in out["customers"] if ctk and x.get("ticker") == ctk), None)
                if hit_:
                    hit_["what"] += f"; {c['pct']*100:.0f}% of revenue per its 10-K"
                    continue
                out["customers"].append({"ticker": ctk, "name": c["label"], "short": c["short"], "what": what,
                                         "pct": round(c["pct"] * 100), "basis": f"its 10-K, year to {fy}",
                                         "url": mc.get("url"), "source": "10-K"})
            # filed figures first, so the graph's capped column always shows them
            out["customers"].sort(key=lambda x: x.get("source") != "10-K")
        elif mc is not None and not mc.get("none_filed"):
            out["customer_note"] = "No single customer is 10% or more of revenue in its latest 10-K (a diversified customer base)."
        # competitors: watchlist peers in the same SEC industry
        try:
            wl = [t for t in parse_tickers(tickers_path)["all"] if registry.get(t) is None]
        except Exception:  # noqa: BLE001
            wl = []
        sics, ciks = {}, {}
        for t in wl:
            h = SEC.annual_history(t, cache_dir, offline=True)
            if h and h.get("sic"):
                sics[t] = h["sic"]
            c = SEC.cik_for(t, cache_dir, offline=True)
            if c:
                ciks[c] = t
        if hist.get("sic"):
            sics[tk] = hist["sic"]
        members, pre = group_of(tk, sics)
        out["competitors"] = [{"ticker": t, "name": t, "what": f"Same industry ({hist.get('sic_desc') or pre})",
                               "basis": "SEC industry code", "source": "peers"} for t in members if t != tk][:10]
        try:
            ciks.pop(cik, None)
            out["mentions"] = G.filing_mentions(name, ciks, cache_dir)
        except Exception:  # noqa: BLE001
            out["mentions"] = []
        # fill in names for watchlist tickers
        for grp in out.values():
            if not isinstance(grp, list):
                continue
            for n in grp:
                t2 = n.get("ticker")
                if t2 and (n.get("name") in (None, "", t2)):
                    s2 = _load_cached(cache_dir, t2) if cache_dir else None
                    n["name"] = (s2.snapshot.name if s2 and s2.snapshot and s2.snapshot.name else t2)
                n["on_watchlist"] = bool(t2 and t2 in wl)
        res = {"ok": True, "ticker": tk, "name": name, "sector": snap.sector if snap else None, **out}
        _GRAPH[tk] = (_t.time(), res)
        return jsonify(res)

    @app.get("/api/funds")
    def funds_api():
        from ..data import funds13f as F
        F.warm_all(cache_dir)
        return jsonify({"ok": True, "funds": F.summaries(cache_dir), "warming": F._WARM["running"]})

    @app.get("/api/funds/search")
    def funds_search():
        from ..data import funds13f as F
        return jsonify({"ok": True, "results": F.search_filers(request.args.get("q", ""))})

    @app.get("/api/funds/<int:cik>")
    def fund_detail(cik: int):
        from ..data import funds13f as F
        rep = F.fund_report(cik, cache_dir)
        if not rep:
            return jsonify({"ok": False, "error": "no 13F filings found for that filer"}), 404
        return jsonify({"ok": True, **rep})

    @app.get("/api/holders/<ticker>")
    def holders_api(ticker: str):
        """Tracked funds holding a ticker, and Congress trades in it."""
        if not _TICKER_RE.match(ticker):
            return jsonify({"error": "invalid ticker"}), 400
        from ..data import funds13f as F
        from ..data.congress import recent_trades
        tk = ticker.upper()
        tr = [t for t in (recent_trades(cache_dir).get("trades") or []) if t.get("ticker") == tk]
        return jsonify({"ok": True, "ticker": tk, "funds": F.holders_of(tk, cache_dir), "congress": tr[:25]})

    @app.get("/ipos")
    def ipos_page():
        from .ipos_page import ipos_html
        return ipos_html()

    @app.get("/api/ipos")
    def ipos_api():
        from ..data.ipo import calendar
        try:
            cal = calendar()
        except Exception:  # noqa: BLE001
            cal = None
        if cal is None:
            return jsonify({"ok": False, "error": "IPO calendar needs a Finnhub key (FINNHUB_API_KEY)"}), 503
        return jsonify({"ok": True, **cal})

    @app.get("/compare")
    def compare_page():
        from .compare_page import compare_html
        return compare_html(request.args.get("t", ""))

    def _compare_tickers():
        raw = request.args.get("t", "")
        tks = []
        for t in re.split(r"[\s,;]+", raw.upper()):
            if t and _TICKER_RE.match(t) and t not in tks:
                tks.append(t)
        return tks

    def _fetch_many(tks):
        from concurrent.futures import ThreadPoolExecutor
        from ..watchlist.pipeline import fetch_one
        with ThreadPoolExecutor(max_workers=4) as ex:
            got = list(ex.map(lambda t: fetch_one(t, period=period, cache_dir=cache_dir,
                                                  ttl=cache_ttl), tks))
        return dict(zip(tks, got))

    @app.get("/api/compare")
    def compare_api():
        from ..leverage import registry
        from ..performance.benchmarks import load_benchmarks
        from ..performance.compare import compare
        tks = _compare_tickers()
        if not 2 <= len(tks) <= 4:
            return jsonify({"ok": False, "error": "pick 2 to 4 tickers"}), 400
        per = request.args.get("period", "5y")
        if per not in ("1y", "3y", "5y", "max"):
            per = "5y"
        data = _fetch_many(tks)
        missing = [t for t, td in data.items() if not (td and (td.ohlcv or {}).get("close"))]
        if missing:
            return jsonify({"ok": False, "error": f"no price data for {', '.join(missing)}"}), 404
        series = {t: {"dates": td.ohlcv["dates"], "closes": td.ohlcv["close"]}
                  for t, td in data.items()}
        spy = load_benchmarks(cache_dir, period, cache_ttl, fetch=True, have=data).get("SPY")
        bench = ({"dates": spy.ohlcv["dates"], "closes": spy.ohlcv["close"]} if spy else None)
        out = compare(series, period=per, bench=bench)
        if not out.get("ok"):
            return jsonify(out), 422
        profiles = []
        for t, td in data.items():
            s = td.snapshot
            lev = registry.get(t)
            price = td.ohlcv["close"][-1]
            profiles.append({
                "ticker": t, "name": (s.name if s else None) or (lev.name if lev else t),
                "type": ("Leveraged " + lev.structure) if lev else
                        {"EQUITY": "Stock", "ETF": "ETF", "MUTUALFUND": "Mutual fund"}.get(
                            ((s.quote_type or "") if s else "").upper(), (s.quote_type or "") if s else ""),
                "sector": s.sector if s else None,
                "market_cap": s.market_cap if s else None,
                "pe": (price / s.eps) if (s and s.eps and s.eps > 0) else None,
                "dividend_yield": (s.dividend_annual / price) if (s and s.dividend_annual and price) else None,
                "leverage": lev.multiplier if lev else None,
                "expense_ratio": (lev.expense_ratio or None) if lev else None,
            })
        out["profiles"] = profiles
        if len(tks) == 2:                 # a pair: the spread's z-score over time
            from ..performance.metrics import align_closes
            from ..signals.pairs import spread_z_series
            a_, b_ = tks
            d_, ca, cb = align_closes(series[a_]["dates"], series[a_]["closes"],
                                      series[b_]["dates"], series[b_]["closes"])
            z = spread_z_series(ca, cb)
            keep = [i for i, d in enumerate(d_) if d >= out["start"]]
            if keep:
                step = max(1, len(keep) // 420)
                idx = keep[::step] + ([keep[-1]] if keep[-1] not in keep[::step] else [])
                out["pair"] = {"a": a_, "b": b_, "dates": [d_[i] for i in idx],
                               "z": [None if z[i] is None else round(z[i], 3) for i in idx],
                               "z_now": z[-1]}
        return jsonify(out)

    _PAIRS_CACHE: dict = {}
    _PAIR_EXCLUDE = {"LEVERAGED", "LEVERAGED-BEAR", "DOW", "NASDAQ100", "TICKERS", "ADDED"}

    def _pair_universe():
        """{ticker: industry section} for plain stocks on the board, and their
        closes aligned to SPY's dates. Read from the cache only (no network)."""
        from ..leverage import registry
        from ..signals.pairs import align_to
        from ..watchlist.pipeline import _load_cached
        from ..watchlist.tickers import parse_tickers
        groups = {}
        try:
            parsed = parse_tickers(tickers_path)
        except Exception:  # noqa: BLE001
            return {}, {}
        for sec, tks in parsed["sections"].items():
            if sec.upper() in _PAIR_EXCLUDE:
                continue
            for t in tks:
                if registry.get(t) is None:
                    groups.setdefault(t, sec)
        spy = _load_cached(cache_dir, "SPY") if cache_dir else None
        if not spy:
            return groups, {}
        series = {}
        for t in groups:
            td = _load_cached(cache_dir, t)
            if td and (td.ohlcv or {}).get("close"):
                series[t] = (td.ohlcv["dates"], td.ohlcv["close"])
        return groups, align_to(spy.ohlcv["dates"], series)

    @app.get("/api/pairs")
    def pairs_api():
        """Pairs on the watchlist that have drifted apart, plus how the classic
        pairs rule actually did on this watchlist's history."""
        import time as _t
        from ..signals.pairs import backtest, stretched_now
        hit = _PAIRS_CACHE.get("v")
        if hit and _t.time() - hit[0] < 12 * 3600:
            return jsonify(hit[1])
        groups, closes = _pair_universe()
        if not closes:
            return jsonify({"ok": False, "error": "no cached price history yet"}), 503
        out = {"ok": True, "pairs": [x for x in stretched_now(closes, groups, top=30)][:12],
               "backtest": backtest(closes, groups, top=20)}
        _PAIRS_CACHE["v"] = (_t.time(), out)
        return jsonify(out)

    @app.get("/api/compare/holdings")
    def compare_holdings():
        from ..data.funds import etf_holdings
        from ..leverage import registry
        from ..performance.compare import holdings_overlap
        tks = _compare_tickers()[:4]
        if not tks:
            return jsonify({"ok": False, "error": "no tickers"}), 400
        data = _fetch_many(tks)
        funds, weights = [], {}
        for t in tks:
            lev = registry.get(t)
            snap = (data.get(t) or None) and data[t].snapshot
            qt = ((snap.quote_type if snap else "") or "").upper()
            if lev:
                w = lev.normalized_constituents()
                kind = "single" if lev.kind == "single" else "basket"
                note = (f"{lev.multiplier:g}x daily exposure to "
                        + ("one stock" if kind == "single" else "this basket"))
                sectors = None
            elif qt in ("ETF", "MUTUALFUND"):
                eh = etf_holdings(t, limit=10)
                w = {h["underlying"]: h["weight"] for h in (eh or {}).get("holdings", [])}
                kind, note = "etf", "Top holdings (the rest of the fund isn't shown)"
                sectors = (eh or {}).get("sectors")
            else:
                w, kind, note, sectors = {t: 1.0}, "stock", "A single company", None
            weights[t] = w
            top = sorted(w.items(), key=lambda kv: kv[1], reverse=True)[:10]
            funds.append({"ticker": t, "kind": kind, "note": note,
                          "multiplier": lev.multiplier if lev else 1.0,
                          "holdings": [{"underlying": u, "weight": x} for u, x in top],
                          "sectors": sectors, "available": bool(w)})
        return jsonify({"ok": True, "funds": funds, "overlap": holdings_overlap(weights)})

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
