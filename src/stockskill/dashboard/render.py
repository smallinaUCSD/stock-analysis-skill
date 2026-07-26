"""Render a self-contained HTML dashboard from computed data.

No external assets (works offline, no CDN). Theme-aware via
prefers-color-scheme. Returns/relative-strength use zero-centered diverging
bars where direction + a numeric label carry the sign, so meaning never rests
on color alone. All inputs are plain numbers computed upstream by the pulse and
portfolio modules -- this file only formats.
"""

from __future__ import annotations

import html
from datetime import datetime


def _pct(x: float | None, signed: bool = True) -> str:
    if x is None or x != x:
        return "n/a"
    return f"{x:+.1%}" if signed else f"{x:.1%}"


def _num(x: float | None, dp: int = 2) -> str:
    return "n/a" if (x is None or x != x) else f"{x:.{dp}f}"


def _money(x: float | None) -> str:
    return "n/a" if (x is None or x != x) else f"${x:,.0f}"


def _diverging_row(label: str, ticker: str, value: float | None, maxabs: float,
                   title: str = "") -> str:
    lab = html.escape(label)
    tk = html.escape(ticker)
    ttl = html.escape(title or f"{label} ({ticker})")
    if value is None or value != value:
        neg = pos = ""
        vcls, vtxt = "muted", "n/a"
    else:
        w = min(100.0, abs(value) / maxabs * 100.0) if maxabs > 0 else 0.0
        if value >= 0:
            pos = f'<div class="fill up" style="width:{w:.1f}%"></div>'
            neg = ""
            vcls, vtxt = "up", _pct(value)
        else:
            neg = f'<div class="fill down" style="width:{w:.1f}%"></div>'
            pos = ""
            vcls, vtxt = "down", _pct(value)
    return (
        f'<div class="row" title="{ttl}">'
        f'<div class="row-label">{lab} <span class="tk">{tk}</span></div>'
        f'<div class="dbar"><div class="half neg">{neg}</div>'
        f'<div class="axis"></div><div class="half pos">{pos}</div></div>'
        f'<div class="row-val {vcls}">{vtxt}</div></div>'
    )


def _magnitude_row(label: str, value: float, maxv: float, value_str: str,
                   sub: str = "") -> str:
    lab = html.escape(label)
    w = min(100.0, value / maxv * 100.0) if maxv > 0 else 0.0
    sub_html = f' <span class="tk">{html.escape(sub)}</span>' if sub else ""
    return (
        f'<div class="row">'
        f'<div class="row-label">{lab}{sub_html}</div>'
        f'<div class="mbar"><div class="fill accent" style="width:{w:.1f}%"></div></div>'
        f'<div class="row-val">{html.escape(value_str)}</div></div>'
    )


def _tile(label: str, value_str: str, tone: str = "") -> str:
    return (
        f'<div class="tile {tone}">'
        f'<div class="tile-val">{html.escape(value_str)}</div>'
        f'<div class="tile-lab">{html.escape(label)}</div></div>'
    )


_CSS = """
:root{
  --bg:#f6f7f9; --surface:#ffffff; --surface-2:#eef1f4; --border:#dfe3e8;
  --ink:#1a1d21; --muted:#6b7280; --up:#0f8a5f; --down:#d1495b; --accent:#3b6ea5;
  --good:#0f8a5f; --warn:#c98a00; --crit:#c0392b; --axis:#c3c9d0;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#0f1215; --surface:#171b20; --surface-2:#1e242b; --border:#2a3138;
    --ink:#e8eaed; --muted:#9aa4af; --up:#3ecf8e; --down:#f2748a; --accent:#6ea8dc;
    --good:#3ecf8e; --warn:#e0b74a; --crit:#f2748a; --axis:#3a424b;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:12px;margin-bottom:4px}
h1{font-size:20px;margin:0;font-weight:650}
.status{font-weight:700;font-size:12px;letter-spacing:.04em;padding:3px 9px;
  border-radius:999px;border:1px solid var(--border)}
.status.open{color:#fff;background:var(--good);border-color:transparent}
.status.pre-market,.status.after-hours{color:var(--warn);border-color:var(--warn)}
.status.closed,.status.weekend{color:var(--muted)}
.sub{color:var(--muted);font-size:12.5px;margin:2px 0 18px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
@media (max-width:820px){.grid{grid-template-columns:1fr}}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:14px 16px}
.card h2{font-size:12.5px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--muted);margin:0 0 12px;font-weight:650}
.card.wide{grid-column:1 / -1}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:10px}
.tile{background:var(--surface-2);border:1px solid var(--border);border-radius:10px;
  padding:10px 12px}
.tile-val{font-size:19px;font-weight:680;font-variant-numeric:tabular-nums}
.tile-lab{font-size:11px;color:var(--muted);margin-top:3px}
.tile.good .tile-val{color:var(--good)} .tile.warn .tile-val{color:var(--warn)}
.tile.crit .tile-val{color:var(--crit)}
.row{display:grid;grid-template-columns:180px 1fr 64px;align-items:center;
  gap:10px;padding:3px 0}
.row-label{font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tk{color:var(--muted);font-size:11px}
.row-val{text-align:right;font-variant-numeric:tabular-nums;font-size:12.5px;font-weight:600}
.row-val.up,.up{color:var(--up)} .row-val.down,.down{color:var(--down)}
.row-val.muted{color:var(--muted)}
.dbar{display:flex;align-items:center;height:15px}
.half{flex:1;display:flex;height:11px}
.half.neg{justify-content:flex-end}
.axis{width:1px;height:15px;background:var(--axis)}
.fill{height:11px;border-radius:3px}
.fill.up{background:var(--up)} .fill.down{background:var(--down)}
.fill.accent{background:var(--accent)}
.mbar{height:11px;background:var(--surface-2);border-radius:3px;overflow:hidden}
.flags{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.flag{font-size:11px;padding:2px 8px;border-radius:999px;font-weight:600;
  background:var(--surface-2);border:1px solid var(--border)}
.flag.on{color:#fff;background:var(--crit);border-color:transparent}
.foot{color:var(--muted);font-size:11.5px;margin-top:16px;line-height:1.5}
.marketbar{display:flex;flex-wrap:wrap;gap:8px 16px;padding:10px 14px;margin-bottom:16px;
  background:var(--surface);border:1px solid var(--border);border-radius:10px;
  font-size:12.5px;font-variant-numeric:tabular-nums}
.marketbar .mq b{color:var(--muted);font-weight:600;font-size:11px;margin-right:3px}
"""


def render_dashboard(*, status, updated_et: str, updated_local: str,
                     refresh_seconds: int, regime_values: dict,
                     regime_flags: dict, sectors: list, factors: list,
                     breadth: tuple, portfolio: dict | None,
                     market: dict | None = None) -> str:
    # ---- market bar (indices / commodities / crypto + sentiment) ----
    market_bar = ""
    if market:
        items = []
        for name, last, chg in market.get("quotes", []):
            if last is None:
                continue
            cls = "up" if (chg or 0) >= 0 else "down"
            ctxt = "" if chg is None else f' <span class="{cls}">{chg:+.1%}</span>'
            items.append(f'<span class="mq"><b>{html.escape(name)}</b> '
                         f'{last:,.0f}{ctxt}</span>')
        fg = market.get("fear_greed")
        if fg:
            items.append(f'<span class="mq"><b>Fear &amp; Greed</b> {fg[0]:.0f} '
                         f'({html.escape(str(fg[1]))})</span>')
        items.append(f'<span class="mq"><b>CVR3</b> {html.escape(market.get("cvr3","n/a"))}</span>')
        clim = market.get("climate")
        if clim:
            items.append(f'<span class="mq"><b>Climate</b> {html.escape(clim)}</span>')
        rot = market.get("rotation")
        if rot:
            items.append(f'<span class="mq"><b>Rotation</b> {html.escape(rot[0])} '
                         f'<span class="up">{rot[1]:+.1%}</span></span>')
        market_bar = '<div class="marketbar">' + "".join(items) + '</div>'

    # ---- regime tiles ----
    vix = regime_values.get("vix")
    vix_tone = "crit" if (vix and vix > 30) else "warn" if (vix and vix > 20) else "good"
    curve = regime_values.get("yield_curve_10y_3m")
    curve_tone = "crit" if (curve is not None and curve < 0) else ""
    tiles = [
        _tile("VIX", _num(vix), vix_tone),
        _tile("Curve 10Y-3M", _num(curve), curve_tone),
        _tile("S&P 500 1m", _pct(regime_values.get("spy_1m"))),
        _tile("HY vs IG 1m", _pct(regime_values.get("hyg_vs_lqd_1m"))),
        _tile("Growth vs Value 1m", _pct(regime_values.get("growth_vs_value_1m"))),
        _tile("Gold 1m", _pct(regime_values.get("gold_1m"))),
    ]
    flag_labels = {
        "vix_elevated": "VIX elevated", "vix_stressed": "VIX stressed",
        "yield_curve_inverted": "curve inverted",
        "narrow_leadership": "narrow leadership", "credit_risk_off": "credit risk-off",
    }
    flags_html = "".join(
        f'<span class="flag {"on" if regime_flags.get(k) else ""}">{html.escape(v)}</span>'
        for k, v in flag_labels.items() if k in regime_flags
    )

    # ---- sectors ----
    sect_max = max((abs(s[4]) for s in sectors if s[4] is not None), default=0.01)
    sect_rows = "".join(
        _diverging_row(name, tk, r1m, sect_max,
                       title=f"{name} {tk}: 1d {_pct(r1d)}, 1w {_pct(r1w)}, 1m {_pct(r1m)}, 3m {_pct(r3m)}")
        for (name, tk, r1d, r1w, r1m, r3m) in sectors
    )

    # ---- factors ----
    fac_max = max((abs(f[3]) for f in factors if f[3] is not None), default=0.01)
    fac_rows = "".join(
        _diverging_row(label, f"{num}/{den}", rs, fac_max)
        for (label, num, den, rs) in factors
    )

    # ---- breadth ----
    pp, pa, nb = breadth
    breadth_tiles = "".join([
        _tile("Sectors positive 1m", _pct(pp, signed=False) if pp is not None else "n/a"),
        _tile("Sectors above 50d", _pct(pa, signed=False) if pa is not None else "n/a"),
        _tile("Sectors tracked", str(nb)),
    ])

    # ---- portfolio ----
    port_html = ""
    if portfolio:
        lev = portfolio.get("effective_leverage")
        lev_tone = "crit" if (lev and lev > 1.5) else "warn" if (lev and lev > 1.2) else ""
        ptiles = "".join([
            _tile("Equity", _money(portfolio.get("total_equity"))),
            _tile("Economic exposure", _money(portfolio.get("total_notional"))),
            _tile("Effective leverage", f'{lev:.2f}x' if lev else "n/a", lev_tone),
        ])
        top = portfolio.get("top_exposures", [])
        tmax = max((amt for _, amt, _ in top), default=1.0)
        top_rows = "".join(
            _magnitude_row(ul, amt, tmax, _pct(share, signed=False)) for ul, amt, share in top
        )
        groups = portfolio.get("groups", [])
        gmax = max((amt for _, amt, _ in groups), default=1.0)
        grp_rows = "".join(
            _magnitude_row(g, amt, gmax, _pct(share, signed=False)) for g, amt, share in groups
        )
        port_html = f"""
        <div class="card wide">
          <h2>Portfolio — look-through</h2>
          <div class="tiles">{ptiles}</div>
          <div class="grid" style="margin-top:14px">
            <div><h2>Top true exposures</h2>{top_rows}</div>
            <div><h2>By factor group</h2>{grp_rows}</div>
          </div>
        </div>"""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{int(refresh_seconds)}">
<title>Market Pulse — {html.escape(status.badge)}</title>
<style>{_CSS}</style></head>
<body><div class="wrap">
<header>
  <h1>Market Pulse &amp; Portfolio</h1>
  <span class="status {html.escape(status.label)}">{html.escape(status.badge)}</span>
</header>
<div class="sub">Updated {html.escape(updated_et)} ET &nbsp;·&nbsp; {html.escape(updated_local)} local
  &nbsp;·&nbsp; auto-refresh {int(refresh_seconds // 60)} min</div>
{market_bar}
<div class="grid">
  <div class="card"><h2>Regime snapshot</h2>
    <div class="tiles">{''.join(tiles)}</div>
    <div class="flags">{flags_html}</div>
  </div>
  <div class="card"><h2>Breadth</h2><div class="tiles">{breadth_tiles}</div></div>
  <div class="card"><h2>Sector rotation (1m)</h2>{sect_rows}</div>
  <div class="card"><h2>Factor / style rotation (1m RS)</h2>{fac_rows}</div>
  {port_html}
</div>

<div class="foot">
  Computed facts, not signals — every number is produced by tested Python, not estimated.
  A defensive lean is a <em>cluster</em> (rising VIX + inverted/flattening curve + narrow
  breadth + credit risk-off), not any single tile. Free ETF/price data; exchange holidays
  not modeled. This is analysis, not investment advice.
</div>
</div></body></html>"""
