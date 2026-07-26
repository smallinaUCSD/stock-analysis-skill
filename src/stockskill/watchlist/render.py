"""Render the watchlist as a self-contained, sortable HTML table.

Reuses the dashboard's theme CSS. Sparklines are inline SVG (no libraries).
Card/heatmap views and filter chips are added in later sub-steps.
"""

from __future__ import annotations

import html

from ..dashboard.render import _CSS

_SIG_CLASS = {"BUY": "buy", "SELL": "sell", "SHORT": "short", "HOLD": "hold"}

_TABLE_CSS = """
.toolbar{display:flex;gap:10px;align-items:center;margin:12px 0}
.toolbar input{flex:0 0 260px;font-size:14px;padding:8px 11px;border-radius:9px;
  border:1px solid var(--border);background:var(--surface);color:var(--ink)}
.count{color:var(--muted);font-size:12.5px}
.tablewrap{overflow-x:auto;border:1px solid var(--border);border-radius:12px}
table.wl{border-collapse:collapse;width:100%;font-size:12.5px;min-width:900px}
table.wl th,table.wl td{padding:7px 10px;text-align:right;white-space:nowrap;
  border-bottom:1px solid var(--border)}
table.wl th{position:sticky;top:0;background:var(--surface-2);color:var(--muted);
  font-weight:650;text-transform:uppercase;letter-spacing:.03em;font-size:11px;
  cursor:pointer;user-select:none}
table.wl th:first-child,table.wl td:first-child{text-align:left;position:sticky;left:0;
  background:var(--surface)}
table.wl tr:hover td{background:var(--surface-2)}
.tk{font-weight:700} .nm{color:var(--muted);font-size:11px;font-weight:400}
.badge{font-weight:700;font-size:11px;padding:2px 7px;border-radius:6px}
.badge.buy{background:var(--good);color:#fff} .badge.short{background:var(--crit);color:#fff}
.badge.sell{background:var(--warn);color:#111} .badge.hold{color:var(--muted)}
.chip{display:inline-block;font-size:10px;padding:1px 5px;border-radius:5px;margin:1px;
  background:var(--surface-2);border:1px solid var(--border);color:var(--ink)}
.chip.g{color:var(--up);border-color:var(--up)} .chip.r{color:var(--down);border-color:var(--down)}
.up{color:var(--up)} .down{color:var(--down)} .muted{color:var(--muted)}
.arrow.up{color:var(--up)} .arrow.down{color:var(--down)} .arrow.flat{color:var(--muted)}
.conf-STRONG{color:var(--good);font-weight:700}
.conf-MODERATE{color:var(--warn)} .conf-WEAK{color:var(--muted)}
"""


def _pct(x, signed=True):
    if x is None or x != x:
        return ("", "n/a")
    cls = "up" if x >= 0 else "down"
    return (cls, f"{x*100:+.1f}%" if signed else f"{x*100:.1f}%")


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
    pts = " ".join(f"{i/(n-1)*w:.1f},{h - (v-lo)/rng*h:.1f}" for i, v in enumerate(vals))
    color = "var(--up)" if vals[-1] >= vals[0] else "var(--down)"
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'preserveAspectRatio="none"><polyline points="{pts}" fill="none" '
            f'stroke="{color}" stroke-width="1.5"/></svg>')


def _indicator_chips(r) -> str:
    chips = []
    if r.macd_state in ("bull_cross", "bullish"):
        chips.append('<span class="chip g">MACD↑</span>')
    elif r.macd_state in ("bear_cross", "bearish"):
        chips.append('<span class="chip r">MACD↓</span>')
    if r.ichimoku == "above":
        chips.append('<span class="chip g">☁▲</span>')
    elif r.ichimoku == "below":
        chips.append('<span class="chip r">☁▼</span>')
    if r.golden_death == "golden":
        chips.append('<span class="chip g">golden</span>')
    elif r.golden_death == "death":
        chips.append('<span class="chip r">death</span>')
    if r.bb_squeeze:
        chips.append('<span class="chip">squeeze</span>')
    if r.vol_spike:
        chips.append('<span class="chip g">vol↑</span>')
    if "near_52w_high" in r.flags:
        chips.append('<span class="chip g">52wH</span>')
    if "near_52w_low" in r.flags:
        chips.append('<span class="chip r">52wL</span>')
    return "".join(chips) or '<span class="muted">—</span>'


def _row_html(r) -> str:
    if r.error or r.price is None:
        return (f'<tr><td class="tk">{html.escape(r.ticker)}</td>'
                f'<td colspan="13" class="muted">no data</td></tr>')
    def cell(x, signed=True):
        cls, txt = _pct(x, signed)
        return f'<td class="{cls}" data-sort="{x if x is not None else -999}">{txt}</td>'

    sig_cls = _SIG_CLASS.get(r.signal, "hold")
    arrow_cls = "up" if r.trend_score > 1 else ("down" if r.trend_score < -1 else "flat")
    rsi_cls = "up" if (r.rsi or 50) >= 70 else ("down" if (r.rsi or 50) <= 30 else "")
    conf = f'<span class="conf-{r.confidence}">{r.confidence}</span>' if r.confidence else '<span class="muted">—</span>'
    return (
        f'<tr>'
        f'<td><span class="tk">{html.escape(r.ticker)}</span> '
        f'<span class="nm">{html.escape((r.name or "")[:22])}</span></td>'
        f'<td data-sort="{r.price}">${r.price:,.2f}</td>'
        + cell(r.changes.get("1d")) + cell(r.changes.get("5d")) + cell(r.changes.get("1m"))
        + cell(r.changes.get("1y")) +
        f'<td>{_spark(r.sparkline)}</td>'
        f'<td data-sort="{r.trend_score}"><span class="badge {sig_cls}">{r.signal}</span></td>'
        f'<td class="arrow {arrow_cls}" data-sort="{r.trend_score}">{r.trend_arrow}</td>'
        f'<td class="{rsi_cls}" data-sort="{r.rsi if r.rsi is not None else -1}">{_num(r.rsi,0)}</td>'
        f'<td style="text-align:left">{_indicator_chips(r)}</td>'
        f'<td>{conf}</td>'
        f'<td data-sort="{r.pe if r.pe is not None else -1}">{_num(r.pe,1)}</td>'
        f'<td data-sort="{r.market_cap or 0}">{_mktcap(r.market_cap)}</td>'
        f'</tr>'
    )


_HEADERS = ["Ticker", "Price", "Day", "5D", "1M", "1Y", "30d", "Signal",
            "Trend", "RSI", "Indicators", "Conf", "P/E", "Mkt Cap"]


def render_watchlist(rows, title: str = "Watchlist", updated: str = "",
                     status_badge: str = "", status_label: str = "") -> str:
    body = "".join(_row_html(r) for r in rows)
    heads = "".join(
        f'<th onclick="sortBy({i})" data-col="{i}">{h}</th>'
        for i, h in enumerate(_HEADERS))
    ok = sum(1 for r in rows if r.price is not None)
    badge = (f'<span class="status {html.escape(status_label)}">{html.escape(status_badge)}</span>'
             if status_badge else "")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="1800">
<title>{html.escape(title)}</title><style>{_CSS}{_TABLE_CSS}</style></head>
<body><div class="wrap">
<header><h1>{html.escape(title)}</h1>{badge}
  <span class="sub" style="margin:0">Updated {html.escape(updated)}</span></header>
<div class="toolbar">
  <input id="q" placeholder="Filter tickers…" oninput="filt()">
  <span class="count" id="count">{ok} of {len(rows)} tickers</span>
</div>
<div class="tablewrap"><table class="wl" id="wl">
<thead><tr>{heads}</tr></thead><tbody>{body}</tbody></table></div>
<p class="muted" style="font-size:11.5px;margin-top:12px">
Signals are rule-based indicator states, not investment advice. Free data
(yfinance) may be delayed. Click a header to sort. All values computed by tested
Python.</p>
</div>
<script>
let sortState = {{col: null, dir: 1}};
function sortBy(col){{
  const tb = document.querySelector('#wl tbody');
  const rows = Array.from(tb.querySelectorAll('tr')).filter(r=>r.children.length>2);
  sortState.dir = (sortState.col===col) ? -sortState.dir : -1;
  sortState.col = col;
  rows.sort((a,b)=>{{
    const av=parseFloat(a.children[col]?.dataset.sort ?? 'NaN');
    const bv=parseFloat(b.children[col]?.dataset.sort ?? 'NaN');
    if(isNaN(av)&&isNaN(bv)) return 0;
    if(isNaN(av)) return 1; if(isNaN(bv)) return -1;
    return (av-bv)*sortState.dir;
  }});
  rows.forEach(r=>tb.appendChild(r));
}}
function filt(){{
  const q=document.getElementById('q').value.trim().toUpperCase();
  let n=0, tot=0;
  document.querySelectorAll('#wl tbody tr').forEach(r=>{{
    tot++;
    const tk=r.children[0].textContent.toUpperCase();
    const show = !q || tk.includes(q);
    r.style.display = show?'':'none';
    if(show) n++;
  }});
  document.getElementById('count').textContent = n+' of '+tot+' tickers';
}}
</script>
</body></html>"""
