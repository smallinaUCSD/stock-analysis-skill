"""Render the watchlist as a self-contained dashboard: table / card / heatmap
views, faceted filter chips, sortable table, live search, and a theme toggle.

Reuses the dashboard theme CSS. Sparklines and heatmap tiles are inline (no
libraries). Every ticker element carries data-* attributes (signal, flags,
categories, sections) so one filter engine works across all three views.
"""

from __future__ import annotations

import html
import json
import os

from ..dashboard.render import _CSS
from ..trade import atr_trade_setup, position_size, suggest_options

_SIG_CLASS = {"BUY": "buy", "SELL": "sell", "SHORT": "short", "HOLD": "hold"}
_SIG_EMOJI = {"BUY": "🟢", "SELL": "🟠", "SHORT": "🔴", "HOLD": "⏸️"}
_FLAG_LABEL = {
    "oversold": "Oversold", "overbought": "Overbought", "surge": "Surge",
    "crash": "Crash", "squeeze": "Squeeze", "vol_spike": "Vol spike",
    "near_52w_high": "52w High", "near_52w_low": "52w Low",
    "earnings_soon": "Earnings soon",
}
_CAT_LABEL = {"tech": "Tech", "leveraged": "Leveraged", "etf": "ETF", "dividend": "Dividend"}
# short sector labels (covers both yfinance and SPDR sector naming)
_SECTOR_ABBR = {
    "technology": "Tech", "information technology": "Tech",
    "consumer discretionary": "Cons Disc", "consumer cyclical": "Cons Cyc",
    "consumer staples": "Cons Staples", "consumer defensive": "Cons Def",
    "communication services": "Comm Svcs", "communication svcs": "Comm Svcs",
    "financial services": "Financials", "financials": "Financials",
    "health care": "Health", "healthcare": "Health",
    "industrials": "Industrials", "energy": "Energy", "utilities": "Utilities",
    "basic materials": "Materials", "materials": "Materials",
    "real estate": "Real Estate",
}


def _abbr_sector(name):
    if not name:
        return name
    return _SECTOR_ABBR.get(str(name).strip().lower(), name)
_EXT_LINKS = [
    ("Yahoo", "https://finance.yahoo.com/quote/{t}"),
    ("Finviz", "https://finviz.com/quote.ashx?t={t}"),
    ("Barchart", "https://www.barchart.com/stocks/quotes/{t}"),
    ("StockAnalysis", "https://stockanalysis.com/stocks/{t}/"),
]

_CSS_EXTRA = """
/* manual theme toggle: force vars regardless of OS preference */
:root[data-theme="light"]{--bg:#f6f7f9;--surface:#fff;--surface-2:#eef1f4;--border:#dfe3e8;
  --ink:#1a1d21;--muted:#6b7280;--up:#0f8a5f;--down:#d1495b;--accent:#3b6ea5;
  --good:#0f8a5f;--warn:#c98a00;--crit:#c0392b;--axis:#c3c9d0;}
:root[data-theme="dark"]{--bg:#0f1215;--surface:#171b20;--surface-2:#1e242b;--border:#2a3138;
  --ink:#e8eaed;--muted:#9aa4af;--up:#3ecf8e;--down:#f2748a;--accent:#6ea8dc;
  --good:#3ecf8e;--warn:#e0b74a;--crit:#f2748a;--axis:#3a424b;}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0}
.bar input{flex:0 0 220px;font-size:12.5px;padding:7px 11px;border-radius:9px;line-height:1.15;
  border:1px solid var(--border);background:var(--surface);color:var(--ink)}
.count{color:var(--muted);font-size:12.5px}
.seg{display:inline-flex;border:1px solid var(--border);border-radius:9px;overflow:hidden}
.seg button{font-size:12.5px;padding:7px 13px;border:none;background:var(--surface);
  color:var(--muted);cursor:pointer}
.seg button.on{background:var(--accent);color:#fff;font-weight:650}
.tbtn{font-size:13px;padding:7px 11px;border-radius:9px;border:1px solid var(--border);
  background:var(--surface);color:var(--ink);cursor:pointer}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 14px}
.chip-f{font-size:11.5px;padding:3px 9px;border-radius:999px;cursor:pointer;
  background:var(--surface-2);border:1px solid var(--border);color:var(--ink)}
.chip-f.on{background:var(--accent);color:#fff;border-color:transparent;font-weight:650}
.chip-f small{opacity:.6}
/* table */
.tablewrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--border);border-radius:12px}
table.wl{border-collapse:collapse;width:100%;font-size:12.5px;min-width:900px}
table.wl th,table.wl td{padding:7px 10px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--border)}
table.wl th{position:sticky;top:0;z-index:2;background:var(--surface-2);color:var(--muted);font-weight:650;
  text-transform:uppercase;letter-spacing:.03em;font-size:11px;cursor:pointer;user-select:none}
/* freeze the Ticker column so the table stays readable while scrolling sideways */
table.wl th:first-child,table.wl td:first-child{text-align:left;position:sticky;left:0;
  background:var(--surface);box-shadow:1px 0 0 var(--border)}
table.wl td:first-child{z-index:1}
table.wl th:first-child{z-index:3}
.tablewrap.scrolled table.wl th:first-child,.tablewrap.scrolled table.wl td:first-child{
  box-shadow:6px 0 8px -4px rgba(0,0,0,.35)}
table.wl tr.item:hover td{background:var(--surface-2)}
table.wl tr.item:hover td:first-child{background:var(--surface-2)}
/* left-align Sector (9), Conf (14), Indicators (15) */
table.wl th:nth-child(9),table.wl td:nth-child(9),
table.wl th:nth-child(14),table.wl td:nth-child(14),
table.wl th:nth-child(15),table.wl td:nth-child(15){text-align:left}
.tk{font-weight:700}.nm{color:var(--muted);font-size:11px;font-weight:400}
.badge{font-weight:700;font-size:11px;padding:2px 7px;border-radius:6px}
.badge.buy{background:var(--good);color:#fff}.badge.short{background:var(--crit);color:#fff}
.badge.sell{background:var(--warn);color:#111}.badge.hold{color:var(--muted)}
.chip{display:inline-block;font-size:10px;padding:1px 5px;border-radius:5px;margin:1px;
  background:var(--surface-2);border:1px solid var(--border);color:var(--ink)}
.chip.g{color:var(--up);border-color:var(--up)}.chip.r{color:var(--down);border-color:var(--down)}
.up{color:var(--up)}.down{color:var(--down)}.muted{color:var(--muted)}
.arrow.up{color:var(--up)}.arrow.down{color:var(--down)}.arrow.flat{color:var(--muted)}
.conf-STRONG{color:var(--good);font-weight:700}.conf-MODERATE{color:var(--warn)}.conf-WEAK{color:var(--muted)}
/* board fills the page (override the shared 1180px cap); responsive side padding */
.wrap{max-width:min(2400px,100%);padding:18px clamp(14px,2.6vw,40px)}
/* cards */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(260px,100%),1fr));gap:12px}
.card-item{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 14px}
.card-top{display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:nowrap}
.card-top>div:first-child{min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.card-price{font-size:20px;font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap;flex:0 0 auto}
.card-row{display:flex;justify-content:space-between;font-size:12px;margin-top:3px;color:var(--muted)}
.card-row b{color:var(--ink);font-variant-numeric:tabular-nums}
.card-spark{margin:8px 0}
.links a{font-size:10.5px;color:var(--accent);text-decoration:none;margin-right:8px}
.tsetup{margin-top:8px;padding:8px 10px;border-radius:8px;border:1px solid var(--border);background:var(--surface-2)}
.tsetup.buy{border-color:var(--up)} .tsetup.short{border-color:var(--down)}
.ts-h{font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}
.ts-row{display:flex;justify-content:space-between;font-size:12px}
.ts-row b{font-variant-numeric:tabular-nums}
.opts{margin-top:2px;font-size:11px}
.card-item{cursor:pointer;position:relative;transition:border-color .12s}
.card-item:hover{border-color:var(--accent)}
.trendline{font-size:12.5px;font-weight:650;margin:1px 0 6px}
.fchip{min-height:36px;margin:0 0 4px;font-size:11.5px;font-weight:600;line-height:1.35}
.fchip .fpill{display:inline-block;max-width:100%;padding:2px 7px;border-radius:6px;
  background:var(--chip,rgba(120,130,150,.10))}
.fchip .up{color:var(--good)}.fchip .down{color:var(--crit)}
/* fixed-height slots so optional lines don't misalign cards */
.exthrs{font-size:11.5px;color:var(--muted);margin:1px 0 5px;font-variant-numeric:tabular-nums;min-height:16px}
.exthrs b{color:var(--ink);font-weight:700}
.erow{min-height:23px;margin-bottom:2px;display:flex;align-items:flex-start}
.erflag{display:inline-block;font-size:10.5px;font-weight:650;padding:2px 7px;border-radius:6px;margin:0}
.erflag.er-now{background:var(--crit);color:#fff}
.erflag.er-soon{background:var(--warn);color:#111}
.erflag.er-wk{background:var(--surface-2);border:1px solid var(--border);color:var(--muted)}
.details-cta{margin-top:8px;padding-top:8px;border-top:1px solid var(--border);
  text-align:center;font-size:11.5px;font-weight:650;color:var(--accent)}
.card-detail{display:none;margin-top:10px;padding-top:10px;border-top:1px dashed var(--border);cursor:default}
/* modal mini-window */
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:100;
  justify-content:center;padding:32px 16px;overflow:auto}
.modal.show{display:flex}
.modal-card{background:var(--surface);border:1px solid var(--border);border-radius:14px;
  padding:18px 20px;max-width:460px;width:100%;height:max-content;position:relative;
  box-shadow:0 20px 60px rgba(0,0,0,.45)}
.modal-x{position:absolute;top:10px;right:10px;width:36px;height:36px;z-index:2;
  border:1px solid var(--border);border-radius:50%;background:var(--surface-2);
  color:var(--ink);font-size:18px;cursor:pointer;line-height:1;display:flex;
  align-items:center;justify-content:center}
.modal-x:hover{background:var(--crit);color:#fff;border-color:transparent}
#modal-body .card-detail{display:block}
#modal-body .details-cta{display:none}
#modal-body .card-item{cursor:default;border:none;padding:0}
/* keep the expanded price out from under the close button */
#modal-body .card-top{padding-right:42px}
/* add-ticker bar (served mode) */
.addbar{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.addwrap{position:relative;flex:0 1 340px}
#addq{width:100%;padding:8px 11px;border-radius:9px;border:1px solid var(--border);
  background:var(--surface);color:var(--ink);font-size:13px}
#addq:focus{outline:none;border-color:var(--accent)}
.addsug{display:none;position:absolute;z-index:60;left:0;right:0;top:calc(100% + 4px);
  background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden;
  box-shadow:0 10px 30px rgba(0,0,0,.25)}
.sug{padding:7px 11px;font-size:13px;cursor:pointer;display:flex;gap:8px;align-items:baseline}
.sug:hover{background:var(--surface-2)} .sug b{color:var(--ink)} .sug span{color:var(--muted);font-size:11.5px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tbtn.add{background:var(--accent);color:#fff;border-color:transparent;font-weight:650}
#addmsg.ok{color:var(--up)} #addmsg.bad{color:var(--down)}
/* tools bar + tool modal */
.toolsbar{display:flex;flex-wrap:wrap;gap:6px;margin-left:6px}
.tool-b{font-family:inherit;font-size:12px;font-weight:600;line-height:1;box-sizing:border-box;
  padding:7px 11px;border-radius:9px;cursor:pointer;
  background:var(--surface);border:1px solid var(--border);color:var(--ink);
  text-decoration:none;display:inline-flex;align-items:center}
.tool-b:hover{border-color:var(--accent);color:var(--accent)}
.bmc{font:650 12px inherit;padding:7px 12px;border-radius:9px;text-decoration:none;
  background:#ffdd57;color:#3a2f00;border:1px solid #e6c200;white-space:nowrap}
.bmc:hover{filter:brightness(1.04)}
.tool-head h3{margin:0 34px 10px 0;font-size:17px}
.tool-form{margin-bottom:10px}
.t-row{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px}
.t-row input,.t-row select{padding:8px 10px;border-radius:8px;border:1px solid var(--border);
  background:var(--surface);color:var(--ink);font-size:13px}
.t-row input{flex:1 1 120px;min-width:90px} .t-row input:focus,.t-row select:focus{outline:none;border-color:var(--accent)}
.tool-out{min-height:20px}
.t-kv{display:flex;justify-content:space-between;gap:12px;padding:3px 0;font-size:13px;
  border-bottom:1px dashed var(--border)}
.t-kv span{color:var(--muted)} .t-kv b{font-variant-numeric:tabular-nums;text-align:right}
.t-kv b.up{color:var(--up)} .t-kv b.down{color:var(--down)}
.t-h{font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;
  letter-spacing:.04em;margin:10px 0 3px}
.t-note{font-size:11px;color:var(--muted);margin-top:8px;line-height:1.45}
.t-err{color:var(--down);font-size:13px;padding:6px 0}
.t-fac{font-size:12px;padding:4px 0;border-bottom:1px dashed var(--border)}
.t-fac b{text-transform:capitalize;font-size:10px;padding:1px 6px;border-radius:6px;margin-right:5px}
.t-fac.support b{background:var(--good,#16794a);color:#fff}
.t-fac.against b{background:var(--crit,#b42318);color:#fff}
.t-fac.neutral b{background:var(--surface-2);color:var(--muted)}
.mc-row{display:grid;grid-template-columns:34px 1fr 62px;align-items:center;gap:8px;
  font-size:12px;padding:2px 0}
.mc-row span{color:var(--muted)} .mc-row b{text-align:right;font-variant-numeric:tabular-nums}
.mc-row b.up{color:var(--up)} .mc-row b.down{color:var(--down)}
.mc-bar{height:9px;background:var(--surface-2);border-radius:5px;overflow:hidden}
.mc-fill{height:9px;border-radius:5px} .mc-fill.up{background:var(--up)} .mc-fill.down{background:var(--down)}
/* panels (sectors + markets + macro), always visible */
.panels{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:12px}
@media (max-width:980px){.panels{grid-template-columns:1fr 1fr}}
@media (max-width:640px){.panels{grid-template-columns:1fr}}
.macro-fg{display:flex;justify-content:space-between;align-items:baseline;gap:8px;
  font-size:12.5px;padding:2px 0}
.macro-fg b{font-variant-numeric:tabular-nums}
.macro-fomc{font-size:12.5px;padding:2px 0}
.macro-fomc b{font-weight:700}
.macro-ev{display:block;text-decoration:none;color:var(--ink);font-size:12px;
  line-height:1.35;padding:3px 0;border-bottom:1px dashed var(--border)}
.macro-ev:last-child{border-bottom:none}
a.macro-ev:hover{color:var(--accent)}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:10px 14px}
.panel-h{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;
  letter-spacing:.04em;margin-bottom:6px}
.panel-body{overflow:visible}
.mkgroup{font-size:9.5px;font-weight:700;color:var(--muted);text-transform:uppercase;
  letter-spacing:.05em;margin:6px 0 2px;opacity:.75}
.mkgroup:first-child{margin-top:0}
.mkrow{display:grid;grid-template-columns:1fr auto 62px;align-items:baseline;gap:8px;
  padding:2px 0;font-size:12.5px}
.mkname{color:var(--ink)}
.mkpx{font-variant-numeric:tabular-nums;color:var(--muted)}
.mkchg{text-align:right;font-variant-numeric:tabular-nums;font-weight:650}
.mkchg.up{color:var(--up)} .mkchg.down{color:var(--down)}
.secrow{display:grid;grid-template-columns:120px 1fr 54px;align-items:center;gap:8px;padding:2px 0;font-size:12px}
.secname{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--muted)}
.secbar{display:flex;align-items:center;height:12px}
.sechalf{flex:1;display:flex;height:9px}.sechalf.neg{justify-content:flex-end}
.secaxis{width:1px;height:12px;background:var(--axis)}
.fill-up{height:9px;border-radius:3px;background:var(--up)}
.fill-down{height:9px;border-radius:3px;background:var(--down)}
.secval{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
.det-sec{margin-top:8px}
.det-h{font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}
.det-row{display:flex;justify-content:space-between;gap:10px;font-size:12px;padding:1px 0}
.det-row b{font-variant-numeric:tabular-nums;text-align:right}
.det-note{font-size:11px;color:var(--muted);margin-top:4px;line-height:1.4}
.ts-sub{font-size:10.5px;color:var(--muted);margin-bottom:4px}
.stance{font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;margin-left:6px;
  text-transform:none;letter-spacing:0}
.stance.pos{background:var(--good);color:#fff} .stance.neg{background:var(--crit);color:#fff}
.stance.midtone{background:var(--warn);color:#111}
.stance.mid{background:var(--surface-2);border:1px solid var(--border);color:var(--muted)}
.fvtable{width:100%;border-collapse:collapse;font-size:12px;margin:4px 0}
.fvtable th{text-align:left;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.04em;padding:2px 0}
.fvtable td{padding:3px 0;font-variant-numeric:tabular-nums}
.fvtable td.fl{font-weight:600} .fvtable td.fl.up{color:var(--up)} .fvtable td.fl.down{color:var(--down)}
.fvtable td.fv{text-align:right;font-weight:700;padding-right:12px}
.fvtable td:last-child{text-align:right;color:var(--muted)}
/* price chart */
.chart-sec .tfbar{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px}
.tfb{font:600 11px inherit;padding:2px 8px;border-radius:999px;cursor:pointer;
  background:var(--surface-2);border:1px solid var(--border);color:var(--muted)}
.tfb:hover{color:var(--ink)}
.tfb.on{background:var(--accent,#3b82f6);border-color:transparent;color:#fff}
.pricechart{position:relative;width:100%;touch-action:none}
.pricechart svg{display:block;width:100%;height:auto;overflow:visible}
.pricechart .axl{fill:var(--muted);font-size:9px;font-family:inherit}
.chart-box{position:absolute;pointer-events:none;z-index:5;background:var(--surface);
  border:1px solid var(--border);border-radius:7px;padding:3px 7px;font-size:11px;
  line-height:1.35;box-shadow:0 4px 14px rgba(0,0,0,.3);white-space:nowrap}
.chart-box .cb-d{color:var(--muted);font-size:10px}
.chart-box .cb-p{font-weight:700;font-variant-numeric:tabular-nums}
.chart-tip{font-size:11px;margin-top:4px;min-height:15px;font-variant-numeric:tabular-nums}
.chart-tip b{color:var(--ink)}
/* recent news list (card modal) */
.nw{display:block;text-decoration:none;padding:6px 0;border-bottom:1px dashed var(--border)}
.nw:last-child{border-bottom:none}
a.nw:hover .nw-t{color:var(--accent)}
.nw-t{font-size:12.5px;color:var(--ink);line-height:1.35}
.nw-m{font-size:10.5px;color:var(--muted);margin-top:2px}
/* heatmap */
.heat{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px}
.heat-group{margin-bottom:16px}
.heat-h{font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase;
  letter-spacing:.03em;margin:0 0 7px;padding-bottom:4px;border-bottom:1px solid var(--border)}
.tile-item{border:1px solid var(--border);border-radius:10px;padding:10px 12px;text-align:center}
.tile-item .t{font-weight:700;font-size:13px}
.tile-item .c{font-size:15px;font-weight:700;font-variant-numeric:tabular-nums;margin-top:2px}
.tile-item .s{font-size:10px;color:var(--muted)}
.view{display:none}.view.active{display:block}
.banner{display:flex;align-items:center;gap:12px;padding:9px 14px;
  margin:10px 0;background:var(--surface-2);border:1px solid var(--border);border-radius:10px;font-size:12.5px}
.banner-vp{flex:1;overflow:hidden;-webkit-mask-image:linear-gradient(90deg,transparent,#000 3%,#000 97%,transparent);
  mask-image:linear-gradient(90deg,transparent,#000 3%,#000 97%,transparent)}
.banner-track{display:inline-flex;gap:26px;white-space:nowrap;animation:marquee 45s linear infinite;will-change:transform}
.banner:hover .banner-track{animation-play-state:paused}
@keyframes marquee{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.banner .a{white-space:nowrap}
.banner .x{cursor:pointer;color:var(--muted);border:none;background:none;font-size:15px;flex:0 0 auto}
@media (prefers-reduced-motion:reduce){.banner-track{animation:none}}
"""


# ---------- formatting helpers ---------- #
def _pct(x, signed=True):
    if x is None or x != x:
        return ("", "n/a")
    return ("up" if x >= 0 else "down", (f"{x*100:+.1f}%" if signed else f"{x*100:.1f}%"))


def _mktcap(x):
    if x is None:
        return "n/a"
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(x) >= div:
            return f"${x/div:.1f}{unit}"
    return f"${x:,.0f}"


def _num(x, dp=1):
    return "n/a" if (x is None or x != x) else f"{x:.{dp}f}"


def _spark(values, w=84, h=22):
    vals = [v for v in (values or []) if v == v]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    n = len(vals)
    pts = " ".join(f"{i/(n-1)*w:.1f},{h-(v-lo)/rng*h:.1f}" for i, v in enumerate(vals))
    color = "var(--up)" if vals[-1] >= vals[0] else "var(--down)"
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5"/></svg>')


def _tile_color(change):
    if change is None or change != change:
        return "transparent"
    mag = min(abs(change) / 0.06, 1.0)
    a = 0.10 + 0.55 * mag
    return f"rgba(30,160,90,{a:.2f})" if change >= 0 else f"rgba(205,70,90,{a:.2f})"


def _data_attrs(r):
    return (f'data-ticker="{html.escape(r.ticker)}" data-signal="{r.signal}" '
            f'data-flags="{html.escape(" ".join(sorted(r.flags)))}" '
            f'data-cats="{html.escape(" ".join(sorted(r.categories)))}" '
            f'data-secs="{html.escape(" ".join(sorted(r.sections)))}"')


def _indicator_chips(r):
    c = []
    if r.macd_state in ("bull_cross", "bullish"):
        c.append('<span class="chip g">MACD↑</span>')
    elif r.macd_state in ("bear_cross", "bearish"):
        c.append('<span class="chip r">MACD↓</span>')
    if r.ichimoku == "above":
        c.append('<span class="chip g">☁▲</span>')
    elif r.ichimoku == "below":
        c.append('<span class="chip r">☁▼</span>')
    if r.golden_death == "golden":
        c.append('<span class="chip g">golden</span>')
    elif r.golden_death == "death":
        c.append('<span class="chip r">death</span>')
    if r.bb_squeeze:
        c.append('<span class="chip">squeeze</span>')
    if r.vol_spike:
        c.append('<span class="chip g">vol↑</span>')
    if "near_52w_high" in r.flags:
        c.append('<span class="chip g">52wH</span>')
    if "near_52w_low" in r.flags:
        c.append('<span class="chip r">52wL</span>')
    return "".join(c) or '<span class="muted">—</span>'


# ---------- per-view renderers ---------- #
_HEADERS = ["Ticker", "Price", "Day", "5D", "1M", "1Y", "52wL", "52wH", "Sector",
            "30d", "Signal", "Trend", "RSI", "Conf", "Indicators", "P/E", "Mkt Cap",
            "Factor"]


def _factor_cls(pct):
    if pct is None:
        return "muted"
    return "up" if pct >= 66 else ("down" if pct <= 33 else "")


def _factor_cell(r):
    """Table cell: the composite factor percentile (sortable), color-coded."""
    comp = (getattr(r, "factor", None) or {}).get("composite")
    if comp is None:
        return '<td class="muted" data-sort="-1">—</td>'
    return f'<td class="{_factor_cls(comp)}" data-sort="{comp}">{comp}</td>'


def _factor_chip(r):
    """Card chip in a fixed-height slot (so 1- vs 2-line reads don't misalign
    cards): the plain-English factor read + composite percentile."""
    f = getattr(r, "factor", None) or {}
    comp, label = f.get("composite"), f.get("label")
    if comp is None or not label:
        return '<div class="fchip"></div>'          # empty slot keeps cards aligned
    return (f'<div class="fchip"><span class="fpill"><span class="{_factor_cls(comp)}">◆</span> '
            f'{html.escape(label)} <span class="muted">· factor {comp}</span></span></div>')


def _row_html(r):
    if r.error or r.price is None:
        return (f'<tr class="item" {_data_attrs(r)}><td class="tk">{html.escape(r.ticker)}</td>'
                f'<td colspan="17" class="muted">no data</td></tr>')

    def cell(x):
        cls, txt = _pct(x)
        return f'<td class="{cls}" data-sort="{x if x is not None else -999}">{txt}</td>'

    def money_cell(x):
        return (f'<td data-sort="{x if x is not None else -1}">'
                f'{("$"+format(x, ",.0f")) if x is not None else "n/a"}</td>')

    sig_cls = _SIG_CLASS.get(r.signal, "hold")
    arrow_cls = "up" if r.trend_score > 1 else ("down" if r.trend_score < -1 else "flat")
    rsi_cls = "up" if (r.rsi or 50) >= 70 else ("down" if (r.rsi or 50) <= 30 else "")
    conf = (f'<span class="conf-{r.confidence}">{r.confidence}</span>'
            if r.confidence else '<span class="muted">—</span>')
    sector = html.escape((_abbr_sector(r.sector) or "—")[:16])
    return (
        f'<tr class="item" {_data_attrs(r)}>'
        f'<td><span class="tk">{html.escape(r.ticker)}</span></td>'
        f'<td data-sort="{r.price}">${r.price:,.2f}</td>'
        + cell(r.changes.get("1d")) + cell(r.changes.get("5d")) + cell(r.changes.get("1m"))
        + cell(r.changes.get("1y"))
        + money_cell(r.week52_low) + money_cell(r.week52_high)
        + f'<td style="text-align:left" class="muted">{sector}</td>'
        + f'<td>{_spark(r.sparkline)}</td>'
        f'<td data-sort="{r.trend_score}"><span class="badge {sig_cls}">{r.signal}</span></td>'
        f'<td class="arrow {arrow_cls}" data-sort="{r.trend_score}">{r.trend_arrow}</td>'
        f'<td class="{rsi_cls}" data-sort="{r.rsi if r.rsi is not None else -1}">{_num(r.rsi,0)}</td>'
        f'<td>{conf}</td>'
        f'<td style="text-align:left">{_indicator_chips(r)}</td>'
        f'<td data-sort="{r.pe if r.pe is not None else -1}">{_num(r.pe,1)}</td>'
        f'<td data-sort="{r.market_cap or 0}">{_mktcap(r.market_cap)}</td>'
        + _factor_cell(r) + '</tr>'
    )


def _trade_setup_html(r):
    if not r.atr or not r.price:
        return ""
    # Always show a setup. Direction from the signal, or the trend when HOLD.
    if r.signal == "SHORT" or (r.signal == "HOLD" and r.trend_score < 0):
        direction, cls = "SHORT", "short"
    else:
        direction, cls = "LONG", "buy"
    s = atr_trade_setup(r.price, r.atr, direction)
    if not s:
        return ""
    illustrative = "" if r.signal in ("BUY", "SHORT") else \
        '<div class="ts-sub">no active signal — illustrative ATR setup, direction from trend</div>'
    # P(target before stop) — a first-passage probability from drift/vol; the
    # honest edge estimate that feeds Kelly. Informational; always shown. The
    # sizing lenses (fixed 2% risk vs edge-based half-Kelly vs vol-target
    # allocation) differ in *fraction*; dollars only when ACCOUNT_SIZE is set.
    from ..trade.sizing import (win_prob_barrier, kelly_risk_fraction,
                                vol_target_fraction, sizing_plan)
    win_line = size_line = lens_line = ""
    if r.vol_annual and r.drift_annual is not None:
        wp = win_prob_barrier(s.entry, s.target, s.stop, r.drift_annual, r.vol_annual, direction)
        if wp is not None:
            win_line = (f'<div class="ts-row"><span>P(target before stop)</span>'
                        f'<b class="{"up" if wp >= 0.5 else "down"}">{wp*100:.0f}%</b></div>')
            f = kelly_risk_fraction(wp, s.rr_ratio)
            vf = vol_target_fraction(r.vol_annual)
            kelly_txt = f'½-Kelly {0.5*f*100:.1f}% risk' if f > 0 else 'Kelly: no edge → pass'
            vt_txt = f' · vol-tgt {vf*100:.0f}% alloc' if vf else ''
            lens_line = f'<div class="ts-sub">Sizing · 2% risk · {kelly_txt}{vt_txt}</div>'

    acct = os.environ.get("ACCOUNT_SIZE")
    if acct and r.vol_annual and r.drift_annual is not None:
        try:
            pl = sizing_plan(float(acct), s, r.drift_annual, r.vol_annual)
            parts = []
            if pl.fixed_dollars:
                parts.append(f'2% ${pl.fixed_dollars:,.0f}')
            if pl.tradable and pl.kelly_dollars:
                parts.append(f'½-Kelly ${pl.kelly_dollars:,.0f}')
            if pl.voltarget_dollars:
                parts.append(f'vol-tgt ${pl.voltarget_dollars:,.0f}')
            if parts:
                size_line = f'<div class="ts-row"><span>Size</span><b>{" · ".join(parts)}</b></div>'
        except ValueError:
            pass
    elif acct:
        try:
            ps = position_size(float(acct), s.entry, s.stop)
            if ps:
                size_line = (f'<div class="ts-row"><span>Size</span><b>{ps.shares:.0f} sh · '
                             f'${ps.dollars:,.0f} ({ps.pct_of_account:.0%})'
                             f'{" (cap)" if ps.capped else ""}</b></div>')
        except ValueError:
            pass
    return (
        f'<div class="tsetup {cls}"><div class="ts-h">Trade setup · {direction} '
        f'({s.rr_ratio:.0f}:1 R:R)</div>{illustrative}'
        f'<div class="ts-row"><span>Entry</span><b>${s.entry:,.2f}</b></div>'
        f'<div class="ts-row"><span>Stop</span><b class="down">${s.stop:,.2f} (-{s.risk_pct*100:.1f}%)</b></div>'
        f'<div class="ts-row"><span>Target</span><b class="up">${s.target:,.2f} (+{s.reward_pct*100:.1f}%)</b></div>'
        f'{win_line}{size_line}{lens_line}</div>')


def _options_html(r):
    day = r.changes.get("1d")
    ideas = suggest_options(trend_score=r.trend_score, rsi=r.rsi,
                            change_pct=(day * 100 if day is not None else None),
                            golden_death=r.golden_death)
    if not ideas:
        return ""
    chips = "".join(
        f'<span class="chip {"g" if i.direction=="bullish" else "r" if i.direction=="bearish" else ""}" '
        f'title="{html.escape(i.rationale)}">{html.escape(i.label)}</span>' for i in ideas)
    return f'<div class="det-sec"><div class="det-h">Options ideas</div><div class="opts">📈 {chips}</div></div>'


def _valuation_html(r):
    d = r.valuation or {}
    v = d.get("valuation") or {}
    c = d.get("consensus") or {}
    if not v:
        return '<div class="det-sec"><div class="det-h">Stock analyzer</div><div class="muted">valuation n/a (ETF or no fundamentals)</div></div>'

    # Colored stance: undervalued=green, overvalued=red, fair=neutral.
    mos = v.get("margin_of_safety")
    if mos is None:
        stance_cls, stance = "mid", "no reliable fair value"
    elif mos >= 0.10:
        stance_cls, stance = "pos", "Undervalued"
    elif mos <= -0.10:
        stance_cls, stance = "neg", "Overvalued"
    else:
        stance_cls, stance = "midtone", "Fairly valued"
    header = (f'<div class="det-h">Stock analyzer — valuation '
              f'<span class="stance {stance_cls}">{stance}'
              + (f' {mos*100:+.0f}%' if mos is not None else '') + '</span></div>')

    price = v.get("price") or r.price
    base, bear, bull = v.get("base"), v.get("bear"), v.get("bull")
    body = ""
    if base is not None and bear is not None and bull is not None:
        def frow(label, val, cls=""):
            pv = ""
            if price and val:
                dv = val / price - 1.0
                pv = f'<td class="{"up" if dv>=0 else "down"}">{dv*100:+.0f}% vs price</td>'
            return f'<tr><td class="fl {cls}">{label}</td><td class="fv">${val:,.0f}</td>{pv or "<td></td>"}</tr>'
        body += ('<table class="fvtable"><tr><th>Fair value</th><th></th><th></th></tr>'
                 + frow("Bear", bear, "down") + frow("Base", base)
                 + frow("Bull", bull, "up") + '</table>')

    rows = []
    ig = v.get("implied_market_growth")
    if ig is not None:
        rows.append(f'<div class="det-row"><span>Reverse-DCF implied growth</span><b>{ig*100:.0f}%</b></div>')
    mc_p = v.get("mc_prob_undervalued")
    if mc_p is not None:
        p5, p95 = v.get("mc_p5"), v.get("mc_p95")
        band = (f' <span class="muted" style="font-weight:400">· P5–P95 ${p5:,.0f}–${p95:,.0f}</span>'
                if (p5 and p95) else '')
        rows.append('<div class="det-row"><span>Monte Carlo DCF · P(undervalued)</span>'
                    f'<b class="{"up" if mc_p >= 0.5 else "down"}">{mc_p*100:.0f}%</b>{band}</div>')
    reco = c.get("reco")
    if reco and reco != "n/a":
        tvp = c.get("target_vs_price")
        thtml = ""
        if tvp is not None:
            thtml = f' · target <span class="{"up" if tvp>=0 else "down"}">{tvp*100:+.0f}%</span>'
        rows.append(f'<div class="det-row"><span>Analyst consensus</span><b>{html.escape(reco)}{thtml}</b></div>')
    note = v.get("note")
    note_html = f'<div class="det-note">{html.escape(note)}</div>' if note else ""
    return f'<div class="det-sec">{header}{body}{"".join(rows)}{note_html}</div>'


_TIMEFRAMES = [("1mo", "1M"), ("3mo", "3M"), ("6mo", "6M"),
               ("1y", "1Y"), ("2y", "2Y"), ("5y", "5Y"), ("max", "Max")]
_CHART_DEFAULT_TF = "1y"


def _chart_html(r):
    ph = r.price_history or {}
    closes = ph.get("c") or []
    if len(closes) < 5:
        return ""
    series = json.dumps({"d": ph.get("d", []), "c": closes}, separators=(",", ":"))
    btns = "".join(
        f'<button type="button" class="tfb{" on" if tf == _CHART_DEFAULT_TF else ""}" '
        f'data-tf="{tf}" onclick="chartTf(this)">{lbl}</button>'
        for tf, lbl in _TIMEFRAMES)
    return (f'<div class="det-sec chart-sec"><div class="det-h">Price history</div>'
            f'<div class="tfbar">{btns}</div>'
            f'<div class="pricechart" data-series="{html.escape(series, quote=True)}"></div>'
            f'<div class="chart-tip muted">Hover the chart for price at a date</div></div>')


def _card_detail(r):
    ts = _trade_setup_html(r)
    ts_sec = f'<div class="det-sec">{ts}</div>' if ts else ""
    return (f'<div class="card-detail" onclick="event.stopPropagation()">'
            f'{_chart_html(r)}{ts_sec}{_options_html(r)}{_valuation_html(r)}'
            f'<div class="cardnews" data-ticker="{html.escape(r.ticker)}"></div></div>')


def _earnings_badge(r):
    """Earnings flag when earnings are within two weeks.

    Always renders a fixed-height slot (empty when there's no upcoming earnings)
    so the sparkline and metric rows stay aligned across cards.
    """
    from .row import earnings_days
    d = earnings_days(getattr(r, "next_earnings", None))
    inner = ""
    if d is not None and d <= 14:
        if d == 0:
            txt, cls = "Earnings today", "er-now"
        elif d == 1:
            txt, cls = "Earnings tomorrow", "er-now"
        elif d <= 6:
            txt, cls = f"Earnings in {d}d", "er-soon"
        else:
            txt, cls = "Earnings next week", "er-wk"
        inner = f'<span class="erflag {cls}">📅 {txt}</span>'
    return f'<div class="erow">{inner}</div>'


def _ext_html(r):
    """Pre/after-hours price line. Always renders a fixed-height slot (empty when
    there's no extended session) so cards line up."""
    if getattr(r, "ext_price", None) is None:
        return '<div class="exthrs"></div>'
    st = (r.market_state or "").upper()
    label = "Pre-market" if st.startswith("PRE") else "After hours"
    cls, txt = _pct(r.ext_change)
    return (f'<div class="exthrs">{label} <b>${r.ext_price:,.2f}</b> '
            f'<span class="{cls}">{txt}</span></div>')


def _card_html(r):
    if r.error or r.price is None:
        return (f'<div class="card-item item" {_data_attrs(r)}>'
                f'<div class="card-top"><b>{html.escape(r.ticker)}</b>'
                f'<span class="muted">no data</span></div></div>')
    dcls, dtxt = _pct(r.changes.get("1d"))
    sig_cls = _SIG_CLASS.get(r.signal, "hold")
    tcls = "up" if r.trend_score > 1 else ("down" if r.trend_score < -1 else "muted")
    trend_word = (r.trend_label or "neutral").capitalize()
    links = " ".join(f'<a href="{u.format(t=r.ticker)}" target="_blank" rel="noopener">{n}</a>'
                     for n, u in _EXT_LINKS)

    def mrow(label, x):
        c, t = _pct(x)
        return f'<div class="card-row"><span>{label}</span><b class="{c}">{t}</b></div>'
    summary = (
        f'<div class="card-top"><div><span class="tk">{html.escape(r.ticker)}</span> '
        f'<span class="badge {sig_cls}">{r.signal}</span></div>'
        f'<span class="card-price">${r.price:,.2f} <span class="{dcls}" style="font-size:13px">{dtxt}</span></span></div>'
        f'<div class="nm">{html.escape((r.name or "")[:34])}</div>'
        f'{_ext_html(r)}'
        f'<div class="trendline {tcls}">{html.escape(trend_word)} <span class="muted">· trend {r.trend_score:+.0f}</span></div>'
        f'{_factor_chip(r)}'
        f'{_earnings_badge(r)}'
        f'<div class="card-spark">{_spark(r.sparkline, w=222, h=34)}</div>'
        f'<div style="margin:4px 0">{_indicator_chips(r)}</div>'
        + mrow("1M", r.changes.get("1m")) + mrow("1Y", r.changes.get("1y"))
        + f'<div class="card-row"><span>RSI</span><b>{_num(r.rsi,0)}</b></div>'
        f'<div class="card-row"><span>P/E · Mkt Cap</span><b>{_num(r.pe,1)} · {_mktcap(r.market_cap)}</b></div>'
        f'<div class="links" onclick="event.stopPropagation()" style="margin-top:8px">{links}</div>'
        f'<div class="details-cta">🔎 Click for full analysis</div>'
    )
    return (f'<div class="card-item item" {_data_attrs(r)} onclick="openCard(this)">'
            f'{summary}{_card_detail(r)}</div>')


def _tile_html(r):
    day = r.changes.get("1d")
    _, dtxt = _pct(day)
    return (
        f'<div class="tile-item item" {_data_attrs(r)} style="background:{_tile_color(day)}">'
        f'<div class="t">{html.escape(r.ticker)}</div>'
        f'<div class="c">{dtxt}</div>'
        f'<div class="s">{r.signal} {r.trend_arrow}</div></div>'
    )


def _heatmap_html(rows):
    """Heatmap grouped by sector, sectors ordered by average day change."""
    def day(r):
        d = r.changes.get("1d") if not (r.error or r.price is None) else None
        return d

    groups: dict[str, list] = {}
    for r in rows:
        sec = (r.sector or "Other") if not (r.error or r.price is None) else "No data"
        groups.setdefault(sec, []).append(r)

    def avg(rs):
        vals = [day(r) for r in rs if day(r) is not None]
        return sum(vals) / len(vals) if vals else -99

    out = []
    for sec, rs in sorted(groups.items(), key=lambda kv: avg(kv[1]), reverse=True):
        a = avg(rs)
        cls, atxt = _pct(a if a != -99 else None)
        rs_sorted = sorted(rs, key=lambda r: (day(r) if day(r) is not None else -99), reverse=True)
        tiles = "".join(_tile_html(r) for r in rs_sorted)
        avg_html = f'<span class="{cls}">{atxt}</span>' if a != -99 else ""
        out.append(
            f'<div class="heat-group" data-sector="{html.escape(sec)}">'
            f'<div class="heat-h">{html.escape(_abbr_sector(sec))} {avg_html} '
            f'<span class="muted">· {len(rs)}</span></div>'
            f'<div class="heat">{tiles}</div></div>')
    return "".join(out)


def _chip_bar(rows):
    signals, flags, cats, secs = set(), set(), set(), set()
    for r in rows:
        signals.add(r.signal)
        flags |= set(r.flags)
        cats |= set(r.categories)
        secs |= set(r.sections)
    secs.discard("TICKERS")

    def chip(group, match, label):
        return f'<button class="chip-f" data-group="{group}" data-match="{match}" onclick="toggleChip(this)">{label}</button>'

    out = []
    for s in ("BUY", "SELL", "SHORT", "HOLD"):
        if s in signals:
            out.append(chip("signal", s, f"{_SIG_EMOJI.get(s,'')} {s}"))
    for fl in ("oversold", "overbought", "surge", "crash", "squeeze", "vol_spike",
               "near_52w_high", "near_52w_low", "earnings_soon"):
        if fl in flags:
            out.append(chip("condition", fl, _FLAG_LABEL[fl]))
    for cat in ("tech", "leveraged", "etf", "dividend"):
        if cat in cats:
            out.append(chip("category", cat, _CAT_LABEL[cat]))
    for sec in sorted(secs):
        out.append(chip("section", sec, sec.title()))
    return "".join(out)


def _banner(alerts):
    """A single-line marquee that slides through every alert (no truncation)."""
    if not alerts:
        return "", ""
    items = "".join(f'<span class="a">{html.escape(a.emoji)} {html.escape(a.message)}</span>'
                    for a in alerts)
    # scale the loop duration with the amount of text so it reads at a steady pace
    dur = max(20, min(150, len(alerts) * 3))
    sig = f"{len(alerts)}:" + ",".join(a.kind for a in alerts[:5])
    track = (f'<div class="banner-track" style="animation-duration:{dur}s">'
             f'{items}{items}</div>')
    banner = (f'<div class="banner" id="banner" data-sig="{html.escape(sig)}">'
              f'<div class="banner-vp">{track}</div>'
              f'<button class="x" onclick="dismissBanner()" title="Dismiss">✕</button></div>')
    return banner, sig


def _sector_html(sectors):
    present = [(n, t, r) for (n, t, r) in (sectors or []) if r is not None]
    if not present:
        return '<section class="panel"><div class="panel-h">Sector performance · 1M</div>' \
               '<div class="muted" style="font-size:12px">unavailable</div></section>'
    mx = max(abs(r) for _, _, r in present) or 0.01
    rows = []
    for name, tk, r in sorted(present, key=lambda x: x[2], reverse=True):
        w = min(100.0, abs(r) / mx * 100.0)
        cls = "up" if r >= 0 else "down"
        neg = f'<div class="fill-down" style="width:{w:.0f}%"></div>' if r < 0 else ""
        pos = f'<div class="fill-up" style="width:{w:.0f}%"></div>' if r >= 0 else ""
        rows.append(
            f'<div class="secrow"><div class="secname">{html.escape(_abbr_sector(name))}</div>'
            f'<div class="secbar"><div class="sechalf neg">{neg}</div>'
            f'<div class="secaxis"></div><div class="sechalf pos">{pos}</div></div>'
            f'<div class="secval {cls}">{r*100:+.1f}%</div></div>')
    return ('<section class="panel"><div class="panel-h">Sector performance · 1M</div>'
            '<div class="panel-body">' + "".join(rows) + '</div></section>')


_MKT_GROUP_LABEL = {"index": "Indices", "commodity": "Commodities", "crypto": "Crypto"}


def _markets_html(markets):
    quotes = [q for q in (markets or []) if q.last is not None]
    if not quotes:
        return '<section class="panel"><div class="panel-h">Markets</div>' \
               '<div class="muted" style="font-size:12px">unavailable</div></section>'
    rows = []
    last_group = None
    for q in quotes:
        if q.group != last_group:
            rows.append(f'<div class="mkgroup">{_MKT_GROUP_LABEL.get(q.group, q.group)}</div>')
            last_group = q.group
        chg = q.change
        ccls = "up" if (chg or 0) >= 0 else "down"
        chg_txt = f"{chg*100:+.2f}%" if chg is not None else "—"
        px = f"${q.last:,.2f}" if q.last < 100 else f"${q.last:,.0f}"
        rows.append(
            f'<div class="mkrow"><span class="mkname">{html.escape(q.name)}</span>'
            f'<span class="mkpx">{px}</span>'
            f'<span class="mkchg {ccls}">{chg_txt}</span></div>')
    return ('<section class="panel"><div class="panel-h">Markets</div>'
            '<div class="panel-body">' + "".join(rows) + '</div></section>')


def _macro_html(macro):
    """Macro-trends panel: rate/vol gauges, next Fed decision, event headlines."""
    macro = macro or {}
    body = ""
    inds = [i for i in macro.get("indicators", []) if i.get("display") not in (None, "—")]
    if inds:
        rows = []
        for i in inds:
            chg = i.get("change")
            ccls = "up" if (chg or 0) >= 0 else "down"
            chg_txt = f"{chg*100:+.2f}%" if chg is not None else "—"
            rows.append(
                f'<div class="mkrow"><span class="mkname">{html.escape(i["name"])}</span>'
                f'<span class="mkpx">{html.escape(str(i["display"]))}</span>'
                f'<span class="mkchg {ccls}">{chg_txt}</span></div>')
        body += '<div class="mkgroup">Rates &amp; vol</div>' + "".join(rows)

    fg = macro.get("fear_greed")
    if fg and fg.get("score") is not None:
        score = fg["score"]
        fcls = "down" if score < 45 else ("up" if score > 55 else "muted")
        body += ('<div class="mkgroup">Sentiment</div>'
                 '<div class="macro-fg"><span class="mkname">Fear &amp; Greed</span>'
                 f'<span><b class="{fcls}">{score:.0f}</b> '
                 f'<span class="{fcls}" style="font-size:11px">{html.escape(str(fg.get("rating","")))}</span>'
                 '</span></div>')

    fomc = macro.get("fomc")
    if fomc:
        iso, days = fomc
        when = "today" if days == 0 else ("tomorrow" if days == 1 else f"in {days}d")
        body += ('<div class="mkgroup">Fed</div>'
                 f'<div class="macro-fomc">🏛️ Fed decision (FOMC) <b>{when}</b> '
                 f'<span class="muted">· {html.escape(iso)}</span></div>')

    events = macro.get("events", [])
    if events:
        ev = []
        for e in events:
            inner = f'{e.get("emoji","")} {html.escape(e.get("title",""))}'
            url = e.get("url") or ""
            ev.append(f'<a class="macro-ev" href="{html.escape(url)}" target="_blank" rel="noopener">{inner}</a>'
                      if url else f'<div class="macro-ev">{inner}</div>')
        body += '<div class="mkgroup">Market events</div>' + "".join(ev)

    if not body:
        body = '<div class="muted" style="font-size:12px">no macro data</div>'
    return ('<section class="panel"><div class="panel-h">Macro</div>'
            '<div class="panel-body">' + body + '</div></section>')


_SERVED_JS = r"""
let _addResults=[], _addTimer=null;
function addMsg(t,cls){ const m=document.getElementById('addmsg'); if(m){ m.textContent=t||''; m.className=(cls||'muted'); } }
function addSearch(){
  clearTimeout(_addTimer);
  const q=document.getElementById('addq').value.trim();
  const sug=document.getElementById('addsug');
  if(q.length<1){ sug.innerHTML=''; sug.style.display='none'; return; }
  _addTimer=setTimeout(()=>{
    fetch('/api/search?q='+encodeURIComponent(q)).then(r=>r.json()).then(d=>{
      _addResults=(d.results||[]).slice(0,8);
      if(!_addResults.length){ sug.innerHTML=''; sug.style.display='none'; return; }
      sug.innerHTML=_addResults.map((x,i)=>
        '<div class="sug" onclick="pickAdd('+i+')"><b>'+x.symbol+'</b> <span>'+
        (x.name||'').replace(/</g,'&lt;')+'</span></div>').join('');
      sug.style.display='block';
    }).catch(()=>{ sug.style.display='none'; });
  },180);
}
function pickAdd(i){ const x=_addResults[i]; if(x){ document.getElementById('addq').value=x.symbol; doAdd(x.symbol); } }
function addTicker(){ const q=document.getElementById('addq').value.trim().toUpperCase(); if(q) doAdd(q); }
function addKey(e){ if(e.key==='Enter'){ e.preventDefault(); addTicker(); } if(e.key==='Escape'){ document.getElementById('addsug').style.display='none'; } }
function doAdd(sym){
  document.getElementById('addsug').style.display='none';
  addMsg('adding '+sym+'…','muted');
  fetch('/api/watchlist/add?ticker='+encodeURIComponent(sym),{method:'POST'})
    .then(r=>r.json()).then(d=>{
      if(d.ok){ addMsg(sym+' added','ok'); location.reload(); }
      else{ addMsg(d.error||('could not add '+sym),'bad'); }
    }).catch(()=>addMsg('network error','bad'));
}
document.addEventListener('click', e=>{
  if(!e.target.closest('.addwrap')){ const s=document.getElementById('addsug'); if(s) s.style.display='none'; }
});

// ---- live update in place (no full page reload) ----
let _refreshing=false;
function _resort(){
  if(sortState.col==null) return;
  const tb=document.querySelector('#wl tbody'); if(!tb) return;
  const rows=Array.from(tb.querySelectorAll('tr.item'));
  rows.sort((a,b)=>{
    const av=parseFloat(a.children[sortState.col]?.dataset.sort ?? 'NaN');
    const bv=parseFloat(b.children[sortState.col]?.dataset.sort ?? 'NaN');
    if(isNaN(av)&&isNaN(bv)) return 0; if(isNaN(av)) return 1; if(isNaN(bv)) return -1;
    return (av-bv)*sortState.dir;
  });
  rows.forEach(r=>tb.appendChild(r));
}
function refreshData(){
  if(_refreshing || document.getElementById('modal').classList.contains('show')) return;
  _refreshing=true;
  fetch(location.pathname, {cache:'no-store'}).then(r=>r.text()).then(txt=>{
    const doc=new DOMParser().parseFromString(txt,'text/html');
    const swap=(sel)=>{ const n=doc.querySelector(sel), o=document.querySelector(sel);
      if(n&&o && o.innerHTML!==n.innerHTML) o.innerHTML=n.innerHTML; };
    swap('#wl tbody'); swap('#view-card .cards'); swap('#view-heatmap');
    swap('.panels'); swap('.banner-vp');
    const nb=doc.querySelector('.status'), ob=document.querySelector('.status');
    if(nb&&ob) ob.className=nb.className, ob.textContent=nb.textContent;
    const nu=doc.getElementById('updated'), ou=document.getElementById('updated');
    if(nu&&ou){ ou.dataset.ts=nu.dataset.ts; fmtUpdated(); }
    wireTableScroll(); _resort(); applyFilter();
  }).catch(()=>{}).finally(()=>{ _refreshing=false; });
}
// Open a page in a new, SCRIPT-opened tab so it can close itself (window.close)
// and return here. Falls back to same-tab nav only if a popup blocker intervenes.
function openTab(url){ var w=window.open(url,'_blank'); if(!w) location.href=url; }
// ---- recent news in the expanded card (served) ----
function _esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function _newsSec(inner){ return '<div class="det-sec"><div class="det-h">Recent news</div>'+inner+'</div>'; }
function loadNews(root){
  const el=root.querySelector('.cardnews'); if(!el) return;
  const t=el.dataset.ticker; if(!t) return;
  const nm=(root.querySelector('.nm')||{}).textContent||'';
  el.innerHTML=_newsSec('<div class="muted" style="font-size:12px">loading…</div>');
  fetch('/api/news/'+encodeURIComponent(t)+(nm?'?name='+encodeURIComponent(nm):'')).then(r=>r.json()).then(d=>{
    const items=(d.items||[]);   // already ranked most-recent first by the server
    if(!items.length){ el.innerHTML=_newsSec('<div class="muted" style="font-size:12px">No recent news.</div>'); return; }
    const rows=items.map(n=>{
      const meta=[n.publisher, n.age].filter(Boolean).join(' · ');
      const inner='<div class="nw-t">'+_esc(n.title)+'</div>'+(meta?'<div class="nw-m">'+_esc(meta)+'</div>':'');
      return n.url ? '<a class="nw" href="'+_esc(n.url)+'" target="_blank" rel="noopener">'+inner+'</a>'
                   : '<div class="nw">'+inner+'</div>';
    }).join('');
    el.innerHTML=_newsSec(rows);
  }).catch(()=>{ el.innerHTML=_newsSec('<div class="muted" style="font-size:12px">News unavailable right now.</div>'); });
}
// ---- analysis tool pop-ups ----
function closeTool(e){ if(e&&e.target&&e.target.id!=='toolmodal'&&e.type==='click') return;
  document.getElementById('toolmodal').classList.remove('show'); }
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeTool(); });
function _tkv(id){ const el=document.getElementById(id); return el?(el.value||'').trim().toUpperCase():''; }
function toolBusy(m){ document.getElementById('tool-out').innerHTML='<div class="muted">'+(m||'Running…')+'</div>'; }
function toolErr(m){ document.getElementById('tool-out').innerHTML='<div class="t-err">'+m+'</div>'; }
function _pc(x){ return x>=0?'up':'down'; }
function _ps(x){ return x==null?'—':(x>=0?'+':'')+(x*100).toFixed(1)+'%'; }
function _usd(x){ return x==null?'—':'$'+Number(x).toLocaleString(undefined,{maximumFractionDigits:2}); }
function _row(l,v){ return '<div class="t-kv"><span>'+l+'</span><b>'+v+'</b></div>'; }
function _mrow(l,v,c){ return '<div class="t-kv"><span>'+l+'</span><b class="'+c+'">'+v+'</b></div>'; }

const TOOLS = {
  evaluate:{title:'Evaluate a trade', form:'<div class="t-row"><input id="evtk" placeholder="Ticker e.g. NVDA" autocomplete="off"><select id="evact"><option value="buy">Buy</option><option value="sell">Sell</option><option value="short">Short</option></select></div><div class="t-row"><input id="evprice" placeholder="Price (opt)" inputmode="decimal"><input id="evstop" placeholder="Stop (opt)" inputmode="decimal"><input id="evtarget" placeholder="Target (opt)" inputmode="decimal"><button class="tbtn add" onclick="runEval()">Run</button></div>', run:runEval},
  lookthrough:{title:'Fund look-through', form:'<div class="t-row"><input id="ltk" placeholder="ETF e.g. VOO, QQQ, FNGU" autocomplete="off" onkeydown="if(event.key===&quot;Enter&quot;)runLook()"><button class="tbtn add" onclick="runLook()">Run</button></div>', run:runLook},
  montecarlo:{title:'Monte Carlo', form:'<div class="t-row"><input id="mctk" placeholder="Ticker e.g. NVDA" autocomplete="off"><select id="mcdays"><option value="21">1 month</option><option value="63" selected>3 months</option><option value="126">6 months</option><option value="252">1 year</option></select><select id="mcmethod"><option value="gbm">GBM (log-normal)</option><option value="bootstrap">Bootstrap (historical)</option></select><button class="tbtn add" onclick="runMC()">Run</button></div>', run:runMC},
};
let curTool=null;
function openTool(name){
  const t=TOOLS[name]; if(!t) return; curTool=name;
  document.getElementById('tool-head').innerHTML='<h3>'+t.title+'</h3>';
  document.getElementById('tool-form').innerHTML=t.form;
  document.getElementById('tool-out').innerHTML='';
  document.getElementById('toolmodal').classList.add('show');
  if(t.auto){ t.run(); } else { const i=document.querySelector('#tool-form input'); if(i) i.focus(); }
}
function runEval(){ const t=_tkv('evtk'); if(!t){ toolErr('enter a ticker'); return; }
  const act=document.getElementById('evact').value; let q='?action='+act;
  ['price','stop','target'].forEach(k=>{ const el=document.getElementById('ev'+k); if(el&&el.value.trim()) q+='&'+k+'='+encodeURIComponent(el.value.trim()); });
  toolBusy('Evaluating '+t+'…');
  fetch('/api/evaluate/'+encodeURIComponent(t)+q).then(r=>r.json()).then(d=>{
    if(d.error){ toolErr(d.error); return; }
    let h='<div class="t-kv"><span>'+t+' · '+d.action+'</span><b>'+_usd(d.price)+'</b></div>';
    h+=_row('Alignment', d.alignment+' <span class="muted">('+d.n_support+' for / '+d.n_against+' against)</span>');
    if(d.rr!=null) h+=_row('Risk / reward', d.rr.toFixed(2)+' : 1');
    h+='<div class="t-h">Factors</div>'+(d.factors||[]).map(f=>'<div class="t-fac '+f.stance+'"><b>'+f.stance+'</b> '+f.name+' <span class="muted">'+f.detail+'</span></div>').join('');
    document.getElementById('tool-out').innerHTML=h;
  }).catch(()=>toolErr('evaluate failed'));
}
function runLook(){ const t=_tkv('ltk'); if(!t){ toolErr('enter a ticker'); return; } toolBusy('Expanding '+t+'…');
  fetch('/api/lookthrough/'+encodeURIComponent(t)).then(r=>r.json()).then(d=>{
    if(!d.ok){ toolErr((d.error||'not a tracked product')+(d.note?'<div class="muted" style="margin-top:6px">'+d.note+'</div>':'')); return; }
    const isEtf = d.kind==='etf';
    let h='<div class="t-kv"><span>'+d.name+'</span><b>'+(isEtf?'ETF':(d.multiplier+'x'))+'</b></div>';
    h+=_row('Type', d.kind==='single'?'single-stock leveraged':(d.kind==='basket'?'leveraged basket':'index / sector ETF'));
    h+='<div class="t-h">'+(isEtf?'Top holdings':'Underlying exposure')+'</div><table class="fvtable"><tbody>'+
      d.constituents.map(c=>'<tr><td class="fl">'+c.underlying+'</td><td class="fv">'+(c.weight*100).toFixed(1)+'%</td><td>'+
        (isEtf?'':(c.weight*d.multiplier*100).toFixed(0)+'% notional')+'</td></tr>').join('')+'</tbody></table>';
    if(isEtf && d.sectors){
      const se=Object.entries(d.sectors).sort((a,b)=>b[1]-a[1]);
      h+='<div class="t-h">Sector weights</div>'+se.map(([k,v])=>_mrow(k.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase()), (v*100).toFixed(1)+'%','')).join('');
    }
    if(d.kind==='basket') h+='<div class="t-note">Basket as of '+(d.as_of||'—')+'. Indices rebalance quarterly — confirm current weights with the issuer.'+(d.verify?' (unverified snapshot)':'')+'</div>';
    if(isEtf) h+='<div class="t-note">'+(d.note||'Top holdings, live from the fund.')+'</div>';
    document.getElementById('tool-out').innerHTML=h;
  }).catch(()=>toolErr('look-through failed'));
}
function runMC(){ const t=_tkv('mctk'); if(!t){ toolErr('enter a ticker'); return; }
  const days=document.getElementById('mcdays').value, method=document.getElementById('mcmethod').value;
  const label=document.getElementById('mcdays').selectedOptions[0].text;
  toolBusy('Simulating '+t+' ('+label+')…');
  fetch('/api/montecarlo/'+encodeURIComponent(t)+'?days='+days+'&method='+method).then(r=>r.json()).then(d=>{
    if(d.error){ toolErr(d.error); return; }
    let h='<div class="t-kv"><span>'+d.ticker+' · '+d.days+'d · '+d.method+'</span><b>'+_usd(d.spot)+'</b></div>';
    h+=_mrow('Expected return',_ps(d.expected_return),_pc(d.expected_return));
    h+=_row('P(up)', (d.prob_up*100).toFixed(0)+'%');
    h+=_mrow('P(gain ≥ '+(d.gain_threshold*100).toFixed(0)+'%)', (d.prob_gain*100).toFixed(0)+'%','up');
    h+=_mrow('P(loss ≥ '+(d.loss_threshold*100).toFixed(0)+'%)', (d.prob_loss*100).toFixed(0)+'%','down');
    h+=_mrow('VaR (95%)', _ps(d.var_95),'down');
    h+='<div class="t-h">Outcome range ('+d.days+'-day return)</div>'+_mcCone(d.pctiles||{});
    h+='<div class="t-note">drift '+(d.drift_annual*100).toFixed(0)+'%/yr · vol '+(d.vol_annual*100).toFixed(0)+'%/yr · '+d.n_paths.toLocaleString()+' paths. A simulation from history, not a forecast.</div>';
    document.getElementById('tool-out').innerHTML=h;
  }).catch(()=>toolErr('montecarlo failed'));
}
function _mcCone(p){ const keys=['p95','p75','p50','p25','p5']; const vals=keys.map(k=>p[k]).filter(v=>v!=null);
  if(!vals.length) return ''; const mag=Math.max.apply(null,vals.map(Math.abs))||1;
  return keys.map(k=>{ const v=p[k]; if(v==null) return '';
    return '<div class="mc-row"><span>'+k+'</span><div class="mc-bar"><div class="mc-fill '+(v>=0?'up':'down')+'" style="width:'+Math.max(3,Math.abs(v)/mag*100)+'%"></div></div><b class="'+(v>=0?'up':'down')+'">'+_ps(v)+'</b></div>'; }).join('');
}
"""


def render_watchlist(rows, title="Watchlist", updated="", status_badge="", status_label="",
                     alerts=None, sectors=None, markets=None, refresh_seconds=1800,
                     served=False, updated_ts=None, macro=None, public=False, bmc_url=None):
    banner, _sig = _banner(alerts or [])
    sector_html = _sector_html(sectors)
    markets_html = _markets_html(markets)
    macro_html = _macro_html(macro)
    # Public mode hides only the Holdings button (personal data). Add-ticker and
    # the read-only tools stay.
    _add_box = (
        '<div class="addwrap">'
        '<input id="addq" placeholder="Add ticker (e.g. NVDA or &quot;oracle&quot;)…" '
        'autocomplete="off" oninput="addSearch()" onkeydown="addKey(event)">'
        '<div id="addsug" class="addsug"></div></div>'
        '<button class="tbtn add" onclick="addTicker()">+ Add</button>')
    _holdings_btn = "" if public else '<button class="tool-b" onclick="openTab(\'/holdings\')">Holdings</button>'
    add_html = (
        '<div class="addbar">' + _add_box +
        '<span class="toolsbar">'
        '<button class="tool-b" onclick="openTool(\'evaluate\')">Evaluate</button>'
        '<button class="tool-b" onclick="openTool(\'lookthrough\')">Look-through</button>'
        '<button class="tool-b" onclick="openTool(\'montecarlo\')">Monte Carlo</button>'
        '<button class="tool-b" onclick="openTab(\'/indicators\')">Indicators</button>'
        + _holdings_btn +
        '</span>'
        '<span id="addmsg" class="muted"></span></div>'
    ) if served else ""
    bmc_html = (
        f'<a class="bmc" href="{html.escape(bmc_url)}" target="_blank" rel="noopener">'
        '☕ Buy me a coffee</a>') if bmc_url else ""
    tool_modal = (
        '<div id="toolmodal" class="modal" onclick="closeTool(event)">'
        '<div class="modal-card" onclick="event.stopPropagation()">'
        '<button class="modal-x" onclick="closeTool()">✕</button>'
        '<div id="tool-head" class="tool-head"></div>'
        '<div id="tool-form" class="tool-form"></div>'
        '<div id="tool-out" class="tool-out"></div>'
        '</div></div>'
    ) if served else ""
    js_served = _SERVED_JS if served else ""
    table = "".join(_row_html(r) for r in rows)
    cards = "".join(_card_html(r) for r in rows)
    tiles = _heatmap_html(rows)
    heads = "".join(f'<th onclick="sortBy({i})">{h}</th>' for i, h in enumerate(_HEADERS))
    chips = _chip_bar(rows)
    ok = sum(1 for r in rows if r.price is not None)
    badge = (f'<span class="status {html.escape(status_label)}">{html.escape(status_badge)}</span>'
             if status_badge else "")
    # Served: poll + update-in-place (no full reload). Static file: meta-refresh.
    meta_refresh = "" if served else f'<meta http-equiv="refresh" content="{int(refresh_seconds)}">'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{meta_refresh}
<title>{html.escape(title)}</title><style>{_CSS}{_CSS_EXTRA}</style></head>
<body><div class="wrap">
<header><h1>{html.escape(title)}</h1>{badge}
  <span class="sub" style="margin:0">Updated <span id="updated" data-ts="{int(updated_ts) if updated_ts else ''}">{html.escape(updated)}</span></span></header>
{banner}
<div class="bar">
  <div class="seg">
    <button data-view="table" class="on" onclick="setView('table')">Table</button>
    <button data-view="card" onclick="setView('card')">Cards</button>
    <button data-view="heatmap" onclick="setView('heatmap')">Heatmap</button>
  </div>
  <input id="q" placeholder="Filter tickers…" oninput="applyFilter()">
  <span class="count" id="count">{ok} of {len(rows)} tickers</span>
  <span style="margin-left:auto;display:inline-flex;gap:8px;align-items:center">{bmc_html}
  <button class="tbtn" onclick="toggleTheme()">◐ Theme</button></span>
</div>
{add_html}
<div class="panels">{sector_html}{markets_html}{macro_html}</div>
<div class="chips">{chips}<button class="chip-f" onclick="clearChips()">Clear</button></div>
<div id="view-table" class="view active"><div class="tablewrap"><table class="wl" id="wl">
<thead><tr>{heads}</tr></thead><tbody>{table}</tbody></table></div></div>
<div id="view-card" class="view"><div class="cards">{cards}</div></div>
<div id="view-heatmap" class="view">{tiles}</div>

<div id="modal" class="modal" onclick="closeModal(event)">
  <div class="modal-card" onclick="event.stopPropagation()">
    <button class="modal-x" onclick="closeModal()">✕</button>
    <div id="modal-body"></div>
  </div>
</div>
{tool_modal}

<p class="muted" style="font-size:11.5px;margin-top:14px">
Signals are rule-based indicator states, not investment advice. Free data (yfinance)
may be delayed. All values computed by tested Python.</p>
</div>
<script>
const active = {{signal:new Set(), condition:new Set(), category:new Set(), section:new Set()}};
let view = localStorage.getItem('wl_view') || 'table';
let sortState = {{col:null, dir:1}};

function vals(el, group){{
  if(group==='signal') return [el.dataset.signal];
  if(group==='condition') return (el.dataset.flags||'').split(' ');
  if(group==='category') return (el.dataset.cats||'').split(' ');
  return (el.dataset.secs||'').split(' ');
}}
function matches(el){{
  for(const g in active){{
    if(active[g].size===0) continue;
    const v = vals(el, g);
    let ok=false; active[g].forEach(m=>{{ if(v.includes(m)) ok=true; }});
    if(!ok) return false;
  }}
  return true;
}}
function applyFilter(){{
  const q=(document.getElementById('q').value||'').trim().toUpperCase();
  let n=0, tot=0;
  document.querySelectorAll('#view-'+view+' .item').forEach(el=>{{
    tot++;
    const show = matches(el) && (!q || (el.dataset.ticker||'').includes(q));
    el.style.display = show?'':'none';
    if(show) n++;
  }});
  document.getElementById('count').textContent = n+' of '+tot+' tickers';
  // hide heatmap sector groups that have no visible tiles
  document.querySelectorAll('#view-heatmap .heat-group').forEach(g=>{{
    const any=[...g.querySelectorAll('.item')].some(el=>el.style.display!=='none');
    g.style.display = any?'':'none';
  }});
}}
function toggleChip(btn){{
  const g=btn.dataset.group, m=btn.dataset.match;
  if(active[g].has(m)){{active[g].delete(m); btn.classList.remove('on');}}
  else {{active[g].add(m); btn.classList.add('on');}}
  applyFilter();
}}
function clearChips(){{
  for(const g in active) active[g].clear();
  document.querySelectorAll('.chip-f.on').forEach(b=>b.classList.remove('on'));
  document.getElementById('q').value='';
  applyFilter();
}}
function setView(v){{
  view=v; localStorage.setItem('wl_view', v);
  document.querySelectorAll('.view').forEach(el=>el.classList.remove('active'));
  document.getElementById('view-'+v).classList.add('active');
  document.querySelectorAll('.seg button').forEach(b=>b.classList.toggle('on', b.dataset.view===v));
  applyFilter();
}}
function openCard(card){{
  const body=document.getElementById('modal-body');
  body.innerHTML='<div class="card-item">'+card.innerHTML+'</div>';
  document.getElementById('modal').classList.add('show');
  drawCharts(body);
  if(typeof loadNews==='function') loadNews(body);
}}
const TF_DAYS={{'1mo':31,'3mo':92,'6mo':183,'1y':366,'2y':731,'5y':1827,'max':1e9}};
function drawCharts(root){{
  root.querySelectorAll('.pricechart').forEach(el=>{{
    try{{ el._series=JSON.parse(el.dataset.series); }}catch(e){{ return; }}
    const bar=el.closest('.chart-sec').querySelector('.tfb.on')
             ||el.closest('.chart-sec').querySelector('.tfb');
    renderChart(el, bar?bar.dataset.tf:'1y');
  }});
}}
function chartTf(btn){{
  const sec=btn.closest('.chart-sec');
  sec.querySelectorAll('.tfb').forEach(b=>b.classList.toggle('on', b===btn));
  renderChart(sec.querySelector('.pricechart'), btn.dataset.tf);
}}
function fmtUSD(v){{ return '$'+v.toLocaleString(undefined,{{minimumFractionDigits:2,maximumFractionDigits:2}}); }}
function fmtAxisPrice(v){{ if(Math.abs(v)>=1000) return '$'+(v/1000).toFixed(1)+'k'; return '$'+(v<10?v.toFixed(2):v.toFixed(0)); }}
function fmtDate(iso){{ const d=new Date(iso); return (d.getMonth()+1)+'/'+d.getDate()+'/'+String(d.getFullYear()).slice(2); }}
function niceStep(range, target){{ const raw=(range||1)/Math.max(1,target); const p=Math.pow(10,Math.floor(Math.log10(raw)));
  const nrm=raw/p; const s=nrm<1.5?1:(nrm<3?2:(nrm<7?5:10)); return s*p; }}
function renderChart(el, tf){{
  const s=el._series; if(!s||!s.c||!s.c.length) return;
  const n=s.c.length;
  const days=TF_DAYS[tf]||366;
  const cutoff=new Date(s.d[n-1]).getTime()-days*86400000;
  let start=0; for(let i=0;i<n;i++){{ if(new Date(s.d[i]).getTime()>=cutoff){{ start=i; break; }} }}
  if(start>n-2) start=Math.max(0,n-2);
  const c=s.c.slice(start), d=s.d.slice(start);
  const W=Math.max(280, Math.round(el.clientWidth||340)), H=176;
  const ML=48, MR=10, MT=8, MB=22, x0=ML, x1=W-MR, y0=H-MB, y1=MT;
  let lo=Math.min.apply(null,c), hi=Math.max.apply(null,c);
  const dataLo=lo, pad=(hi-lo)*0.06||1; lo-=pad; hi+=pad; if(dataLo>=0 && lo<0) lo=0;
  const rng=(hi-lo)||1;
  const X=i=> x0 + (c.length<2?0:i/(c.length-1)*(x1-x0));
  const Y=v=> y0 - (v-lo)/rng*(y0-y1);
  const up=c[c.length-1]>=c[0];
  const stroke=up?'var(--up)':'var(--down)';
  const line=c.map((v,i)=>X(i).toFixed(1)+','+Y(v).toFixed(1)).join(' ');
  const area=x0.toFixed(1)+','+y0+' '+line+' '+x1.toFixed(1)+','+y0;
  // y gridlines + labels (nice steps)
  const step=niceStep(hi-lo,4); let grid='', ylab='';
  for(let v=Math.ceil(lo/step)*step; v<=hi+1e-9; v+=step){{ const yy=Y(v).toFixed(1);
    grid+='<line x1="'+x0+'" y1="'+yy+'" x2="'+x1+'" y2="'+yy+'" stroke="var(--border)" stroke-width="0.6" opacity="0.55"/>';
    ylab+='<text x="'+(x0-5)+'" y="'+(parseFloat(yy)+3)+'" text-anchor="end" class="axl">'+fmtAxisPrice(v)+'</text>'; }}
  // x labels: start / mid / end
  let xlab=''; [[0,'start'],[Math.floor((c.length-1)/2),'middle'],[c.length-1,'end']].forEach(([idx,anc])=>{{
    xlab+='<text x="'+X(idx).toFixed(1)+'" y="'+(H-7)+'" text-anchor="'+anc+'" class="axl">'+fmtDate(d[idx])+'</text>'; }});
  const axes='<line x1="'+x0+'" y1="'+y1+'" x2="'+x0+'" y2="'+y0+'" stroke="var(--muted)" stroke-width="1"/>'
            +'<line x1="'+x0+'" y1="'+y0+'" x2="'+x1+'" y2="'+y0+'" stroke="var(--muted)" stroke-width="1"/>';
  el.innerHTML=
    '<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">'
    +grid
    +'<polygon points="'+area+'" fill="'+stroke+'" opacity="0.08"/>'
    +'<polyline points="'+line+'" fill="none" stroke="'+stroke+'" stroke-width="1.6"/>'
    +axes+ylab+xlab
    +'<line class="cx" x1="0" y1="'+y1+'" x2="0" y2="'+y0+'" stroke="var(--muted)" stroke-width="1" style="display:none"/>'
    +'<circle class="cd" r="3.2" fill="'+stroke+'" style="display:none"/></svg>'
    +'<div class="chart-box" style="display:none"></div>';
  el._geom={{c,d,W,H,X,Y,x0,x1,y0,y1}};
  const tip=el.closest('.chart-sec').querySelector('.chart-tip');
  const pct=((c[c.length-1]-c[0])/c[0]*100);
  const base='<b>'+fmtUSD(c[c.length-1])+'</b> · '+(pct>=0?'+':'')+pct.toFixed(1)+'% ('+d[0]+' → '+d[d.length-1]+')';
  if(tip){{ tip.dataset.base=base; tip.innerHTML=base; }}
  el.onmousemove=chartHover; el.onmouseleave=chartLeave; el.ontouchmove=chartHover;
}}
function chartHover(e){{
  const el=e.currentTarget, g=el._geom; if(!g) return;
  const r=el.getBoundingClientRect(), sx=r.width/g.W, sy=r.height/g.H;
  const cx=(e.touches?e.touches[0].clientX:e.clientX)-r.left;
  const plotL=g.x0*sx, plotW=(g.x1-g.x0)*sx;
  const frac=Math.max(0,Math.min(1,(cx-plotL)/(plotW||1)));
  let i=Math.round(frac*(g.c.length-1)); i=Math.max(0,Math.min(g.c.length-1,i));
  const svg=el.querySelector('svg'), cxl=svg.querySelector('.cx'), dot=svg.querySelector('.cd');
  const vx=g.X(i), vy=g.Y(g.c[i]);
  cxl.setAttribute('x1',vx); cxl.setAttribute('x2',vx); cxl.style.display='';
  dot.setAttribute('cx',vx); dot.setAttribute('cy',vy); dot.style.display='';
  const box=el.querySelector('.chart-box');
  box.innerHTML='<div class="cb-d">'+g.d[i]+'</div><div class="cb-p">'+fmtUSD(g.c[i])+'</div>';
  box.style.display='';
  const px=vx*sx, py=vy*sy, bw=box.offsetWidth||70, bh=box.offsetHeight||34;
  let left=px+10; if(left+bw>r.width-2) left=px-bw-10; if(left<2) left=2;
  let top=py-bh-8; if(top<2) top=py+10;
  box.style.left=left+'px'; box.style.top=top+'px';
  const tip=el.closest('.chart-sec').querySelector('.chart-tip');
  if(tip) tip.innerHTML='<b>'+fmtUSD(g.c[i])+'</b> · '+g.d[i];
}}
function chartLeave(e){{
  const el=e.currentTarget, svg=el.querySelector('svg'), box=el.querySelector('.chart-box');
  if(svg){{ svg.querySelector('.cx').style.display='none'; svg.querySelector('.cd').style.display='none'; }}
  if(box) box.style.display='none';
  const tip=el.closest('.chart-sec').querySelector('.chart-tip');
  if(tip&&tip.dataset.base) tip.innerHTML=tip.dataset.base;
}}
function closeModal(e){{
  if(e && e.target && e.target.id!=='modal' && e.type==='click') return;
  document.getElementById('modal').classList.remove('show');
}}
document.addEventListener('keydown', e=>{{ if(e.key==='Escape') closeModal(); }});
function dismissBanner(){{
  const b=document.getElementById('banner'); if(!b) return;
  b.style.display='none'; localStorage.setItem('wl_banner', b.dataset.sig);
}}
function toggleTheme(){{
  const cur=document.documentElement.getAttribute('data-theme');
  const dark=window.matchMedia('(prefers-color-scheme: dark)').matches;
  const next=(cur? cur==='dark' : dark) ? 'light':'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('wl_theme', next);
}}
function sortBy(col){{
  const tb=document.querySelector('#wl tbody');
  const rows=Array.from(tb.querySelectorAll('tr.item'));
  sortState.dir=(sortState.col===col)?-sortState.dir:-1; sortState.col=col;
  rows.sort((a,b)=>{{
    const av=parseFloat(a.children[col]?.dataset.sort ?? 'NaN');
    const bv=parseFloat(b.children[col]?.dataset.sort ?? 'NaN');
    if(isNaN(av)&&isNaN(bv)) return 0; if(isNaN(av)) return 1; if(isNaN(bv)) return -1;
    return (av-bv)*sortState.dir;
  }});
  rows.forEach(r=>tb.appendChild(r));
}}
function fmtUpdated(){{
  const up=document.getElementById('updated');
  if(up && up.dataset.ts){{
    const d=new Date(parseInt(up.dataset.ts,10));
    if(!isNaN(d)) up.textContent=d.toLocaleString(undefined,
      {{weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}})
      +' '+(Intl.DateTimeFormat().resolvedOptions().timeZone||'local');
  }}
}}
function wireTableScroll(){{
  document.querySelectorAll('.tablewrap').forEach(w=>{{
    if(w._wired) return; w._wired=1;
    const upd=()=>w.classList.toggle('scrolled', w.scrollLeft>2);
    w.addEventListener('scroll', upd, {{passive:true}}); upd();
  }});
}}
const REFRESH_MS = {int(refresh_seconds)}*1000;
const SERVED = {"true" if served else "false"};
(function init(){{
  const t=localStorage.getItem('wl_theme'); if(t) document.documentElement.setAttribute('data-theme', t);
  const b=document.getElementById('banner');
  if(b && localStorage.getItem('wl_banner')===b.dataset.sig) b.style.display='none';
  setView(view);
  fmtUpdated();
  wireTableScroll();
  // poll only while a session is active (short interval); no updates when the
  // market is closed after 8pm ET or on weekends (long interval).
  if(SERVED && typeof refreshData==='function' && REFRESH_MS>0 && REFRESH_MS<=3600000)
    setInterval(refreshData, Math.max(30000, REFRESH_MS));
}})();
{js_served}
</script>
</body></html>"""
