"""Render the watchlist as a self-contained dashboard: table / card / heatmap
views, faceted filter chips, sortable table, live search, and a theme toggle.

Reuses the dashboard theme CSS. Sparklines and heatmap tiles are inline (no
libraries). Every ticker element carries data-* attributes (signal, flags,
categories, sections) so one filter engine works across all three views.
"""

from __future__ import annotations

import html
import os

from ..dashboard.render import _CSS
from ..trade import atr_trade_setup, position_size, suggest_options

_SIG_CLASS = {"BUY": "buy", "SELL": "sell", "SHORT": "short", "HOLD": "hold"}
_SIG_EMOJI = {"BUY": "🟢", "SELL": "🟠", "SHORT": "🔴", "HOLD": "⏸️"}
_FLAG_LABEL = {
    "oversold": "Oversold", "overbought": "Overbought", "surge": "Surge",
    "crash": "Crash", "squeeze": "Squeeze", "vol_spike": "Vol spike",
    "near_52w_high": "52w High", "near_52w_low": "52w Low",
}
_CAT_LABEL = {"tech": "Tech", "leveraged": "Leveraged", "etf": "ETF", "dividend": "Dividend"}
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
.bar input{flex:0 0 220px;font-size:14px;padding:8px 11px;border-radius:9px;
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
.tablewrap{overflow-x:auto;border:1px solid var(--border);border-radius:12px}
table.wl{border-collapse:collapse;width:100%;font-size:12.5px;min-width:900px}
table.wl th,table.wl td{padding:7px 10px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--border)}
table.wl th{position:sticky;top:0;background:var(--surface-2);color:var(--muted);font-weight:650;
  text-transform:uppercase;letter-spacing:.03em;font-size:11px;cursor:pointer;user-select:none}
table.wl th:first-child,table.wl td:first-child{text-align:left;position:sticky;left:0;background:var(--surface)}
table.wl tr.item:hover td{background:var(--surface-2)}
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
/* cards */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.card-item{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 14px}
.card-top{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.card-price{font-size:20px;font-weight:700;font-variant-numeric:tabular-nums}
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
.modal-x{position:absolute;top:10px;right:12px;border:none;background:none;color:var(--muted);
  font-size:19px;cursor:pointer;line-height:1}
#modal-body .card-detail{display:block}
#modal-body .details-cta{display:none}
#modal-body .card-item{cursor:default;border:none;padding:0}
/* sector performance */
details.sectors{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:10px 14px;margin-bottom:14px}
details.sectors summary{cursor:pointer;font-size:12.5px;font-weight:650;color:var(--muted);
  text-transform:uppercase;letter-spacing:.04em;list-style:none}
details.sectors summary::-webkit-details-marker{display:none}
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
/* heatmap */
.heat{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px}
.tile-item{border:1px solid var(--border);border-radius:10px;padding:10px 12px;text-align:center}
.tile-item .t{font-weight:700;font-size:13px}
.tile-item .c{font-size:15px;font-weight:700;font-variant-numeric:tabular-nums;margin-top:2px}
.tile-item .s{font-size:10px;color:var(--muted)}
.view{display:none}.view.active{display:block}
.banner{display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;padding:9px 14px;
  margin:10px 0;background:var(--surface-2);border:1px solid var(--border);border-radius:10px;font-size:12.5px}
.banner .a{white-space:nowrap}
.banner .x{margin-left:auto;cursor:pointer;color:var(--muted);border:none;background:none;font-size:15px}
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
_HEADERS = ["Ticker", "Price", "Day", "5D", "1M", "1Y", "30d", "Signal",
            "Trend", "RSI", "Indicators", "Conf", "P/E", "Mkt Cap"]


def _row_html(r):
    if r.error or r.price is None:
        return (f'<tr class="item" {_data_attrs(r)}><td class="tk">{html.escape(r.ticker)}</td>'
                f'<td colspan="13" class="muted">no data</td></tr>')

    def cell(x):
        cls, txt = _pct(x)
        return f'<td class="{cls}" data-sort="{x if x is not None else -999}">{txt}</td>'

    sig_cls = _SIG_CLASS.get(r.signal, "hold")
    arrow_cls = "up" if r.trend_score > 1 else ("down" if r.trend_score < -1 else "flat")
    rsi_cls = "up" if (r.rsi or 50) >= 70 else ("down" if (r.rsi or 50) <= 30 else "")
    conf = (f'<span class="conf-{r.confidence}">{r.confidence}</span>'
            if r.confidence else '<span class="muted">—</span>')
    return (
        f'<tr class="item" {_data_attrs(r)}>'
        f'<td><span class="tk">{html.escape(r.ticker)}</span> '
        f'<span class="nm">{html.escape((r.name or "")[:22])}</span></td>'
        f'<td data-sort="{r.price}">${r.price:,.2f}</td>'
        + cell(r.changes.get("1d")) + cell(r.changes.get("5d")) + cell(r.changes.get("1m"))
        + cell(r.changes.get("1y"))
        + f'<td>{_spark(r.sparkline)}</td>'
        f'<td data-sort="{r.trend_score}"><span class="badge {sig_cls}">{r.signal}</span></td>'
        f'<td class="arrow {arrow_cls}" data-sort="{r.trend_score}">{r.trend_arrow}</td>'
        f'<td class="{rsi_cls}" data-sort="{r.rsi if r.rsi is not None else -1}">{_num(r.rsi,0)}</td>'
        f'<td style="text-align:left">{_indicator_chips(r)}</td>'
        f'<td>{conf}</td>'
        f'<td data-sort="{r.pe if r.pe is not None else -1}">{_num(r.pe,1)}</td>'
        f'<td data-sort="{r.market_cap or 0}">{_mktcap(r.market_cap)}</td></tr>'
    )


def _trade_setup_html(r):
    if r.signal not in ("BUY", "SHORT") or not r.atr or not r.price:
        return ""
    direction = "LONG" if r.signal == "BUY" else "SHORT"
    s = atr_trade_setup(r.price, r.atr, direction)
    if not s:
        return ""
    size_line = ""
    acct = os.environ.get("ACCOUNT_SIZE")
    if acct:
        try:
            ps = position_size(float(acct), s.entry, s.stop)
            if ps:
                cap = " (cap)" if ps.capped else ""
                size_line = (f'<div class="ts-row"><span>Size</span><b>{ps.shares:.0f} sh · '
                             f'${ps.dollars:,.0f} ({ps.pct_of_account:.0%}){cap}</b></div>')
        except ValueError:
            pass
    cls = "buy" if r.signal == "BUY" else "short"
    return (
        f'<div class="tsetup {cls}"><div class="ts-h">Trade setup · {direction} '
        f'({s.rr_ratio:.0f}:1 R:R)</div>'
        f'<div class="ts-row"><span>Entry</span><b>${s.entry:,.2f}</b></div>'
        f'<div class="ts-row"><span>Stop</span><b class="down">${s.stop:,.2f} (-{s.risk_pct*100:.1f}%)</b></div>'
        f'<div class="ts-row"><span>Target</span><b class="up">${s.target:,.2f} (+{s.reward_pct*100:.1f}%)</b></div>'
        f'{size_line}</div>')


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
    rows = [f'<div class="det-row"><span>Valuation signal</span><b>{html.escape(v.get("signal") or "n/a")}</b></div>']
    base, bear, bull = v.get("base"), v.get("bear"), v.get("bull")
    if base is not None and bear is not None and bull is not None:
        rows.append(f'<div class="det-row"><span>Fair value bear/base/bull</span>'
                    f'<b>${bear:,.0f} / ${base:,.0f} / ${bull:,.0f}</b></div>')
        mos = v.get("margin_of_safety")
        if mos is not None:
            rows.append(f'<div class="det-row"><span>Price vs fair value</span>'
                        f'<b class="{"up" if mos>=0 else "down"}">{mos*100:+.0f}%</b></div>')
    ig = v.get("implied_market_growth")
    if ig is not None:
        rows.append(f'<div class="det-row"><span>Reverse-DCF implied growth</span><b>{ig*100:.0f}%</b></div>')
    reco = c.get("reco")
    if reco and reco != "n/a":
        tvp = c.get("target_vs_price")
        thtml = ""
        if tvp is not None:
            thtml = f' · target <span class="{"up" if tvp>=0 else "down"}">{tvp*100:+.0f}%</span>'
        rows.append(f'<div class="det-row"><span>Analyst consensus</span><b>{html.escape(reco)}{thtml}</b></div>')
    note = v.get("note")
    note_html = f'<div class="det-note">{html.escape(note)}</div>' if note else ""
    return f'<div class="det-sec"><div class="det-h">Stock analyzer — valuation</div>{"".join(rows)}{note_html}</div>'


def _card_detail(r):
    ts = _trade_setup_html(r)
    ts_sec = f'<div class="det-sec">{ts}</div>' if ts else ""
    return (f'<div class="card-detail" onclick="event.stopPropagation()">'
            f'{ts_sec}{_options_html(r)}{_valuation_html(r)}</div>')


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
        f'<div class="trendline {tcls}">{html.escape(trend_word)} <span class="muted">· trend {r.trend_score:+.0f}</span></div>'
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
               "near_52w_high", "near_52w_low"):
        if fl in flags:
            out.append(chip("condition", fl, _FLAG_LABEL[fl]))
    for cat in ("tech", "leveraged", "etf", "dividend"):
        if cat in cats:
            out.append(chip("category", cat, _CAT_LABEL[cat]))
    for sec in sorted(secs):
        out.append(chip("section", sec, sec.title()))
    return "".join(out)


def _banner(alerts, cap=14):
    if not alerts:
        return "", ""
    shown = alerts[:cap]
    extra = len(alerts) - len(shown)
    items = "".join(f'<span class="a">{html.escape(a.emoji)} {html.escape(a.message)}</span>'
                    for a in shown)
    if extra > 0:
        items += f'<span class="a muted">+{extra} more</span>'
    sig = f"{len(alerts)}:" + ",".join(a.kind for a in shown[:5])
    banner = (f'<div class="banner" id="banner" data-sig="{html.escape(sig)}">{items}'
              f'<button class="x" onclick="dismissBanner()" title="Dismiss">✕</button></div>')
    return banner, sig


def _sector_html(sectors):
    present = [(n, t, r) for (n, t, r) in (sectors or []) if r is not None]
    if not present:
        return ""
    mx = max(abs(r) for _, _, r in present) or 0.01
    rows = []
    for name, tk, r in sorted(present, key=lambda x: x[2], reverse=True):
        w = min(100.0, abs(r) / mx * 100.0)
        cls = "up" if r >= 0 else "down"
        neg = f'<div class="fill-down" style="width:{w:.0f}%"></div>' if r < 0 else ""
        pos = f'<div class="fill-up" style="width:{w:.0f}%"></div>' if r >= 0 else ""
        rows.append(
            f'<div class="secrow"><div class="secname">{html.escape(name)}</div>'
            f'<div class="secbar"><div class="sechalf neg">{neg}</div>'
            f'<div class="secaxis"></div><div class="sechalf pos">{pos}</div></div>'
            f'<div class="secval {cls}">{r*100:+.1f}%</div></div>')
    return ('<details class="sectors"><summary>Sector performance (1m) ▾</summary>'
            '<div style="margin-top:8px">' + "".join(rows) + '</div></details>')


def render_watchlist(rows, title="Watchlist", updated="", status_badge="", status_label="",
                     alerts=None, sectors=None, refresh_seconds=1800):
    banner, _sig = _banner(alerts or [])
    sector_html = _sector_html(sectors)
    table = "".join(_row_html(r) for r in rows)
    cards = "".join(_card_html(r) for r in rows)
    tiles = "".join(_tile_html(r) for r in rows)
    heads = "".join(f'<th onclick="sortBy({i})">{h}</th>' for i, h in enumerate(_HEADERS))
    chips = _chip_bar(rows)
    ok = sum(1 for r in rows if r.price is not None)
    badge = (f'<span class="status {html.escape(status_label)}">{html.escape(status_badge)}</span>'
             if status_badge else "")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{int(refresh_seconds)}">
<title>{html.escape(title)}</title><style>{_CSS}{_CSS_EXTRA}</style></head>
<body><div class="wrap">
<header><h1>{html.escape(title)}</h1>{badge}
  <span class="sub" style="margin:0">Updated {html.escape(updated)}</span></header>
{banner}
<div class="bar">
  <div class="seg">
    <button data-view="table" class="on" onclick="setView('table')">Table</button>
    <button data-view="card" onclick="setView('card')">Cards</button>
    <button data-view="heatmap" onclick="setView('heatmap')">Heatmap</button>
  </div>
  <input id="q" placeholder="Filter tickers…" oninput="applyFilter()">
  <span class="count" id="count">{ok} of {len(rows)} tickers</span>
  <button class="tbtn" onclick="toggleTheme()" style="margin-left:auto">◐ Theme</button>
</div>
<div class="chips">{chips}<button class="chip-f" onclick="clearChips()">Clear</button></div>
{sector_html}
<div id="view-table" class="view active"><div class="tablewrap"><table class="wl" id="wl">
<thead><tr>{heads}</tr></thead><tbody>{table}</tbody></table></div></div>
<div id="view-card" class="view"><div class="cards">{cards}</div></div>
<div id="view-heatmap" class="view"><div class="heat">{tiles}</div></div>

<div id="modal" class="modal" onclick="closeModal(event)">
  <div class="modal-card" onclick="event.stopPropagation()">
    <button class="modal-x" onclick="closeModal()">✕</button>
    <div id="modal-body"></div>
  </div>
</div>

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
  document.getElementById('modal-body').innerHTML =
    '<div class="card-item">'+card.innerHTML+'</div>';
  document.getElementById('modal').classList.add('show');
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
(function init(){{
  const t=localStorage.getItem('wl_theme'); if(t) document.documentElement.setAttribute('data-theme', t);
  const b=document.getElementById('banner');
  if(b && localStorage.getItem('wl_banner')===b.dataset.sig) b.style.display='none';
  setView(view);
}})();
</script>
</body></html>"""
