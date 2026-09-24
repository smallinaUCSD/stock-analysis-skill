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

from ..dashboard.render import _CSS, _THEME_BOOT, icon
from ..trade import atr_trade_setup, position_size, suggest_options

_SIG_CLASS = {"BUY": "buy", "SELL": "sell", "SHORT": "short", "HOLD": "hold"}
# human labels for ticker-file sections (acronyms kept, everything else sentence case)
_SECTION_LABEL = {"M7": "M7", "AI-DATACENTER": "AI datacenter", "NASDAQ100": "Nasdaq 100",
                  "DOW": "Dow", "INTL": "International", "SEMIS": "Semiconductors",
                  "LEVERAGED": "Leveraged long", "LEVERAGED-BEAR": "Leveraged bear"}
# sections that stay on the board but get no filter chip
_HIDDEN_SECTION_CHIPS = {"TICKERS", "ADDED", "DOW"}


def _section_label(sec: str) -> str:
    return _SECTION_LABEL.get(sec) or sec.replace("-", " ").capitalize()
_FLAG_LABEL = {
    "oversold": "Oversold", "overbought": "Overbought", "surge": "Surge",
    "crash": "Crash", "squeeze": "Squeeze", "vol_spike": "Vol spike",
    "near_52w_high": "52w high", "near_52w_low": "52w low",
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
/* ---- controls ---------------------------------------------------------- */
.tbtn,.tool-b,.icon-btn,.chip-f,.seg button,.tfb,.analysis-btn button,.modal-x{
  transition:background-color .15s var(--ease-out),border-color .15s var(--ease-out),
    color .15s var(--ease-out),box-shadow .15s var(--ease-out),transform .12s var(--ease-out)}
.tbtn:active,.tool-b:active,.icon-btn:active,.chip-f:active,.seg button:active,
.tfb:active,.analysis-btn button:active,.modal-x:active{transform:scale(.97)}
.tbtn,.tool-b{display:inline-flex;align-items:center;gap:6px;height:40px;padding:0 16px;
  font-size:14px;font-weight:500;line-height:1;border-radius:var(--r);cursor:pointer;
  background:var(--bg);border:1px solid var(--border);color:var(--ink);
  text-decoration:none;white-space:nowrap}
.tbtn:hover,.tool-b:hover{border-color:var(--border-strong)}
.tbtn.add{background:var(--accent);border-color:transparent;color:var(--accent-ink);padding:0 20px}
.tbtn.add:active{background:var(--accent-press)}
.icon-btn{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;
  padding:0;border-radius:50%;border:1px solid var(--border);background:var(--bg);
  color:var(--ink);cursor:pointer}
.icon-btn:hover{border-color:var(--border-strong)}
/* ---- header + toolbar ---------------------------------------------------- */
.wrap{max-width:min(2400px,100%);padding:18px clamp(14px,2.6vw,40px)}
.top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}
.top-l{display:flex;align-items:center;gap:6px 10px;flex-wrap:wrap;min-width:0;flex:1}
.top-l h1{font-size:36px}
.top-l .sub{margin:0;font-size:13px;color:var(--muted)}
.top-r{display:flex;align-items:center;gap:8px}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0 10px}
.search{position:relative;display:flex;align-items:center;flex:0 1 240px}
.search .ic{position:absolute;left:12px;color:var(--muted);pointer-events:none}
.bar input,#addq{width:100%;height:40px;font-size:14px;padding:0 14px;border-radius:var(--r);
  border:1px solid var(--border);background:var(--bg);color:var(--ink);
  transition:border-color .15s var(--ease-out),box-shadow .15s var(--ease-out)}
.search input{padding-left:36px}
.bar input::placeholder,#addq::placeholder{color:var(--muted)}
.bar input:focus-visible,#addq:focus-visible,.t-row input:focus-visible,.t-row select:focus-visible{
  outline:none;border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 15%,transparent)}
.count{color:var(--muted);font-size:13px;white-space:nowrap}
.seg{display:inline-flex;gap:2px}
.seg button{height:36px;padding:0 14px;font-size:14px;font-weight:500;border:none;border-radius:var(--r);
  background:transparent;color:var(--muted);cursor:pointer}
.seg button:hover{color:var(--ink)}
.seg button.on{background:var(--surface-2);color:var(--ink)}
.toolsbar{display:flex;flex-wrap:wrap;gap:6px;margin-left:auto}
@media (max-width:640px){
  .search{flex:1 1 100%}
  .toolsbar{margin-left:0;width:100%;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;
    -webkit-mask-image:linear-gradient(90deg,#000 88%,transparent);mask-image:linear-gradient(90deg,#000 88%,transparent)}
  .toolsbar::-webkit-scrollbar{display:none}
}
/* add bar (served) */
.addbar{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin:0 0 14px}
.addwrap{position:relative;flex:1 1 220px;max-width:560px}
.addsug{display:none;position:absolute;z-index:60;left:0;right:0;top:calc(100% + 6px);
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;
  box-shadow:var(--shadow-pop)}
.sug{padding:8px 12px;font-size:14px;cursor:pointer;display:flex;gap:10px;align-items:baseline}
.sug:hover{background:var(--surface-2)} .sug b{color:var(--ink);font-family:var(--font-mono);font-weight:500}
.sug span{color:var(--muted);font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#addmsg{font-size:13px;line-height:1.5}
#addmsg.ok,#addmsg .ok{color:var(--up)} #addmsg.bad,#addmsg .bad{color:var(--down)}
.addsg{color:var(--link);text-decoration:underline;text-underline-offset:3px;cursor:pointer}
/* ---- filter chips: labeled groups ----------------------------------------- */
.chips{display:grid;gap:7px;margin:4px 0 16px;padding:12px 14px;border:1px solid var(--border);
  border-radius:var(--r-lg);background:var(--surface)}
.cgroup{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.cglab{flex:0 0 96px;font-size:13px;font-weight:500;color:var(--muted)}
@media (max-width:640px){.cglab{flex-basis:100%}}
.chip-f{display:inline-flex;align-items:center;gap:6px;height:28px;padding:0 12px;font-size:14px;
  font-weight:500;border-radius:999px;cursor:pointer;background:transparent;
  border:1px solid var(--border);color:var(--ink-2)}
.chip-f:hover{border-color:var(--border-strong);color:var(--ink)}
.chip-f.on{background:var(--surface-3);border-color:var(--border-strong);color:var(--ink)}
.chip-f small{opacity:.6}
.chip-f.clear{margin-left:auto;border-style:dashed;color:var(--muted)}
.dot{width:7px;height:7px;border-radius:50%;flex:0 0 auto;background:var(--muted)}
.dot.buy{background:var(--up)} .dot.short{background:var(--down)} .dot.sell{background:var(--warn)}
.dot.hold{background:transparent;box-shadow:inset 0 0 0 1.5px var(--muted)}
.empty{display:none;padding:34px 16px;text-align:center;color:var(--muted);font-size:14px;
  border:1px dashed var(--border-strong);border-radius:var(--r-lg);margin-top:4px}
.empty.show{display:block}
.empty b{display:block;color:var(--ink);font-family:var(--font-display);font-size:28px;font-weight:500;margin-bottom:6px}
/* ---- table ------------------------------------------------------------------ */
.tablewrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--border);
  border-radius:var(--r-lg);background:var(--surface)}
table.wl{border-collapse:collapse;width:100%;font-size:14px;min-width:900px}
table.wl th,table.wl td{padding:8px 11px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--border)}
table.wl tr:last-child td{border-bottom:none}
table.wl th{position:sticky;top:0;z-index:2;background:var(--surface-2);color:var(--muted);font-weight:500;
  text-transform:uppercase;letter-spacing:1.5px;font-size:12px;cursor:pointer;user-select:none}
table.wl th:hover{color:var(--ink)}
table.wl th:first-child,table.wl td:first-child{text-align:left;position:sticky;left:0;
  background:var(--surface);box-shadow:1px 0 0 var(--border)}
table.wl th:first-child{background:var(--surface-2)}
table.wl td:first-child{z-index:1}
table.wl th:first-child{z-index:3}
.tablewrap.scrolled table.wl th:first-child,.tablewrap.scrolled table.wl td:first-child{
  box-shadow:8px 0 12px -8px rgba(0,0,0,.4)}
table.wl tr.item{cursor:default}
table.wl tr.item:hover td,table.wl tr.item:hover td:first-child{background:var(--surface-2)}
/* left-align Sector (9), Conf (14), Indicators (15) */
table.wl th:nth-child(9),table.wl td:nth-child(9),
table.wl th:nth-child(14),table.wl td:nth-child(14),
table.wl th:nth-child(15),table.wl td:nth-child(15){text-align:left}
.tk{font-family:var(--font-mono);font-weight:500}
.nm{color:var(--muted);font-size:13px;font-weight:400}
.badge{display:inline-block;font-weight:500;font-size:12px;letter-spacing:1.5px;text-transform:uppercase;padding:2px 7px;
  border-radius:var(--r-sm);color:var(--muted);background:var(--surface-2)}
.badge.buy{color:var(--up);background:color-mix(in srgb,var(--up) 15%,transparent)}
.badge.short{color:var(--down);background:color-mix(in srgb,var(--down) 15%,transparent)}
.badge.sell{color:var(--warn);background:color-mix(in srgb,var(--warn) 15%,transparent)}
.chip{display:inline-block;font-size:13px;font-weight:500;padding:1px 6px;border-radius:5px;margin:1px;
  background:var(--surface-2);border:1px solid var(--border);color:var(--ink-2)}
.chip.g{color:var(--up);border-color:color-mix(in srgb,var(--up) 45%,transparent)}
.chip.r{color:var(--down);border-color:color-mix(in srgb,var(--down) 45%,transparent)}
.up{color:var(--up)}.down{color:var(--down)}.muted{color:var(--muted)}
.arrow.up{color:var(--up)}.arrow.down{color:var(--down)}.arrow.flat{color:var(--muted)}
.conf-STRONG{color:var(--good);font-weight:500}.conf-MODERATE{color:var(--warn);font-weight:500}.conf-WEAK{color:var(--muted)}
/* ---- cards --------------------------------------------------------------------- */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(270px,100%),1fr));gap:12px}
.card-item{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);
  padding:14px 16px 12px;cursor:pointer;position:relative;
  transition:border-color .15s var(--ease-out),box-shadow .15s var(--ease-out)}
.card-item:hover{border-color:var(--border-strong)}
.card-top{display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:nowrap}
.card-top>div:first-child{min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.card-top .tk{font-size:14px}
.card-price{font-size:22px;font-weight:500;white-space:nowrap;flex:0 0 auto}
.card-price .chg{font-size:13px;font-weight:500;margin-left:2px}
.card-row{display:flex;justify-content:space-between;font-size:13px;margin-top:4px;color:var(--muted)}
.card-row b{color:var(--ink);font-weight:500}
.card-spark{margin:8px 0}
.links{margin-top:10px;display:flex;flex-wrap:wrap;gap:4px 10px}
.links a,.details-cta span{text-decoration:underline;text-decoration-color:transparent;
  text-underline-offset:3px;transition:color .15s ease,text-decoration-color .15s ease}
.links a{font-size:13px;color:var(--muted)}
.links a:hover,.details-cta:hover span{color:var(--link);text-decoration-color:currentColor}
.trendline{font-size:13px;font-weight:500;margin:2px 0 6px;display:flex;align-items:center;gap:6px}
.tscore{font-size:13px;font-weight:500;color:var(--muted);padding:0 5px;border-radius:5px;
  background:var(--surface-2)}
.fchip{min-height:36px;margin:0 0 4px;font-size:13px;font-weight:500;line-height:1.35}
.fchip .fpill{display:inline-flex;align-items:baseline;gap:7px;max-width:100%;color:var(--ink-2)}
.fchip .fscore{font-weight:500;font-size:13px;min-width:22px;padding:0 5px;border-radius:5px;
  text-align:center;background:var(--surface-2)}
.fchip .fscore.up{color:var(--good);background:color-mix(in srgb,var(--good) 14%,transparent)}
.fchip .fscore.down{color:var(--crit);background:color-mix(in srgb,var(--crit) 14%,transparent)}
.details-cta{display:flex;align-items:center;justify-content:space-between;margin-top:10px;
  padding-top:9px;border-top:1px solid var(--border);font-size:13px;font-weight:500;color:var(--muted)}
.details-cta svg{transition:color .15s ease}
.details-cta:hover svg{color:var(--link)}
.analysis-btn{display:flex;gap:10px;width:100%;margin:14px 0 6px}
.analysis-btn button{flex:1;display:flex;align-items:center;justify-content:center;gap:8px;height:40px;
  border-radius:var(--r);cursor:pointer;font:500 14px var(--font);border:1px solid transparent}
.analysis-btn .cta-1{background:var(--accent);color:var(--accent-ink)}
.analysis-btn .cta-1:active{background:var(--accent-press)}
.analysis-btn .cta-2{background:var(--surface);color:var(--ink);border-color:var(--border)}
.analysis-btn .cta-2:hover{background:var(--surface-2)}
.site-help{color:var(--link);text-decoration:none;font-weight:500}.site-help:hover{text-decoration:underline}
.site-note{color:var(--muted);font-size:13px;margin-top:18px;line-height:1.5}
.site-foot{color:var(--on-band-soft);background:var(--band);font-size:13px;text-align:center;
  margin:24px 0 4px;padding:22px 16px;border-radius:var(--r-lg)}
/* fixed-height slots so optional lines don't misalign cards */
.exthrs{font-size:13px;color:var(--muted);margin:1px 0 5px;min-height:16px}
.exthrs b{color:var(--ink);font-weight:500}
.erow{min-height:23px;margin-bottom:2px;display:flex;align-items:flex-start}
.erflag{display:inline-block;font-size:13px;font-weight:500;padding:2px 7px;border-radius:var(--r-sm);margin:0}
.erflag.er-now{color:var(--crit);background:color-mix(in srgb,var(--crit) 15%,transparent)}
.erflag.er-soon{color:var(--warn);background:color-mix(in srgb,var(--warn) 15%,transparent)}
.erflag.er-wk{background:var(--surface-2);color:var(--muted)}
.tsetup{margin-top:8px;padding:8px 10px;border-radius:var(--r);border:1px solid var(--border);background:var(--surface-2)}
.tsetup.buy{border-color:color-mix(in srgb,var(--up) 50%,transparent)}
.tsetup.short{border-color:color-mix(in srgb,var(--down) 50%,transparent)}
.ts-h{font-size:13px;font-weight:500;color:var(--ink-2);margin-bottom:4px}
.ts-row{display:flex;justify-content:space-between;font-size:13px}
.opts{margin-top:2px;font-size:13px}
.card-detail{display:none;margin-top:10px;padding-top:10px;border-top:1px solid var(--border);cursor:default}
/* ---- modal ------------------------------------------------------------------------ */
@keyframes backdrop-in{from{opacity:0}to{opacity:1}}
@keyframes sheet-in{from{opacity:0;transform:translateY(8px) scale(.985)}to{opacity:1;transform:none}}
.modal{display:none;position:fixed;inset:0;z-index:100;justify-content:center;padding:32px 16px;overflow:auto;
  background:color-mix(in srgb,var(--bg) 62%,transparent)}
.modal.show{display:flex;animation:backdrop-in .18s var(--ease-out)}
.modal.show .modal-card{animation:sheet-in .22s var(--ease-out)}
.modal-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-xl);
  padding:20px 22px;max-width:480px;width:100%;height:max-content;position:relative;box-shadow:var(--shadow-modal)}
.modal-x{position:absolute;top:12px;right:12px;width:36px;height:36px;z-index:2;display:flex;align-items:center;
  justify-content:center;border:1px solid var(--border);border-radius:50%;background:var(--bg);
  color:var(--ink);cursor:pointer}
.modal-x:hover{border-color:var(--border-strong)}
#modal-body .card-detail{display:block}
#modal-body .details-cta,#modal-body .card-spark,#modal-body .erow:empty,#modal-body .exthrs:empty{display:none}
#modal-body .card-item{cursor:default;border:none;padding:0;box-shadow:none}
#modal-body .card-top{padding-right:44px}
#modal .modal-card{max-width:1100px;padding:24px 26px}
.mx-head{margin-bottom:12px}
.mx-chart .chart-sec{margin-top:0}
.mx-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px 30px;align-items:start;
  margin-top:20px;padding-top:18px;border-top:1px solid var(--border)}
.mx-grid>div{min-width:0}
.mx-grid .det-sec:first-child,.mx-sum>:first-child{margin-top:0}
.mx-grid .det-h{margin-bottom:8px}
.mx-grid .card-row{margin-top:0;padding:4px 0;gap:12px}
.mx-grid .card-row b{text-align:right}
.mx-grid .det-sec+.det-sec{margin-top:18px}
.mx-sum .trendline{margin:0 0 6px}
.mx-sum .fchip{min-height:0;margin:0 0 8px}
.mx-sum .links{margin-top:10px!important}
.mx-news{margin-top:22px;padding-top:16px;border-top:1px solid var(--border)}
.mx .analysis-btn{margin:22px 0 2px}
@media (max-width:900px){.mx-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:620px){.mx-grid{grid-template-columns:1fr}}
.bmc{display:inline-flex;align-items:center;height:32px;font-size:13px;font-weight:500;padding:0 12px;
  border-radius:var(--r);text-decoration:none;background:#ffdd57;color:#3a2f00;border:1px solid #e6c200;white-space:nowrap}
.bmc:hover{filter:brightness(1.04)}
/* tool modal */
.tool-head h3{margin:0 44px 12px 0;font-family:var(--font-display);font-size:28px;font-weight:500;letter-spacing:-.02em}
.tool-form{margin-bottom:10px}
.t-row{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px}
.t-row input,.t-row select{height:34px;padding:0 10px;border-radius:var(--r);border:1px solid var(--border);
  background:var(--surface);color:var(--ink);font-size:14px}
.t-row input{flex:1 1 120px;min-width:90px}
.tool-out{min-height:20px}
.t-kv{display:flex;justify-content:space-between;gap:12px;padding:4px 0;font-size:14px;border-bottom:1px solid var(--border)}
.t-kv span{color:var(--muted)} .t-kv b{text-align:right;font-weight:500}
.t-kv b.up{color:var(--up)} .t-kv b.down{color:var(--down)}
.t-h{font-size:13px;font-weight:500;color:var(--ink-2);margin:12px 0 4px}
.t-note{font-size:13px;color:var(--muted);margin-top:8px;line-height:1.5}
.t-err{color:var(--down);font-size:14px;padding:6px 0}
.t-fac{font-size:13px;padding:5px 0;border-bottom:1px solid var(--border)}
.t-fac b{font-size:13px;font-weight:500;padding:1px 6px;border-radius:5px;margin-right:6px;text-transform:capitalize}
.t-fac.support b{color:var(--good);background:color-mix(in srgb,var(--good) 15%,transparent)}
.t-fac.against b{color:var(--crit);background:color-mix(in srgb,var(--crit) 15%,transparent)}
.t-fac.neutral b{background:var(--surface-2);color:var(--muted)}
.mc-row{display:grid;grid-template-columns:34px 1fr 62px;align-items:center;gap:8px;font-size:13px;padding:2px 0}
.mc-row span{color:var(--muted)} .mc-row b{text-align:right;font-weight:500}
.mc-row b.up{color:var(--up)} .mc-row b.down{color:var(--down)}
.mc-bar{height:8px;background:var(--surface-2);border-radius:4px;overflow:hidden}
.mc-fill{height:8px;border-radius:4px} .mc-fill.up{background:var(--up)} .mc-fill.down{background:var(--down)}
/* ---- panels ------------------------------------------------------------------------ */
.panels{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:12px}
@media (max-width:980px){.panels{grid-template-columns:1fr 1fr}}
@media (max-width:640px){.panels{grid-template-columns:1fr}}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);padding:12px 16px 14px}
.panel-h{display:flex;align-items:baseline;justify-content:space-between;gap:8px;
  font-size:16px;font-weight:500;color:var(--ink);margin-bottom:10px}
.ph-tag{font-size:13px;font-weight:500;color:var(--muted)}
.panel-body{overflow:visible}
.mkgroup{font-size:13px;font-weight:500;color:var(--muted);margin:10px 0 3px}
.mkgroup:first-child{margin-top:0}
.mkrow{display:grid;grid-template-columns:1fr auto 64px 64px;align-items:baseline;gap:8px;padding:2px 0;font-size:14px}
.mkpts{text-align:right;font-variant-numeric:tabular-nums}
.mkpts.up{color:var(--up)} .mkpts.down{color:var(--down)}
.mkname{color:var(--ink)}
.mkpx{color:var(--muted)}
.mkchg{text-align:right;font-weight:500}
.mkchg.up{color:var(--up)} .mkchg.down{color:var(--down)}
.macro-fg{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font-size:14px;padding:2px 0}
.macro-fomc{font-size:14px;padding:2px 0}
.macro-fomc b{font-weight:500}
.macro-ev{display:block;text-decoration:none;color:var(--ink);font-size:13px;line-height:1.4;
  padding:5px 0;border-bottom:1px solid var(--border)}
.macro-ev:last-child{border-bottom:none}
a.macro-ev:hover{color:var(--link)}
.secrow{display:grid;grid-template-columns:120px 1fr 56px;align-items:center;gap:8px;padding:2px 0;font-size:13px}
.secname{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--ink-2)}
.secbar{display:flex;align-items:center;height:12px}
.sechalf{flex:1;display:flex;height:8px}.sechalf.neg{justify-content:flex-end}
.secaxis{width:1px;height:12px;background:var(--axis)}
.fill-up{height:8px;border-radius:3px;background:var(--up)}
.fill-down{height:8px;border-radius:3px;background:var(--down)}
.secval{text-align:right;font-weight:500}
/* ---- card detail (modal) -------------------------------------------------------- */
.det-sec{margin-top:12px}
.det-h{font-size:13px;font-weight:500;color:var(--ink-2);margin-bottom:5px}
.det-row{display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:1px 0}
.det-row b{text-align:right;font-weight:500}
.det-line{font-size:13px;line-height:1.5;padding:1px 0}
.det-line b{font-weight:500}
.det-note{font-size:13px;color:var(--muted);margin-top:4px;line-height:1.45}
.ts-sub{font-size:13px;color:var(--muted);margin-bottom:4px}
.stance{font-size:13px;font-weight:500;padding:2px 8px;border-radius:999px;margin-left:6px}
.stance.pos{color:var(--good);background:color-mix(in srgb,var(--good) 15%,transparent)}
.stance.neg{color:var(--crit);background:color-mix(in srgb,var(--crit) 15%,transparent)}
.stance.midtone{color:var(--warn);background:color-mix(in srgb,var(--warn) 15%,transparent)}
.stance.mid{background:var(--surface-2);color:var(--muted)}
.fvtable{width:100%;border-collapse:collapse;font-size:13px;margin:4px 0}
.fvtable th{text-align:left;color:var(--muted);font-size:13px;font-weight:500;padding:2px 0}
.fvtable td{padding:3px 0}
.fvtable td.fl{font-weight:500} .fvtable td.fl.up{color:var(--up)} .fvtable td.fl.down{color:var(--down)}
.fvtable td.fv{text-align:right;font-weight:500;padding-right:12px}
.fvtable td:last-child{text-align:right;color:var(--muted)}
/* price chart */
.chart-sec .tfbar{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px}
.tfb{height:24px;font-size:13px;font-weight:500;padding:0 9px;border-radius:999px;cursor:pointer;
  background:transparent;border:1px solid var(--border);color:var(--muted)}
.tfb:hover{color:var(--ink);border-color:var(--border-strong)}
.tfb.on{background:var(--surface-3);border-color:var(--border-strong);color:var(--ink)}
.pricechart{position:relative;width:100%;touch-action:none}
.pricechart svg{display:block;width:100%;height:auto;overflow:visible}
.pricechart .axl{fill:var(--muted);font-size:9px;font-family:inherit}
.chart-box{position:absolute;pointer-events:none;z-index:5;background:var(--surface);
  border:1px solid var(--border);border-radius:var(--r);padding:4px 8px;font-size:13px;
  line-height:1.35;box-shadow:var(--shadow-pop);white-space:nowrap}
.chart-box .cb-d{color:var(--muted);font-size:13px}
.chart-box .cb-p{font-weight:500}
.chart-tip{font-size:13px;margin-top:6px;min-height:15px}
.chart-tip b{color:var(--ink)}
/* recent news */
.nw{display:block;text-decoration:none;padding:7px 0;border-bottom:1px solid var(--border)}
.nw:last-child{border-bottom:none}
a.nw:hover .nw-t{color:var(--link)}
.nw-t{font-size:14px;color:var(--ink);line-height:1.4}
.nw-m{font-size:13px;color:var(--muted);margin-top:2px}
/* ---- heatmap ----------------------------------------------------------------------- */
.heat{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px}
.heat-group{margin-bottom:18px}
.heat-h{font-size:16px;font-weight:500;color:var(--ink);margin:0 0 8px;padding-bottom:6px;
  border-bottom:1px solid var(--border)}
.tile-item{border:1px solid var(--border);border-radius:var(--r);padding:10px 12px;text-align:center}
.tile-item .t{font-weight:500;font-size:14px;font-family:var(--font-mono)}
.tile-item .c{font-size:16px;font-weight:500;margin-top:2px}
.tile-item .s{font-size:13px;color:var(--muted)}
.view{display:none}.view.active{display:block}
/* ---- alert marquee ------------------------------------------------------------------ */
.banner{display:flex;align-items:center;gap:10px;padding:8px 8px 8px 14px;margin:0 0 4px;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);font-size:13px}
.banner-vp{flex:1;overflow:hidden;-webkit-mask-image:linear-gradient(90deg,transparent,#000 3%,#000 97%,transparent);
  mask-image:linear-gradient(90deg,transparent,#000 3%,#000 97%,transparent)}
.banner-track{display:inline-flex;gap:28px;white-space:nowrap;animation:marquee 45s linear infinite;will-change:transform}
.banner:hover .banner-track{animation-play-state:paused}
@keyframes marquee{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.banner .a{white-space:nowrap;display:inline-flex;align-items:center;gap:7px;color:var(--ink-2)}
.banner .dot.a-up{background:var(--up)} .banner .dot.a-down{background:var(--down)}
.banner .dot.a-warn{background:var(--warn)} .banner .dot.a-info{background:var(--accent)}
.banner .x{flex:0 0 auto}
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
        c.append('<span class="chip g">Cloud↑</span>')
    elif r.ichimoku == "below":
        c.append('<span class="chip r">Cloud↓</span>')
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
    return "".join(c) or '<span class="muted">-</span>'


# ---------- per-view renderers ---------- #
_HEADERS = ["Ticker", "Price", "Day", "5D", "1M", "1Y", "52wL", "52wH", "Sector",
            "30d", "Signal", "Trend", "RSI", "Conf", "Indicators", "P/E", "Mkt Cap",
            "Beta", "Factor"]


def _factor_cls(pct):
    if pct is None:
        return "muted"
    return "up" if pct >= 66 else ("down" if pct <= 33 else "")


def _factor_cell(r):
    """Table cell: the composite factor percentile (sortable), color-coded."""
    comp = (getattr(r, "factor", None) or {}).get("composite")
    if comp is None:
        return '<td class="muted" data-sort="-1">-</td>'
    return f'<td class="{_factor_cls(comp)}" data-sort="{comp}">{comp}</td>'


def _factor_chip(r):
    """Card chip in a fixed-height slot (so 1- vs 2-line reads don't misalign
    cards): the plain-English factor read + composite percentile."""
    f = getattr(r, "factor", None) or {}
    comp, label = f.get("composite"), f.get("label")
    if comp is None or not label:
        return '<div class="fchip"></div>'          # empty slot keeps cards aligned
    read = html.escape(label.replace(" · ", ", ")).capitalize()
    return (f'<div class="fchip"><span class="fpill" title="Factor composite percentile">'
            f'<span class="fscore {_factor_cls(comp)}">{comp}</span>{read}</span></div>')


def _row_html(r):
    if r.error or r.price is None:
        return (f'<tr class="item" {_data_attrs(r)}><td class="tk">{html.escape(r.ticker)}</td>'
                f'<td colspan="{len(_HEADERS) - 1}" class="muted">no data</td></tr>')

    def cell(x):
        cls, txt = _pct(x)
        return f'<td class="{cls}" data-sort="{x if x is not None else -999}">{txt}</td>'

    def money_cell(x):
        return (f'<td data-sort="{x if x is not None else -1}">'
                f'{("$"+format(x, ",.0f")) if x is not None else "n/a"}</td>')

    sig_cls = _SIG_CLASS.get(r.signal, "hold")
    arrow_cls = "up" if r.trend_score > 1 else ("down" if r.trend_score < -1 else "flat")
    rsi_cls = "up" if (r.rsi or 50) >= 70 else ("down" if (r.rsi or 50) <= 30 else "")
    conf = (f'<span class="conf-{r.confidence}">{r.confidence.capitalize()}</span>'
            if r.confidence else '<span class="muted">-</span>')
    sector = html.escape((_abbr_sector(r.sector) or "-")[:16])
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
        f'<td data-sort="{r.beta if r.beta is not None else -99}">{_num(r.beta, 2)}</td>'
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
        '<div class="ts-sub">no active signal - illustrative ATR setup, direction from trend</div>'
    # Regime & trend context (Dai-Zhang-Zhu P(bull) + time-series momentum).
    rg = getattr(r, "regime", None) or {}
    regime_line = ""
    if rg.get("state"):
        pb = rg.get("p_bull")
        pbt = f' (P bull {pb*100:.0f}%)' if pb is not None else ''
        tml = f' · TS-mom {html.escape(rg["tsmom_label"])}' if rg.get("tsmom_label") else ''
        cls_rg = "up" if rg["state"] == "bull" else ("down" if rg["state"] == "bear" else "muted")
        regime_line = (f'<div class="ts-sub">Regime · <span class="{cls_rg}">{rg["state"]}'
                       f'</span>{pbt}{tml}</div>')
    if rg.get("stop_helps") is not None:
        prem = rg.get("stop_premium")
        verdict = "helped" if rg["stop_helps"] else "hurt"
        vcls = "up" if rg["stop_helps"] else "down"
        premtxt = f' ({prem*100:+.0f}%/yr)' if prem is not None else ''
        regime_line += (f'<div class="ts-sub">Stop study · a trailing stop would have '
                        f'<span class="{vcls}">{verdict}{premtxt}</span> '
                        f'<span class="muted">(stops help in trends, hurt in chop)</span></div>')
    # P(target before stop) - a first-passage probability from drift/vol; the
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
        f'({s.rr_ratio:.0f}:1 R:R)</div>{illustrative}{regime_line}'
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
    return f'<div class="det-sec"><div class="det-h">Options ideas</div><div class="opts">{chips}</div></div>'


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
    header = (f'<div class="det-h">Stock analyzer - valuation '
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
        band = (f' <span class="muted" style="font-weight:400">· P5-P95 ${p5:,.0f}-${p95:,.0f}</span>'
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


_TIMEFRAMES = [("5d", "1W"), ("1mo", "1M"), ("3mo", "3M"), ("6mo", "6M"),
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


def _kv(label, value, cls="", title=""):
    """One label-left / value-right row, the same in every quick-look column."""
    t = f' title="{html.escape(title, quote=True)}"' if title else ""
    return f'<div class="card-row"{t}><span>{label}</span><b class="{cls}">{value}</b></div>'


def _valuation_summary(r):
    """Valuation for the modal: verdict, base fair value, Monte Carlo chance it's
    undervalued, and the reverse DCF (growth the price assumes vs reported)."""
    payload = r.valuation or {}
    v = payload.get("valuation") if "valuation" in payload else payload
    v = v or {}
    if not v.get("reliable"):
        return ""                      # ETFs / no cash flows: the full analysis explains why
    mos = v.get("margin_of_safety") or 0.0
    stance = "Undervalued" if mos >= 0.10 else ("Overvalued" if mos <= -0.10 else "Fairly valued")
    scls = "up" if mos >= 0.10 else ("down" if mos <= -0.10 else "")
    rows = [_kv("Verdict", stance, scls)]
    if v.get("base"):
        rows.append(_kv("Fair value (base)", f'${v["base"]:,.0f}'))
    if v.get("mc_prob_undervalued") is not None:
        rows.append(_kv("Chance undervalued", f'{v["mc_prob_undervalued"]*100:.0f}%',
                        title="Monte Carlo DCF: share of simulated fair values above today's price"))
    ig = v.get("implied_market_growth")
    if ig is not None:
        rows.append(_kv("Price assumes", f"{ig*100:.0f}%/yr growth",
                        title="Reverse DCF: the 10-year growth rate that justifies today's price"))
        asm = v.get("assumptions") or {}
        grew = asm.get("reported_growth")
        src = (asm.get("growth_source") or "").split(",")[0].replace(" growth", "")
        if grew is not None and src and not src.startswith("default"):
            rows.append(_kv("Reported growth", f"{grew*100:.0f}% {html.escape(src)}"))
    return f'<div class="det-sec"><div class="det-h">Valuation</div>{"".join(rows)}</div>'


def _regime_summary(r):
    """Regime + 12-month trend for the modal."""
    rg = r.regime or {}
    rows = []
    if rg.get("state"):
        rows.append(_kv("Regime", html.escape(rg["state"].capitalize())))
    if rg.get("p_bull") is not None:
        pb = rg["p_bull"]
        rows.append(_kv("Chance of a bull regime", f"{pb*100:.0f}%",
                        "up" if pb >= 0.6 else ("down" if pb <= 0.4 else "")))
    if rg.get("tsmom_label"):
        rows.append(_kv("12-month trend", html.escape(rg["tsmom_label"].capitalize())))
    if not rows:
        return ""
    return f'<div class="det-sec"><div class="det-h">Regime &amp; trend</div>{"".join(rows)}</div>'


def _volume_summary(r):
    """Volume / money-flow read for the modal."""
    vs = getattr(r, "volume_signal", None) or {}
    if not vs.get("label"):
        return ""
    st = vs.get("state", "")
    cls = "up" if st in ("accumulation", "bullish-divergence") else \
          ("down" if st in ("distribution", "bearish-divergence") else "")
    rows = [_kv("Read", html.escape(vs["label"].capitalize()), cls)]
    if getattr(r, "mfi", None) is not None:
        rows.append(_kv("Money flow (MFI)", f"{r.mfi:.0f}"))
    return f'<div class="det-sec vol-sec"><div class="det-h">Volume</div>{"".join(rows)}</div>'


_BETA_TIP = ("Beta vs the S&P 500 over the last year (Welch slope-winsorized estimate). "
             "1.5 = tends to move 1.5x the market.")


def _risk_summary(r):
    """Risk vs the market for the modal: beta vs S&P 500 / Nasdaq-100, alpha
    (flagged when it's statistically just noise), Sharpe, drawdown, capture."""
    rk = getattr(r, "risk", None) or {}
    spy, qqq = rk.get("SPY") or {}, rk.get("QQQ") or {}
    if not spy:
        return ""
    rows = [_kv("Beta vs S&amp;P 500", _num(spy.get("beta"), 2), title=_BETA_TIP)]
    if qqq.get("beta") is not None:
        rows.append(_kv("Beta vs Nasdaq-100", _num(qqq.get("beta"), 2)))
    a = spy.get("alpha")
    if a is not None:
        cls, txt = _pct(a)
        sig = spy.get("alpha_significant")
        rows.append(_kv("Alpha, per year",
                        txt + ("" if sig else ' <span class="muted" style="font-weight:400">(noise)</span>'),
                        cls if sig else "",
                        title="Return beyond what market exposure explains; "
                              "'noise' = too small for one year of data to tell from luck"))
    rows.append(_kv("Sharpe · Sortino",
                    f'{_num(spy.get("sharpe"), 2)} · {_num(spy.get("sortino"), 2)}'))
    _, dtxt = _pct(spy.get("max_drawdown"))
    rows.append(_kv("Max drawdown", dtxt, "down" if spy.get("max_drawdown") else ""))
    up, dn = spy.get("up_capture"), spy.get("down_capture")
    if up is not None and dn is not None:
        rows.append(_kv("Up · down capture", f"{up*100:.0f}% · {dn*100:.0f}%"))
    return (f'<div class="det-sec risk-sec"><div class="det-h">Risk vs the market '
            f'<span class="muted" style="font-weight:400">(1 year)</span></div>'
            f'{"".join(rows)}</div>')


def _card_detail(r):
    """Modal quick-look: chart + compact summaries + news, with a button to the
    full, roomier analysis page. The dense valuation/trade/regime detail lives on
    /analysis/<ticker> to keep the modal readable."""
    tk = html.escape(r.ticker)
    btn = (f'<div class="analysis-btn cta-row">'
           f'<button type="button" class="cta-2" onclick="event.stopPropagation();'
           f"openTab('/compare?t={tk}')\">Compare</button>"
           f'<button type="button" class="cta-1" onclick="event.stopPropagation();'
           f"openTab('/analysis/{tk}')\">Analysis</button></div>")
    return (f'<div class="card-detail" onclick="event.stopPropagation()">'
            f'{_chart_html(r)}{_valuation_summary(r)}{_risk_summary(r)}{_regime_summary(r)}'
            f'{_volume_summary(r)}{btn}'
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
        inner = f'<span class="erflag {cls}">{txt}</span>'
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
        f'<span class="card-price">${r.price:,.2f} <span class="chg {dcls}">{dtxt}</span></span></div>'
        f'<div class="nm">{html.escape((r.name or "")[:34])}</div>'
        f'{_ext_html(r)}'
        f'<div class="trendline {tcls}">{html.escape(trend_word)} '
        f'<span class="tscore" title="Trend score">{r.trend_score:+.0f}</span></div>'
        f'{_factor_chip(r)}'
        f'{_earnings_badge(r)}'
        f'<div class="card-spark">{_spark(r.sparkline, w=222, h=34)}</div>'
        f'<div style="margin:4px 0">{_indicator_chips(r)}</div>'
        + mrow("1M", r.changes.get("1m")) + mrow("1Y", r.changes.get("1y"))
        + f'<div class="card-row"><span>RSI</span><b>{_num(r.rsi,0)}</b></div>'
        f'<div class="card-row"><span>P/E</span><b>{_num(r.pe,1)}</b></div>'
        f'<div class="card-row"><span>Market cap</span><b>{_mktcap(r.market_cap)}</b></div>'
        f'<div class="card-row" title="{_BETA_TIP}"><span>Beta</span><b>{_num(r.beta, 2)}</b></div>'
        f'<div class="links" onclick="event.stopPropagation()" style="margin-top:8px">{links}</div>'
        f'<div class="details-cta"><span>Details</span>{icon("chevron-right", 14)}</div>'
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
    """Filter chips as labeled rows (signal / conditions / categories / sections)
    so ~35 filters scan as four short lists instead of one wall."""
    signals, flags, cats, secs = set(), set(), set(), set()
    for r in rows:
        signals.add(r.signal)
        flags |= set(r.flags)
        cats |= set(r.categories)
        secs |= set(r.sections)
    secs -= _HIDDEN_SECTION_CHIPS

    def chip(group, match, label, dot=""):
        d = f'<span class="dot {dot}"></span>' if dot else ""
        return (f'<button class="chip-f" data-group="{group}" data-match="{match}" '
                f'onclick="toggleChip(this)">{d}{label}</button>')

    def grp(label, chips):
        return (f'<div class="cgroup"><span class="cglab">{label}</span>{"".join(chips)}</div>'
                if chips else "")

    sig = [chip("signal", s, s.capitalize(), _SIG_CLASS.get(s, "hold"))
           for s in ("BUY", "SELL", "SHORT", "HOLD") if s in signals]
    cond = [chip("condition", fl, _FLAG_LABEL[fl])
            for fl in ("oversold", "overbought", "surge", "crash", "squeeze", "vol_spike",
                       "near_52w_high", "near_52w_low", "earnings_soon") if fl in flags]
    cat = [chip("category", c, _CAT_LABEL[c])
           for c in ("tech", "leveraged", "etf", "dividend") if c in cats]
    sec = [chip("section", x, _section_label(x)) for x in sorted(secs, key=_section_label)]
    return (grp("Signal", sig) + grp("Conditions", cond) + grp("Categories", cat)
            + grp("Sections", sec))


def _alert_tone(kind: str) -> str:
    """Semantic dot for an alert kind (replaces the per-alert emoji)."""
    if kind in ("52w_high", "surge", "signal_buy"):
        return "a-up"
    if kind in ("52w_low", "crash", "signal_short", "signal_sell"):
        return "a-down"
    if kind in ("vol_spike", "squeeze"):
        return "a-warn"
    return "a-info"


def _banner(alerts):
    """A single-line marquee that slides through every alert (no truncation)."""
    if not alerts:
        return "", ""
    items = "".join(f'<span class="a"><span class="dot {_alert_tone(a.kind)}"></span>'
                    f'{html.escape(a.message)}</span>' for a in alerts)
    # scale the loop duration with the amount of text so it reads at a steady pace
    dur = max(20, min(150, len(alerts) * 3))
    sig = f"{len(alerts)}:" + ",".join(a.kind for a in alerts[:5])
    track = (f'<div class="banner-track" style="animation-duration:{dur}s">'
             f'{items}{items}</div>')
    banner = (f'<div class="banner" id="banner" data-sig="{html.escape(sig)}">'
              f'<div class="banner-vp">{track}</div>'
              f'<button class="x icon-btn" onclick="dismissBanner()" title="Dismiss" '
              f'aria-label="Dismiss alerts">{icon("x", 15)}</button></div>')
    return banner, sig


def _sector_html(sectors):
    present = [(n, t, r) for (n, t, r) in (sectors or []) if r is not None]
    if not present:
        return '<section class="panel"><div class="panel-h">Sector performance<span class="ph-tag">1 month</span></div>' \
               '<div class="muted" style="font-size:13px">unavailable</div></section>'
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
    return ('<section class="panel"><div class="panel-h">Sector performance<span class="ph-tag">1 month</span></div>'
            '<div class="panel-body">' + "".join(rows) + '</div></section>')


_MKT_GROUP_LABEL = {"index": "Indices", "commodity": "Commodities", "crypto": "Crypto"}


def _points(last, chg):
    """The day's move in points/dollars, backed out of the last price and the
    % change (prev = last / (1 + chg))."""
    if last is None or chg is None or chg <= -1:
        return "-"
    pts = last - last / (1.0 + chg)
    return f"{pts:+,.2f}" if abs(pts) < 100 else f"{pts:+,.0f}"


def _markets_html(markets):
    quotes = [q for q in (markets or []) if q.last is not None]
    if not quotes:
        return '<section class="panel"><div class="panel-h">Markets</div>' \
               '<div class="muted" style="font-size:13px">unavailable</div></section>'
    rows = []
    last_group = None
    for q in quotes:
        if q.group != last_group:
            rows.append(f'<div class="mkgroup">{_MKT_GROUP_LABEL.get(q.group, q.group)}</div>')
            last_group = q.group
        chg = q.change
        ccls = "up" if (chg or 0) >= 0 else "down"
        chg_txt = f"{chg*100:+.2f}%" if chg is not None else "-"
        px = f"${q.last:,.2f}" if q.last < 100 else f"${q.last:,.0f}"
        rows.append(
            f'<div class="mkrow"><span class="mkname">{html.escape(q.name)}</span>'
            f'<span class="mkpx">{px}</span>'
            f'<span class="mkpts {ccls}">{_points(q.last, chg)}</span>'
            f'<span class="mkchg {ccls}">{chg_txt}</span></div>')
    return ('<section class="panel"><div class="panel-h">Markets</div>'
            '<div class="panel-body">' + "".join(rows) + '</div></section>')


def _macro_html(macro):
    """Macro-trends panel: rate/vol gauges, next Fed decision, event headlines."""
    macro = macro or {}
    body = ""
    inds = [i for i in macro.get("indicators", []) if i.get("display") not in (None, "-")]
    if inds:
        rows = []
        for i in inds:
            chg = i.get("change")
            ccls = "muted" if chg is None else ("up" if chg >= 0 else "down")
            chg_txt = f"{chg*100:+.2f}%" if chg is not None else "-"
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
                 f'<span class="{fcls}" style="font-size:13px">{html.escape(str(fg.get("rating","")))}</span>'
                 '</span></div>')

    fomc = macro.get("fomc")
    if fomc:
        iso, days = fomc
        when = "today" if days == 0 else ("tomorrow" if days == 1 else f"in {days}d")
        body += ('<div class="mkgroup">Fed</div>'
                 f'<div class="macro-fomc">Fed decision (FOMC) <b>{when}</b> '
                 f'<span class="muted">{html.escape(iso)}</span></div>')

    events = macro.get("events", [])
    if events:
        ev = []
        for e in events:
            inner = html.escape(e.get("title", ""))
            url = e.get("url") or ""
            ev.append(f'<a class="macro-ev" href="{html.escape(url)}" target="_blank" rel="noopener">{inner}</a>'
                      if url else f'<div class="macro-ev">{inner}</div>')
        body += '<div class="mkgroup">Market events</div>' + "".join(ev)

    if not body:
        body = '<div class="muted" style="font-size:13px">no macro data</div>'
    return ('<section class="panel"><div class="panel-h">Macro</div>'
            '<div class="panel-body">' + body + '</div></section>')


_SERVED_JS = r"""
let _addResults=[], _addTimer=null, _addPoll=null;
function addMsg(t,cls){ const m=document.getElementById('addmsg'); if(m){ m.textContent=t||''; m.className=(cls||'muted'); } }
// The add box takes one ticker or a list: "NET, OKTA CHKP" (commas/spaces/newlines).
function _addTokens(s){ return (s||'').toUpperCase().split(/[\s,;]+/).filter(Boolean); }
function _lastTok(s){ const p=(s||'').split(/[\s,;]+/); return (p[p.length-1]||'').trim(); }
function addSearch(){
  clearTimeout(_addTimer);
  const q=_lastTok(document.getElementById('addq').value);   // autocomplete the one being typed
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
function pickAdd(i){
  const x=_addResults[i]; if(!x) return;
  const inp=document.getElementById('addq'), toks=_addTokens(inp.value);
  if(toks.length<=1){ inp.value=x.symbol; doAdd(x.symbol); return; }   // single: add right away
  toks[toks.length-1]=x.symbol;                                          // list: complete the last one
  inp.value=toks.join(', ')+', ';
  document.getElementById('addsug').style.display='none'; inp.focus();
}
function addTicker(){ const t=_addTokens(document.getElementById('addq').value); if(t.length) doAddMany(t); }
function addKey(e){ if(e.key==='Enter'){ e.preventDefault(); addTicker(); } if(e.key==='Escape'){ document.getElementById('addsug').style.display='none'; } }
function doAdd(sym){ doAddMany([sym]); }
// Adding runs as a background job on the server: this returns at once and polls
// for progress, so the board, cards and analysis pages stay usable meanwhile.
function doAddMany(list){
  document.getElementById('addsug').style.display='none';
  clearTimeout(_addPoll);
  addMsg('adding '+(list.length===1?list[0]:list.length+' tickers')+'…','muted');
  fetch('/api/watchlist/add_bulk',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({tickers:list})})
    .then(r=>r.json()).then(d=>{
      if(!d.ok){ addMsg(d.error||'could not add','bad'); return; }
      document.getElementById('addq').value='';
      if(!(d.queued||[]).length){ _addResult({added:[],failed:[],skipped:d.skipped||[]}); return; }
      _pollAdd(d.job);
    }).catch(()=>addMsg('network error','bad'));
}
function _pollAdd(id){
  fetch('/api/watchlist/add_status/'+encodeURIComponent(id),{cache:'no-store'}).then(r=>r.json()).then(j=>{
    if(!j.ok){ addMsg(j.error||'add status unavailable','bad'); return; }
    if(j.state!=='done'){
      addMsg(j.state==='building' ? 'updating the board…' : 'adding '+j.done+'/'+j.total+'…','muted');
      _addPoll=setTimeout(()=>_pollAdd(id),900); return;
    }
    _addResult(j);
    if((j.added||[]).length) refreshWhenFree();
  }).catch(()=>{ _addPoll=setTimeout(()=>_pollAdd(id),2000); });
}
function _addResult(j){
  const m=document.getElementById('addmsg'); if(!m) return;
  const e=_esc, parts=[];
  if((j.added||[]).length) parts.push('<span class="ok">added '+e(j.added.join(', '))+'</span>');
  (j.failed||[]).filter(f=>!f.retry).forEach(f=>{
    let s='<span class="bad">'+e(f.ticker)+': not found</span>';
    if(f.suggest&&f.suggest.symbol) s+=' <a href="#" class="addsg" onclick="doAdd(\''+e(f.suggest.symbol)+
      '\');return false;">did you mean '+e(f.suggest.symbol)+(f.suggest.name?' ('+e(f.suggest.name)+')':'')+'?</a>';
    parts.push(s);
  });
  // Real tickers that couldn't be checked because the data providers are
  // rate-limited: say so (not "not found") and offer a one-click retry.
  const retry=(j.failed||[]).filter(f=>f.retry).map(f=>f.ticker);
  if(retry.length) parts.push('<span class="bad">couldn&#39;t verify '+e(retry.join(', '))+
    ' right now (data providers rate-limited)</span> <a href="#" class="addsg" onclick="doAddMany([\''+
    retry.join('\',\'')+'\']);return false;">retry</a>');
  const sk=j.skipped||[];
  if(sk.length) parts.push('<span class="muted">skipped '+e(sk.map(x=>x.ticker+' ('+x.reason+')').join(', '))+'</span>');
  m.className=''; m.innerHTML=parts.join(' · ')||'<span class="muted">nothing to add</span>';
}
// Swap the new board in once the user isn't mid-interaction (card modal open).
function refreshWhenFree(){
  if(_refreshing || document.getElementById('modal').classList.contains('show')){ setTimeout(refreshWhenFree,1500); return; }
  refreshData();
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
    const nc=doc.querySelector('.chips'), oc=document.querySelector('.chips');
    if(nc&&oc&&oc.innerHTML!==nc.innerHTML){ oc.innerHTML=nc.innerHTML;   // new sections -> new chips
      if(typeof active!=='undefined') oc.querySelectorAll('.chip-f[data-group]').forEach(b=>{
        const set=active[b.dataset.group]; if(set&&set.has(b.dataset.match)) b.classList.add('on'); }); }
    const nb=doc.querySelector('.status'), ob=document.querySelector('.status');
    if(nb&&ob) ob.className=nb.className, ob.textContent=nb.textContent;
    const nu=doc.getElementById('updated'), ou=document.getElementById('updated');
    if(nu&&ou){ ou.dataset.ts=nu.dataset.ts;
      if(nu.dataset.refresh) ou.dataset.refresh=nu.dataset.refresh;   // adopt new cadence
      fmtUpdated(); }
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
  el.innerHTML=_newsSec('<div class="muted" style="font-size:13px">loading…</div>');
  fetch('/api/news/'+encodeURIComponent(t)+(nm?'?name='+encodeURIComponent(nm):'')).then(r=>r.json()).then(d=>{
    const items=(d.items||[]);   // already ranked most-recent first by the server
    if(!items.length){ el.innerHTML=_newsSec('<div class="muted" style="font-size:13px">No recent news.</div>'); return; }
    const rows=items.map(n=>{
      const meta=[n.publisher, n.age].filter(Boolean).join(' · ');
      const inner='<div class="nw-t">'+_esc(n.title)+'</div>'+(meta?'<div class="nw-m">'+_esc(meta)+'</div>':'');
      return n.url ? '<a class="nw" href="'+_esc(n.url)+'" target="_blank" rel="noopener">'+inner+'</a>'
                   : '<div class="nw">'+inner+'</div>';
    }).join('');
    el.innerHTML=_newsSec(rows);
  }).catch(()=>{ el.innerHTML=_newsSec('<div class="muted" style="font-size:13px">News unavailable right now.</div>'); });
}
// ---- analysis tool pop-ups ----
function closeTool(e){ if(e&&e.target&&e.target.id!=='toolmodal'&&e.type==='click') return;
  document.getElementById('toolmodal').classList.remove('show'); }
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeTool(); });
function _tkv(id){ const el=document.getElementById(id); return el?(el.value||'').trim().toUpperCase():''; }
function toolBusy(m){ document.getElementById('tool-out').innerHTML='<div class="muted">'+(m||'Running…')+'</div>'; }
function toolErr(m){ document.getElementById('tool-out').innerHTML='<div class="t-err">'+m+'</div>'; }
function _pc(x){ return x>=0?'up':'down'; }
function _ps(x){ return x==null?'-':(x>=0?'+':'')+(x*100).toFixed(1)+'%'; }
function _usd(x){ return x==null?'-':'$'+Number(x).toLocaleString(undefined,{maximumFractionDigits:2}); }
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
    if(d.kind==='basket') h+='<div class="t-note">Basket as of '+(d.as_of||'-')+'. Indices rebalance quarterly - confirm current weights with the issuer.'+(d.verify?' (unverified snapshot)':'')+'</div>';
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
        '<input id="addq" placeholder="Add tickers (e.g. NVDA, NET OKTA or &quot;oracle&quot;)…" '
        'autocomplete="off" oninput="addSearch()" onkeydown="addKey(event)">'
        '<div id="addsug" class="addsug"></div></div>'
        f'<button class="tbtn add" onclick="addTicker()">{icon("plus", 15)}Add</button>')
    _holdings_btn = "" if public else '<button class="tool-b" onclick="openTab(\'/holdings\')">Holdings</button>'
    tools_html = (
        '<span class="toolsbar">'
        '<button class="tool-b" onclick="openTool(\'evaluate\')">Evaluate</button>'
        '<button class="tool-b" onclick="openTool(\'lookthrough\')">Look-through</button>'
        '<button class="tool-b" onclick="openTool(\'montecarlo\')">Monte Carlo</button>'
        '<button class="tool-b" onclick="openTab(\'/compare\')">Compare</button>'
        '<button class="tool-b" onclick="openTab(\'/indicators\')">Indicators</button>'
        '<button class="tool-b" onclick="openTab(\'/interpret\')">Interpret</button>'
        + _holdings_btn + '</span>'
    ) if served else ""
    add_html = (
        '<div class="addbar">' + _add_box + '<span id="addmsg" class="muted"></span></div>'
    ) if served else ""
    bmc_html = (
        f'<a class="bmc" href="{html.escape(bmc_url)}" target="_blank" rel="noopener">'
        'Buy me a coffee</a>') if bmc_url else ""
    tool_modal = (
        '<div id="toolmodal" class="modal" onclick="closeTool(event)">'
        '<div class="modal-card" onclick="event.stopPropagation()">'
        f'<button class="modal-x" onclick="closeTool()" aria-label="Close">{icon("x", 17)}</button>'
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
<title>{html.escape(title)}</title>{_THEME_BOOT}<style>{_CSS}{_CSS_EXTRA}</style></head>
<body><div class="wrap">
<header class="top">
  <div class="top-l"><h1>{html.escape(title)}</h1>{badge}
    <span class="sub">Updated <span id="updated" data-ts="{int(updated_ts) if updated_ts else ''}" data-refresh="{int(refresh_seconds)}">{html.escape(updated)}</span></span></div>
  <div class="top-r">{bmc_html}<button class="icon-btn" onclick="toggleTheme()" title="Switch light / dark" aria-label="Switch light or dark theme">{icon("theme", 16)}</button></div>
</header>
{banner}
<div class="bar">
  <div class="seg" role="tablist" aria-label="View">
    <button data-view="table" class="on" onclick="setView('table')">Table</button>
    <button data-view="card" onclick="setView('card')">Cards</button>
    <button data-view="heatmap" onclick="setView('heatmap')">Heatmap</button>
  </div>
  <label class="search">{icon("search", 15)}<input id="q" placeholder="Filter tickers" aria-label="Filter tickers" oninput="applyFilter()"></label>
  <span class="count" id="count">{ok} of {len(rows)} tickers</span>
  {tools_html}
</div>
{add_html}
<div class="panels">{sector_html}{markets_html}{macro_html}</div>
<div class="chips">{chips}<div class="cgroup"><button class="chip-f clear" onclick="clearChips()">Clear filters</button></div></div>
<div id="view-table" class="view active"><div class="tablewrap"><table class="wl" id="wl">
<thead><tr>{heads}</tr></thead><tbody>{table}</tbody></table></div></div>
<div id="view-card" class="view"><div class="cards">{cards}</div></div>
<div id="view-heatmap" class="view">{tiles}</div>
<div class="empty" id="empty"><b>No tickers match these filters</b>
  Remove a filter or clear the search to see the board again.
  <div style="margin-top:12px"><button class="tbtn" onclick="clearChips()">Clear filters</button></div></div>

<div id="modal" class="modal" onclick="closeModal(event)">
  <div class="modal-card" onclick="event.stopPropagation()">
    <button class="modal-x" onclick="closeModal()" aria-label="Close">{icon("x", 17)}</button>
    <div id="modal-body"></div>
  </div>
</div>
{tool_modal}

<p class="site-note">
Signals are rule-based indicator states, not investment advice. Free data may be
delayed. All values computed by tested Python.
<a class="site-help" href="/interpret" onclick="openTab('/interpret');return false">How to read this</a></p>
<div class="site-foot">2026 SMI Investments. All rights reserved.</div>
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
  const em=document.getElementById('empty'); if(em) em.classList.toggle('show', tot>0 && n===0);
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
  // Quick-look, top to bottom: ticker and price, the chart across the full width,
  // every metric in a grid below it, recent news, then Compare / Analysis.
  const body=document.getElementById('modal-body');
  const src=document.createElement('div'); src.innerHTML=card.innerHTML;
  const detail=src.querySelector('.card-detail');
  const pick=sel=>detail?detail.querySelector(sel):null;
  const chart=pick('.chart-sec'), news=pick('.cardnews'), cta=pick('.analysis-btn'), risk=pick('.risk-sec'),
        vol=pick('.vol-sec');
  if(detail) detail.remove();
  const head=document.createElement('div'); head.className='mx-head';
  ['.card-top','.nm','.exthrs'].forEach(sel=>{{ const n=src.querySelector(sel); if(n) head.appendChild(n); }});
  const sum=document.createElement('div'); sum.className='mx-sum';     // trend, factors, stats, links
  const oh=document.createElement('div'); oh.className='det-h'; oh.textContent='Overview';
  sum.appendChild(oh);
  while(src.firstChild) sum.appendChild(src.firstChild);
  const more=document.createElement('div'); more.className='mx-more';  // valuation, regime
  if(detail) Array.from(detail.children).forEach(c=>{{
    if(c!==chart && c!==news && c!==cta && c!==risk && c!==vol) more.appendChild(c); }});
  const grid=document.createElement('div'); grid.className='mx-grid';
  grid.appendChild(sum);
  if(risk||vol){{ const r=document.createElement('div');               // risk, then volume
    if(risk) r.appendChild(risk); if(vol) r.appendChild(vol); grid.appendChild(r); }}
  if(more.children.length) grid.appendChild(more);
  const top=document.createElement('div'); top.className='mx-chart';
  if(chart) top.appendChild(chart);
  const wrap=document.createElement('div'); wrap.className='card-item mx';
  wrap.append(head, top, grid);
  if(news){{ news.classList.add('mx-news'); wrap.appendChild(news); }}
  if(cta) wrap.appendChild(cta);
  body.innerHTML=''; body.appendChild(wrap);
  document.getElementById('modal').classList.add('show');
  fitChart(body);
  drawCharts(body);
  if(typeof loadNews==='function') loadNews(body);
}}
function fitChart(body){{
  // A taller chart now that it spans the whole quick-look (phones keep the default).
  const el=body.querySelector('.mx-chart .pricechart');
  if(el) el._h=window.matchMedia('(max-width:820px)').matches?0:300;
}}
const TF_DAYS={{'5d':8,'1mo':31,'3mo':92,'6mo':183,'1y':366,'2y':731,'5y':1827,'max':1e9}};
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
  const W=Math.max(280, Math.round(el.clientWidth||340)), H=el._h||176;
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
  const step=niceStep(hi-lo,Math.max(4,Math.round(H/55))); let grid='', ylab='';
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
const SERVED = {"true" if served else "false"};
// Adaptive polling: re-read the interval from #updated[data-refresh] each cycle,
// so the instant cold-start board (a short interval) auto-upgrades to live prices
// within a cycle, then settles to the live cadence (15m open / 30m extended / 1h
// closed). No manual reload needed; catches session changes too.
function _pollMs(){{ const u=document.getElementById('updated');
  const s=u&&u.dataset.refresh?parseInt(u.dataset.refresh,10):0;
  return (s>0?Math.max(20000,Math.min(s*1000,3600000)):0); }}
function _schedulePoll(){{
  if(!SERVED || typeof refreshData!=='function') return;
  const ms=_pollMs(); if(!ms) return;
  setTimeout(function(){{ refreshData(); _schedulePoll(); }}, ms);
}}
(function init(){{
  const t=localStorage.getItem('wl_theme'); if(t) document.documentElement.setAttribute('data-theme', t);
  const b=document.getElementById('banner');
  if(b && localStorage.getItem('wl_banner')===b.dataset.sig) b.style.display='none';
  setView(view);
  fmtUpdated();
  wireTableScroll();
  _schedulePoll();
}})();
{js_served}
</script>
</body></html>"""
