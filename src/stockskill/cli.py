"""Command-line entry points. Every command prints numbers computed by the
tested library functions -- the CLI only formats, it never does math.

    stockskill value TICKER [--growth 0.08] [--snapshot file.json] [--save f.json]
    stockskill portfolio [--holdings holdings.csv]
    stockskill lookthrough [--holdings holdings.csv]
    stockskill decay --multiplier 3 [--vol 0.45] [--drift 0.12] [--days 252]
                     [--ticker FNGU]   # replay a real 1y path instead
"""

from __future__ import annotations

import argparse
import sys

from .config import FACTOR_GROUPS


def _fmt_money(x: float) -> str:
    return f"${x:,.0f}"


def _fmt_pct(x: float) -> str:
    return "n/a" if x != x else f"{x:+.1%}"


# --------------------------------------------------------------------------- #
# value
# --------------------------------------------------------------------------- #
def cmd_value(args: argparse.Namespace) -> int:
    from .data.fundamentals import FundamentalSnapshot, fetch_snapshot
    from .valuation.service import Assumptions, value_snapshot

    if args.snapshot:
        snap = FundamentalSnapshot.from_json(args.snapshot)
        print(f"Loaded snapshot {snap.ticker} as of {snap.as_of} (source: {snap.source})")
    else:
        print(f"Fetching {args.ticker} ...")
        snap = fetch_snapshot(args.ticker)
        if args.save:
            snap.to_json(args.save)
            print(f"Saved snapshot -> {args.save}")

    a = Assumptions()
    if args.growth is not None:
        a.stage1_growth = args.growth
    if args.terminal is not None:
        a.terminal_growth = args.terminal
    if args.peer_pe is not None:
        a.peer_pe = args.peer_pe
    if args.peer_ps is not None:
        a.peer_ps = args.peer_ps
    if args.peer_ev_ebitda is not None:
        a.peer_ev_ebitda = args.peer_ev_ebitda

    out = value_snapshot(snap, a)
    rep = out.report

    print(f"\n=== Valuation: {rep.ticker} ===")
    print(f"Price:          {snap.price if snap.price is None else _fmt_money(snap.price)}")
    print(f"Discount rate:  {out.discount_rate:.2%}  (CAPM, beta="
          f"{snap.beta if snap.beta is not None else a.default_beta})")
    print("\nMethod estimates (fair value / share):")
    for e in rep.estimates:
        print(f"  {e.method:<10} {_fmt_money(e.fair_value):>12}   [{e.note}]")

    rng = rep.range()
    if rng:
        lo, base, hi = rng
        print(f"\nFair-value range:  {_fmt_money(lo)}  ..  {_fmt_money(hi)}")
        print(f"Blended base:      {_fmt_money(base)}")
        print(f"Margin of safety:  {_fmt_pct(rep.margin_of_safety())}  ->  {rep.verdict()}")
    if out.implied_market_growth is not None:
        print(f"\nReverse DCF: market price implies ~{out.implied_market_growth:.1%} "
              f"FCF growth for {a.stage1_years}y.")

    # DCF sensitivity: fair value across discount rate x terminal growth.
    if out.dcf_inputs is not None and not args.no_sensitivity:
        from .valuation.dcf import sensitivity_grid
        base_r = out.discount_rate
        rates = [round(base_r - 0.02, 4), round(base_r - 0.01, 4), round(base_r, 4),
                 round(base_r + 0.01, 4), round(base_r + 0.02, 4)]
        terms = [0.015, 0.02, 0.025, 0.03, 0.035]
        grid = sensitivity_grid(out.dcf_inputs, rates, terms)
        print("\nDCF sensitivity -- fair value / share (rows=discount rate, cols=terminal g):")
        print("  disc\\term  " + "".join(f"{t:>9.1%}" for t in terms))
        for r, row in zip(rates, grid):
            cells = "".join(("     n/a " if v != v else f"{v:>9,.0f}") for v in row)
            print(f"  {r:>7.2%}   {cells}")

    if out.warnings:
        print("\nNotes:")
        for w in out.warnings:
            print(f"  - {w}")
    return 0


# --------------------------------------------------------------------------- #
# lookthrough / portfolio
# --------------------------------------------------------------------------- #
def _load(args) -> list:
    from .portfolio.io import load_holdings_csv
    return load_holdings_csv(args.holdings)


def cmd_lookthrough(args: argparse.Namespace) -> int:
    from .portfolio.lookthrough import expand
    from .leverage import registry

    holdings = _load(args)
    lt = expand(holdings)

    print(f"Equity (sum of positions): {_fmt_money(lt.total_equity)}")
    print(f"Economic exposure (notional): {_fmt_money(lt.total_notional)}")
    print(f"Effective leverage: {lt.effective_leverage:.2f}x\n")
    print("Top underlying exposures (look-through):")
    weights = lt.exposure_weights()
    for ul, amt in lt.top(15):
        print(f"  {ul:<6} {_fmt_money(amt):>12}   {weights[ul]:6.1%}")

    verify = [p.ticker for p in registry.all_products().values() if p.verify]
    if verify:
        print(f"\n[!] Basket/multiplier snapshots to VERIFY vs issuer data: {', '.join(verify)}")
    return 0


def cmd_portfolio(args: argparse.Namespace) -> int:
    from .portfolio.lookthrough import expand
    from .portfolio import risk

    holdings = _load(args)
    lt = expand(holdings)
    weights = lt.exposure_weights()

    print("=== Portfolio review (look-through) ===")
    print(f"Equity: {_fmt_money(lt.total_equity)}   "
          f"Economic exposure: {_fmt_money(lt.total_notional)}   "
          f"Effective leverage: {lt.effective_leverage:.2f}x\n")

    hhi = risk.herfindahl(lt.notional_by_underlying)
    print(f"Concentration (HHI): {hhi:.3f}   "
          f"Effective # of bets: {risk.effective_number_of_bets(lt.notional_by_underlying):.1f}")
    print(f"Top-5 exposure share: {risk.top_n_concentration(lt.notional_by_underlying, 5):.1%}\n")

    print("Exposure by factor group:")
    for ge in risk.group_exposure(lt.notional_by_underlying, FACTOR_GROUPS):
        print(f"  {ge.group:<22} {_fmt_money(ge.dollars):>12}   {ge.share:6.1%}")

    print("\nBy account (equity):")
    by_acct: dict[str, float] = {}
    for h in holdings:
        by_acct[h.account or "(unlabeled)"] = by_acct.get(h.account or "(unlabeled)", 0.0) + h.market_value
    for acct, amt in sorted(by_acct.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {acct:<22} {_fmt_money(amt):>12}   {amt / lt.total_equity:6.1%}")
    return 0


# --------------------------------------------------------------------------- #
# decay
# --------------------------------------------------------------------------- #
def cmd_decay(args: argparse.Namespace) -> int:
    from .portfolio.decay import monte_carlo_decay, path_leveraged_return

    daily_fee = (args.expense or 0.0) / 252.0

    if args.ticker:
        from .data.prices import daily_returns
        rets = daily_returns(args.ticker, period=args.period)
        if not rets:
            print(f"Could not fetch returns for {args.ticker}.", file=sys.stderr)
            return 1
        res = path_leveraged_return(rets, args.multiplier, daily_fee)
        print(f"=== Real-path decay: {args.ticker} x{args.multiplier:g} "
              f"over {args.period} ({len(rets)} days) ===")
        print(f"Underlying total return:   {_fmt_pct(res.underlying_total_return)}")
        print(f"Naive {args.multiplier:g}x expectation:      {_fmt_pct(res.naive_expectation)}")
        print(f"Actual leveraged return:   {_fmt_pct(res.leveraged_actual)}")
        print(f"Volatility decay drag:     {_fmt_pct(-res.decay_drag)}")
        return 0

    mc = monte_carlo_decay(
        annual_drift=args.drift, annual_vol=args.vol, multiplier=args.multiplier,
        days=args.days, daily_fee=daily_fee, seed=args.seed,
    )
    print(f"=== Monte Carlo decay: x{args.multiplier:g}, drift={args.drift:.0%}, "
          f"vol={args.vol:.0%}, {args.days}d, seed={args.seed} ===")
    print(f"Median underlying return:   {_fmt_pct(mc.median_underlying)}")
    print(f"Median naive {args.multiplier:g}x:            {_fmt_pct(mc.median_naive)}")
    print(f"Median leveraged (actual):  {_fmt_pct(mc.median_leveraged)}")
    print(f"P(leveraged beats naive):   {mc.prob_leveraged_beats_naive:.1%}")
    print(f"P(leveraged loses money):   {mc.prob_leveraged_loss:.1%}")
    print("Leveraged return percentiles:")
    for k, v in mc.pctiles_leveraged.items():
        print(f"  {k:>4}: {_fmt_pct(v)}")
    return 0


def _load_universe(path: str) -> list[str]:
    tickers: list[str] = []
    with open(path) as f:
        for line in f:
            tok = line.strip().split(",")[0].strip()
            if not tok or tok.startswith("#") or tok.lower() == "ticker":
                continue
            tickers.append(tok.upper())
    return tickers


def cmd_screen(args: argparse.Namespace) -> int:
    import os
    from .data.fundamentals import FundamentalSnapshot, fetch_snapshot
    from .screener.screen import run_screen, LANES

    tickers = _load_universe(args.universe)
    print(f"Screening {len(tickers)} names, lane='{args.lane}' ...")

    snapshots = []
    momentum: dict[str, float] = {}
    for tk in tickers:
        snap = None
        cache = os.path.join(args.cache_dir, f"{tk}.json") if args.cache_dir else None
        if cache and os.path.exists(cache) and not args.refresh:
            snap = FundamentalSnapshot.from_json(cache)
        else:
            try:
                snap = fetch_snapshot(tk)
                if cache:
                    os.makedirs(args.cache_dir, exist_ok=True)
                    snap.to_json(cache)
            except Exception as e:  # noqa: BLE001
                print(f"  [skip] {tk}: {e}", file=sys.stderr)
                continue
        snapshots.append(snap)
        if args.momentum and args.lane == "aggressive":
            from .data.prices import daily_returns
            import numpy as np
            rets = daily_returns(tk, period=args.momentum)
            if rets:
                momentum[tk] = float(np.prod([1 + r for r in rets]) - 1.0)

    ranked = run_screen(snapshots, lane=args.lane, momentum=momentum)
    specs = [s.name for s in LANES[args.lane]]

    print(f"\n=== Screen: {args.lane} lane, top {args.top} of {len(ranked)} ===")
    print(f"{'rank':>4}  {'ticker':<7}{'score':>7}{'cov':>6}   components (best->worst normalized)")
    for i, s in enumerate(ranked[:args.top], 1):
        top_comp = sorted(
            ((k, v) for k, v in s.components.items() if v is not None),
            key=lambda kv: kv[1], reverse=True,
        )[:3]
        comp_str = ", ".join(f"{k}:{v:.2f}" for k, v in top_comp)
        print(f"{i:>4}  {s.ticker:<7}{s.score:>7.3f}{s.coverage:>6.0%}   {comp_str}")
    print(f"\nMetrics used: {', '.join(specs)}")
    print("Scores are cross-sectional percentiles within THIS universe, not "
          "absolute buy signals. Run `value TICKER` on the shortlist for depth.")
    return 0


def cmd_pulse(args: argparse.Namespace) -> int:
    import os
    from .data.prices import price_map, save_price_map, load_price_map
    from .pulse import (all_tickers, sector_table, factor_table, breadth, regime,
                        all_market_tickers, market_quotes, detect_rotation,
                        cvr3_signal, fetch_fear_greed)

    fetch_list = list(dict.fromkeys([*all_tickers(), *all_market_tickers()]))
    if args.price_map and os.path.exists(args.price_map) and not args.refresh:
        pm = load_price_map(args.price_map)
        print(f"Loaded cached price map: {args.price_map}")
    else:
        print(f"Fetching {len(fetch_list)} tickers ({args.period}) ...")
        pm = price_map(fetch_list, period=args.period)
        if args.price_map:
            save_price_map(pm, args.price_map)
            print(f"Saved price map -> {args.price_map}")

    # --- market bar ---
    print("=== Market ===")
    cells = []
    for q in market_quotes(pm):
        val = "n/a" if q.last is None else (f"{q.last:,.0f}")
        chg = "" if q.change is None else f" ({q.change:+.1%})"
        cells.append(f"{q.name} {val}{chg}")
    print("  " + "   ".join(cells))

    wins = ["1d", "1w", "1m", "3m"]
    print("\n=== Sector rotation (sorted by 1m) ===")
    print(f"  {'sector':<22}{'ticker':<7}" + "".join(f"{w:>8}" for w in wins))
    for r in sector_table(pm, "1m"):
        cells = "".join((f"{'  n/a':>8}" if r.returns[w] is None else f"{r.returns[w]:>8.1%}") for w in wins)
        print(f"  {r.name:<22}{r.ticker:<7}{cells}")

    print("\n=== Factor / style rotation (relative strength, num - den) ===")
    for r in factor_table(pm):
        cells = "".join((f"{'  n/a':>8}" if r.rs[w] is None else f"{r.rs[w]:>+8.1%}") for w in wins)
        print(f"  {r.label:<26}{r.num}/{r.den:<6}{cells}")

    b = breadth(pm)
    print("\n=== Breadth ===")
    pp = "n/a" if b.pct_positive_1m is None else f"{b.pct_positive_1m:.0%}"
    pa = "n/a" if b.pct_above_50d is None else f"{b.pct_above_50d:.0%}"
    print(f"  Sectors positive over 1m: {pp}   Sectors above 50d MA: {pa}   (n={b.n_sectors})")

    rg = regime(pm)
    print("\n=== Regime snapshot ===")
    labels = {
        "vix": "VIX", "10y_yield": "10Y yield", "3m_yield": "3M yield",
        "yield_curve_10y_3m": "Curve (10Y-3M)", "spy_1m": "S&P 500 (1m)",
        "spy_vs_rsp_1m": "Cap-weight vs equal-weight (1m)",
        "hyg_vs_lqd_1m": "HY vs IG credit (1m)",
        "growth_vs_value_1m": "Growth vs Value (1m)",
        "gold_1m": "Gold (1m)", "dollar_1m": "US Dollar (1m)",
    }
    pct_keys = {"spy_1m", "spy_vs_rsp_1m", "hyg_vs_lqd_1m", "growth_vs_value_1m", "gold_1m", "dollar_1m"}
    for k, lab in labels.items():
        v = rg.values.get(k)
        if v is None:
            disp = "n/a"
        elif k in pct_keys:
            disp = f"{v:+.1%}"
        else:
            disp = f"{v:.2f}"
        print(f"  {lab:<34}{disp:>10}")
    if rg.flags:
        on = [k for k, val in rg.flags.items() if val]
        print("  flags: " + (", ".join(on) if on else "none tripped"))

    # --- sentiment + rotation ---
    print("\n=== Sentiment & rotation ===")
    vix_series = pm.get("^VIX", [])
    print(f"  CVR3 (VIX reversal): {cvr3_signal(vix_series)}")
    fg = fetch_fear_greed()
    if fg:
        print(f"  Fear & Greed: {fg.score:.0f}/100 ({fg.rating})")
    leader = detect_rotation(pm)
    if leader:
        print(f"  Rotation leader: {leader.label} ({leader.ticker}) "
              f"3d {leader.ret_3d:+.1%}, 5d {leader.ret_5d:+.1%} (accelerating)")
    else:
        print("  Rotation leader: none (no clear momentum inflection)")

    print("\nInterpretation is yours: these are computed facts, not signals. "
          "Rising VIX + inverted curve + narrow leadership + credit risk-off "
          "together lean defensive; see references/regime-playbook.md.")
    return 0


def _compute_dashboard_data(price_map_path: str | None, period: str, refresh: bool):
    import os
    from .data.prices import price_map, save_price_map, load_price_map
    from .pulse import (all_tickers, sector_table, factor_table, breadth, regime,
                        all_market_tickers, market_quotes, detect_rotation,
                        cvr3_signal, fetch_fear_greed)

    fetch_list = list(dict.fromkeys([*all_tickers(), *all_market_tickers()]))
    if price_map_path and os.path.exists(price_map_path) and not refresh:
        pm = load_price_map(price_map_path)
    else:
        pm = price_map(fetch_list, period=period)
        if price_map_path:
            save_price_map(pm, price_map_path)

    sectors = [(r.name, r.ticker, r.returns["1d"], r.returns["1w"],
                r.returns["1m"], r.returns["3m"]) for r in sector_table(pm, "1m")]
    factors = [(r.label, r.num, r.den, r.rs["1m"]) for r in factor_table(pm)]
    b = breadth(pm)
    rg = regime(pm)

    fg = fetch_fear_greed()
    leader = detect_rotation(pm)
    market = {
        "quotes": [(q.name, q.last, q.change) for q in market_quotes(pm)],
        "cvr3": cvr3_signal(pm.get("^VIX", [])),
        "fear_greed": (fg.score, fg.rating) if fg else None,
        "rotation": (leader.label, leader.ret_3d) if leader else None,
    }
    return sectors, factors, (b.pct_positive_1m, b.pct_above_50d, b.n_sectors), rg, market


def _compute_portfolio_data(holdings_path: str):
    import os
    if not os.path.exists(holdings_path):
        return None
    from .portfolio.io import load_holdings_csv
    from .portfolio.lookthrough import expand
    from .portfolio import risk
    from .config import FACTOR_GROUPS

    lt = expand(load_holdings_csv(holdings_path))
    weights = lt.exposure_weights()
    top = [(ul, amt, weights.get(ul, 0.0)) for ul, amt in lt.top(10)]
    groups = [(ge.group, ge.dollars, ge.share)
              for ge in risk.group_exposure(lt.notional_by_underlying, FACTOR_GROUPS)]
    return {
        "effective_leverage": lt.effective_leverage,
        "total_equity": lt.total_equity,
        "total_notional": lt.total_notional,
        "top_exposures": top,
        "groups": groups,
    }


def _write_dashboard(args, refresh_seconds: int) -> str:
    from datetime import datetime
    from .marketclock import market_status, ET
    from .dashboard import render_dashboard

    status = market_status()
    sectors, factors, breadth_t, rg, market = _compute_dashboard_data(
        args.price_map, args.period, args.refresh)
    portfolio = _compute_portfolio_data(args.holdings)

    now = datetime.now(ET)
    html_out = render_dashboard(
        status=status,
        updated_et=now.strftime("%a %b %d, %I:%M %p"),
        updated_local=datetime.now().astimezone().strftime("%I:%M %p %Z"),
        refresh_seconds=refresh_seconds,
        regime_values=rg.values, regime_flags=rg.flags,
        sectors=sectors, factors=factors, breadth=breadth_t, portfolio=portfolio,
        market=market,
    )
    with open(args.out, "w") as f:
        f.write(html_out)
    return status.badge


def cmd_dashboard(args: argparse.Namespace) -> int:
    import os
    import time

    refresh_seconds = max(60, int(args.interval * 60))
    badge = _write_dashboard(args, refresh_seconds)
    print(f"[{badge}] wrote {args.out}")

    if args.open:
        os.system(f"open {args.out!r}" if sys.platform == "darwin" else f"xdg-open {args.out!r}")

    if not args.watch:
        return 0

    print(f"Watching: regenerating every {args.interval:g} min. Ctrl-C to stop.")
    try:
        while True:
            time.sleep(refresh_seconds)
            try:
                badge = _write_dashboard(args, refresh_seconds)
                print(f"[{badge}] updated {args.out} at {time.strftime('%H:%M:%S')}")
            except Exception as e:  # noqa: BLE001
                print(f"  update failed: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nstopped.")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import os
    from .server import create_app

    app = create_app()
    url = f"http://{args.host}:{args.port}"
    print(f"Stock Analyzer at {url}  (Ctrl-C to stop)")
    if args.open:
        os.system(f"open {url!r}" if sys.platform == "darwin" else f"xdg-open {url!r}")
    app.run(host=args.host, port=args.port, debug=False)
    return 0


def _refresh_seconds_for(status, base_interval: float | None) -> int:
    """Page auto-refresh cadence: fast when the market is open, slow when closed."""
    if base_interval:
        return max(15, int(base_interval * 60))
    if status.is_open:
        return 60           # ~realtime during regular hours
    if status.label in ("pre-market", "after-hours"):
        return 300
    return 1800             # closed / weekend


def _generate_watchlist(args) -> str:
    from datetime import datetime
    from .marketclock import market_status, ET
    from .signals import SignalConfig
    from .watchlist import parse_tickers, fetch_all, build_row, render_watchlist
    from .alerts import all_alerts, load_custom_alerts
    from .pulse import SECTOR_ETFS, sector_table
    from .data.prices import price_map

    parsed = parse_tickers(args.tickers)
    tickers = parsed["all"]
    tag_map: dict[str, set] = {}
    for sec, tks in parsed["sections"].items():
        for t in tks:
            tag_map.setdefault(t, set()).add(sec)

    data = fetch_all(tickers, period=args.period, workers=args.workers, cache_dir=args.cache_dir)
    cfg = SignalConfig.from_env()
    rows = [build_row(data[t], cfg, tag_map.get(t)) for t in tickers if t in data]
    alerts = all_alerts(rows, load_custom_alerts(args.alerts))

    # sector performance strip
    sec_pm = price_map(list(SECTOR_ETFS), period="3mo")
    sectors = [(r.name, r.ticker, r.returns.get("1m")) for r in sector_table(sec_pm, "1m")]

    status = market_status()
    refresh = _refresh_seconds_for(status, getattr(args, "interval", None))
    now = datetime.now(ET)
    html_out = render_watchlist(
        rows, title="Watchlist", updated=now.strftime("%a %b %d, %I:%M %p") + " ET",
        status_badge=status.badge, status_label=status.label, alerts=alerts,
        sectors=sectors, refresh_seconds=refresh)
    with open(args.out, "w") as f:
        f.write(html_out)
    ok = sum(1 for r in rows if r.price is not None)
    return f"[{status.badge}] {args.out} ({ok}/{len(rows)} tickers), reload {refresh}s"


def cmd_watchlist(args: argparse.Namespace) -> int:
    import os
    import time

    print("Fetching watchlist ...")
    print(_generate_watchlist(args))
    if args.open:
        os.system(f"open {args.out!r}" if sys.platform == "darwin" else f"xdg-open {args.out!r}")

    if not args.watch:
        return 0

    from .marketclock import market_status
    print("Watching: regenerating live (fast when market is open). Ctrl-C to stop.")
    try:
        while True:
            sleep = _refresh_seconds_for(market_status(), getattr(args, "interval", None))
            time.sleep(sleep)
            try:
                print(_generate_watchlist(args) + f"  @ {time.strftime('%H:%M:%S')}")
            except Exception as e:  # noqa: BLE001
                print(f"  update failed: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nstopped.")
    return 0


def cmd_holdings(args: argparse.Namespace) -> int:
    import os
    from .portfolio.manage import read_rows, write_rows, apply_trade, reprice
    from .data.prices import closing_prices

    if not os.path.exists(args.file):
        print(f"{args.file} not found", file=sys.stderr)
        return 1
    rows = read_rows(args.file)

    if args.action == "list":
        print(f"{'ticker':<8}{'account':<12}{'shares':>12}{'value':>14}")
        for r in sorted(rows, key=lambda x: (x.account, x.ticker)):
            sh = "" if r.shares is None else f"{r.shares:,.2f}"
            mv = "" if r.market_value is None else f"${r.market_value:,.2f}"
            print(f"{r.ticker:<8}{r.account:<12}{sh:>12}{mv:>14}")
        return 0

    _price_cache: dict = {}
    def latest(tk):
        if tk not in _price_cache:
            c = closing_prices(tk, "5d")
            _price_cache[tk] = c[-1] if c else None
        return _price_cache[tk]

    if args.action == "reprice":
        n = reprice(rows, latest)
        write_rows(args.file, rows)
        print(f"Repriced {n} share-based position(s) at latest prices.")
        return 0

    # buy / sell
    if not args.ticker or args.shares is None:
        print("buy/sell need a TICKER and SHARES, e.g. holdings buy AAPU 10 --price 45",
              file=sys.stderr)
        return 2
    price = args.price if args.price is not None else latest(args.ticker)
    if price is None:
        print(f"couldn't fetch a price for {args.ticker}; pass --price", file=sys.stderr)
        return 1
    delta = args.shares if args.action == "buy" else -args.shares
    try:
        r = apply_trade(rows, args.ticker, args.account, delta, price)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    write_rows(args.file, rows)
    verb = "Bought" if args.action == "buy" else "Sold"
    if r:
        print(f"{verb} {args.shares:g} {args.ticker.upper()} @ ${price:,.2f} "
              f"-> {r.shares:g} sh, ${r.market_value:,.2f} in {args.account}")
    else:
        print(f"Closed {args.ticker.upper()} in {args.account}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="stockskill", description="Reproducible stock analysis.")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("value", help="fair-value estimate for a ticker")
    v.add_argument("ticker", nargs="?")
    v.add_argument("--growth", type=float, help="stage-1 FCF growth (decimal)")
    v.add_argument("--terminal", type=float, help="terminal growth (decimal)")
    v.add_argument("--peer-pe", type=float)
    v.add_argument("--peer-ps", type=float)
    v.add_argument("--peer-ev-ebitda", type=float)
    v.add_argument("--snapshot", help="load a saved snapshot JSON instead of fetching")
    v.add_argument("--save", help="save fetched snapshot to this JSON path")
    v.add_argument("--no-sensitivity", action="store_true", help="hide the DCF sensitivity grid")
    v.set_defaults(func=cmd_value)

    lt = sub.add_parser("lookthrough", help="true underlying exposure of holdings")
    lt.add_argument("--holdings", default="holdings.csv")
    lt.set_defaults(func=cmd_lookthrough)

    pf = sub.add_parser("portfolio", help="full look-through portfolio review")
    pf.add_argument("--holdings", default="holdings.csv")
    pf.set_defaults(func=cmd_portfolio)

    d = sub.add_parser("decay", help="leveraged-ETF volatility decay")
    d.add_argument("--multiplier", type=float, required=True)
    d.add_argument("--vol", type=float, default=0.45, help="annualized vol (decimal)")
    d.add_argument("--drift", type=float, default=0.10, help="annualized drift (decimal)")
    d.add_argument("--days", type=int, default=252)
    d.add_argument("--expense", type=float, default=0.0, help="annual expense+financing (decimal)")
    d.add_argument("--seed", type=int, default=12345)
    d.add_argument("--ticker", help="replay this underlying's real path instead of MC")
    d.add_argument("--period", default="1y")
    d.set_defaults(func=cmd_decay)

    sc = sub.add_parser("screen", help="rank a universe into a shortlist")
    sc.add_argument("--universe", default="universe.csv")
    sc.add_argument("--lane", choices=["core", "aggressive"], default="core")
    sc.add_argument("--top", type=int, default=15)
    sc.add_argument("--cache-dir", help="dir to save/load snapshot JSONs (reproducibility)")
    sc.add_argument("--refresh", action="store_true", help="re-fetch even if cached")
    sc.add_argument("--momentum", help="period for aggressive-lane momentum, e.g. 1y")
    sc.set_defaults(func=cmd_screen)

    pu = sub.add_parser("pulse", help="market pulse: sector/factor rotation, breadth, regime")
    pu.add_argument("--period", default="1y", help="history window to fetch")
    pu.add_argument("--price-map", help="JSON cache path (save/load for reproducibility)")
    pu.add_argument("--refresh", action="store_true", help="re-fetch even if cached")
    pu.set_defaults(func=cmd_pulse)

    db = sub.add_parser("dashboard", help="write a self-contained HTML dashboard")
    db.add_argument("--out", default="dashboard.html", help="output HTML path")
    db.add_argument("--holdings", default="holdings.csv")
    db.add_argument("--period", default="1y")
    db.add_argument("--price-map", help="JSON cache path for the price series")
    db.add_argument("--refresh", action="store_true", help="re-fetch prices even if cached")
    db.add_argument("--interval", type=float, default=30.0,
                    help="minutes between updates / meta-refresh (default 30)")
    db.add_argument("--watch", action="store_true", help="keep running, regenerate every interval")
    db.add_argument("--open", action="store_true", help="open the file in the browser after writing")
    db.set_defaults(func=cmd_dashboard)

    sv = sub.add_parser("serve", help="run the interactive stock analyzer (search any ticker)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8787)
    sv.add_argument("--open", action="store_true", help="open the browser after starting")
    sv.set_defaults(func=cmd_serve)

    wl = sub.add_parser("watchlist", help="multi-ticker technical dashboard (table view)")
    wl.add_argument("--tickers", default="data/tickers.csv")
    wl.add_argument("--out", default="watchlist.html")
    wl.add_argument("--period", default="2y", help="history to fetch (>1y so 1Y change fills)")
    wl.add_argument("--workers", type=int, default=5)
    wl.add_argument("--cache-dir", help="per-ticker cache dir (e.g. .cache/stock_cache)")
    wl.add_argument("--alerts", default="data/alerts.json", help="custom alerts JSON")
    wl.add_argument("--watch", action="store_true",
                    help="keep regenerating live (fast during market hours)")
    wl.add_argument("--interval", type=float,
                    help="minutes between updates (default: auto — 1m open, 5m ext, 30m closed)")
    wl.add_argument("--open", action="store_true", help="open the file after writing")
    wl.set_defaults(func=cmd_watchlist)

    h = sub.add_parser("holdings", help="update holdings.csv from trades")
    h.add_argument("action", choices=["list", "buy", "sell", "reprice"])
    h.add_argument("ticker", nargs="?")
    h.add_argument("shares", nargs="?", type=float)
    h.add_argument("--price", type=float, help="trade price (default: fetch latest)")
    h.add_argument("--account", default="brokerage")
    h.add_argument("--file", default="holdings.csv")
    h.set_defaults(func=cmd_holdings)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "command", None) == "value" and not args.ticker and not args.snapshot:
        print("value: provide a TICKER or --snapshot", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
