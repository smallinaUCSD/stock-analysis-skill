"""Full-page deep analysis for one ticker: one box per model, live price, and
auto-refresh on the market cadence. Roomier and larger-text than the card modal.

Each model gets its own section (Valuation, Monte Carlo DCF, Trade setup, Position
sizing, Momentum, Regime, Stop study, Virtue of Complexity) so the reader can take
them in one at a time. The math comes from the tested engines; this only lays it
out and links each box to its plain-language guide on /interpret.
"""

from __future__ import annotations

import html as _html
import os

from ..dashboard.render import _CSS
from ..watchlist.render import _CSS_EXTRA, _pct, _SIG_CLASS
from ..trade.setup import atr_trade_setup, position_size
from ..trade.sizing import (win_prob_barrier, kelly_risk_fraction,
                            vol_target_fraction, sizing_plan)
from ..regime import tsmom, dzz_rule, stop_study, voc_timing

_ANALYSIS_CSS = """
body{font-size:15px}
.wrap{max-width:min(1120px,100%);padding:20px clamp(16px,3vw,40px)}
.a-head{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin:4px 0 2px}
.a-head h1{margin:0;font-size:26px}
.a-price{font-size:26px;font-weight:800;font-variant-numeric:tabular-nums;margin-left:auto}
.a-ext{font-size:13px;color:var(--muted);margin:0 0 6px}
.agrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px;margin-top:12px;align-items:start}
.asec{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px 22px}
.a-h{font-size:16px;font-weight:700;margin:0 0 10px;display:flex;align-items:center;gap:8px}
.a-h .stance{font-size:11px;font-weight:700;padding:2px 8px;border-radius:6px}
.a-h .stance.pos{background:var(--good);color:#fff}.a-h .stance.neg{background:var(--crit);color:#fff}
.a-h .stance.midtone{color:var(--muted);border:1px solid var(--border)}
.a-row{display:flex;justify-content:space-between;gap:12px;font-size:14.5px;padding:6px 0;border-top:1px solid var(--border);font-variant-numeric:tabular-nums}
.a-row:first-of-type{border-top:none}
.a-row b{color:var(--ink)}
.a-read{font-size:13px;color:var(--muted);line-height:1.5;margin-top:10px;padding-top:9px;border-top:1px dashed var(--border)}
.fvtab{width:100%;font-size:14.5px;border-collapse:collapse;margin-top:2px}
.fvtab td{padding:6px 4px;border-top:1px solid var(--border)}.fvtab tr:first-child td{border-top:none}
.a-help{color:var(--muted);text-decoration:none;font-weight:700;font-size:13px;margin-left:auto}
.a-help:hover{color:var(--accent)}
.a-back{display:inline-block;margin:14px 0;color:var(--muted);text-decoration:none;font-size:14px}
.a-back:hover{color:var(--ink);text-decoration:underline}
.a-note{color:var(--muted);font-size:12.5px;margin-top:16px;line-height:1.5}
.a-foot{color:var(--muted);font-size:12px;text-align:center;margin:26px 0 6px;padding-top:14px;border-top:1px solid var(--border)}
.up{color:var(--up)}.down{color:var(--down)}.muted{color:var(--muted)}
"""


def _r(label, value, cls=""):
    return f'<div class="a-row"><span>{label}</span><b class="{cls}">{value}</b></div>'


def _box(title, inner, read="", help_id=""):
    # help_id kept for call-site compatibility; per-box links removed in favour of
    # the single "Full guide" link at the bottom of the page.
    readhtml = f'<div class="a-read">{read}</div>' if read else ""
    return f'<div class="asec"><div class="a-h">{title}</div>{inner}{readhtml}</div>'


def _pctpair(x):
    cls, txt = _pct(x)
    return f'<span class="{cls}">{txt}</span>'


# --- per-model sections -------------------------------------------------------
def _valuation_box(r):
    d = r.valuation or {}
    v = d.get("valuation") or {}
    c = d.get("consensus") or {}
    if not v.get("reliable"):
        return _box("Valuation", f'<div class="muted">{_html.escape(v.get("signal") or "no reliable basis (ETF or no fundamentals)")}</div>',
                    help_id="dcf")
    mos = v.get("margin_of_safety") or 0.0
    stance = ("pos", "Undervalued") if mos >= 0.10 else (("neg", "Overvalued") if mos <= -0.10 else ("midtone", "Fairly valued"))
    title = f'Valuation <span class="stance {stance[0]}">{stance[1]}{f" {mos*100:+.0f}%" if mos else ""}</span>'
    price = v.get("price") or r.price
    rows = ""
    if v.get("bear") and v.get("base") and v.get("bull"):
        def frow(lbl, val, c):
            dv = f' <span class="muted">({val/price*100-100:+.0f}% vs price)</span>' if price and val else ""
            return f'<tr><td class="{c}">{lbl}</td><td style="text-align:right"><b>${val:,.0f}</b>{dv}</td></tr>'
        rows = ('<table class="fvtab">' + frow("Bear", v["bear"], "down") +
                frow("Base", v["base"], "") + frow("Bull", v["bull"], "up") + '</table>')
    ig = v.get("implied_market_growth")
    if ig is not None:
        rows += _r("Reverse-DCF implied growth", f"{ig*100:.0f}%/yr")
    reco = c.get("reco")
    if reco and reco != "n/a":
        tvp = c.get("target_vs_price")
        tv = f' &middot; target {_pctpair(tvp)}' if tvp is not None else ""
        rows += _r("Analyst consensus", f"{_html.escape(reco)}{tv}")
    read = ("Fair value from a two-stage discounted cash flow, shown as a bear / base / "
            "bull range. Above the price is cheap, below is expensive; the reverse-DCF "
            "growth is what the price already assumes.")
    return _box(title, rows, read, "dcf")


def _mc_box(r):
    v = (r.valuation or {}).get("valuation") or {}
    p = v.get("mc_prob_undervalued")
    if p is None:
        return ""
    rows = _r("P(undervalued) at price", f"{p*100:.0f}%", "up" if p >= 0.5 else "down")
    if v.get("mc_p5") and v.get("mc_p95"):
        rows += _r("Fair-value band (P5 to P95)", f"${v['mc_p5']:,.0f} to ${v['mc_p95']:,.0f}")
    if v.get("mc_p50"):
        rows += _r("Median fair value", f"${v['mc_p50']:,.0f}")
    read = ("The DCF re-run thousands of times with the assumptions nudged at random. "
            "P(undervalued) is the share of runs worth more than today's price; a high "
            "number with a tight band is a confident cheap read.")
    return _box("Monte Carlo DCF", rows, read, "montecarlo")


def _direction(r):
    if r.signal == "SHORT" or (r.signal == "HOLD" and r.trend_score < 0):
        return "SHORT"
    return "LONG"


def _trade_box(r):
    if not r.atr or not r.price:
        return ""
    d = _direction(r)
    s = atr_trade_setup(r.price, r.atr, d)
    if not s:
        return ""
    rows = (_r("Direction", f"{d} &middot; {s.rr_ratio:.0f}:1 reward/risk") +
            _r("Entry", f"${s.entry:,.2f}") +
            _r("Stop", f"${s.stop:,.2f} (-{s.risk_pct*100:.1f}%)", "down") +
            _r("Target", f"${s.target:,.2f} (+{s.reward_pct*100:.1f}%)", "up"))
    wp = None
    if r.vol_annual and r.drift_annual is not None:
        wp = win_prob_barrier(s.entry, s.target, s.stop, r.drift_annual, r.vol_annual, d)
        if wp is not None:
            rows += _r("P(target before stop)", f"{wp*100:.0f}%", "up" if wp >= 0.5 else "down")
    read = ("A volatility-scaled stop (2x ATR) and a 2:1 target. P(target before stop) is "
            "the estimated chance price reaches the target before the stop, from its recent "
            "drift and volatility. Not a signal to trade; the direction follows the trend.")
    return _box("Trade setup", rows, read, "ptarget")


def _sizing_box(r):
    if not (r.atr and r.price and r.vol_annual and r.drift_annual is not None):
        return ""
    d = _direction(r)
    s = atr_trade_setup(r.price, r.atr, d)
    if not s:
        return ""
    wp = win_prob_barrier(s.entry, s.target, s.stop, r.drift_annual, r.vol_annual, d)
    f = kelly_risk_fraction(wp, s.rr_ratio)
    vf = vol_target_fraction(r.vol_annual)
    rows = _r("Fixed rule", "risk 2% of capital")
    rows += _r("Half-Kelly", f"risk {0.5*f*100:.1f}%" if f > 0 else "no positive edge, pass", "up" if f > 0 else "down")
    if vf:
        rows += _r("Volatility-targeted", f"allocate {vf*100:.0f}% (to ~15% vol)")
    acct = os.environ.get("ACCOUNT_SIZE")
    if acct:
        try:
            pl = sizing_plan(float(acct), s, r.drift_annual, r.vol_annual)
            dollars = []
            if pl.fixed_dollars:
                dollars.append(f"2% ${pl.fixed_dollars:,.0f}")
            if pl.tradable and pl.kelly_dollars:
                dollars.append(f"Kelly ${pl.kelly_dollars:,.0f}")
            if pl.voltarget_dollars:
                dollars.append(f"vol ${pl.voltarget_dollars:,.0f}")
            if dollars:
                rows += _r("Position ($)", " &middot; ".join(dollars))
        except ValueError:
            pass
    read = ("Three ways to size the trade. Kelly bets bigger when the edge (win probability) "
            "is bigger and says pass when there is none; vol-targeting shrinks the position "
            "when the stock is jumpy. Use half-Kelly; full Kelly is very aggressive.")
    return _box("Position sizing", rows, read, "kelly")


def _momentum_box(closes):
    t = tsmom(closes)
    if not t:
        return ""
    sig = "long / uptrend" if t.signal > 0 else ("short / downtrend" if t.signal < 0 else "flat")
    rows = (_r("12-month trend", sig, "up" if t.signal > 0 else "down" if t.signal < 0 else "muted") +
            _r("Trailing 12m return", _pctpair(t.trailing_return)))
    if t.ann_vol:
        rows += _r("Annualized volatility", f"{t.ann_vol*100:.0f}%")
    read = ("Time-series momentum: the sign of the past year's return tends to persist into "
            "the next month. Positive = the trend has been up. Position size scales down when "
            "the stock is more volatile.")
    return _box("Momentum (time-series)", rows, read, "momentum")


def _regime_box(closes):
    z = dzz_rule(closes)
    if not z:
        return ""
    scls = "up" if z.state == "bull" else ("down" if z.state == "bear" else "muted")
    rows = (_r("P(bull regime)", f"{z.p_bull*100:.0f}%", scls) +
            _r("Read", z.state) +
            _r("Bull vs bear drift", f"{z.params.mu_bull*100:+.0f}% vs {z.params.mu_bear*100:+.0f}% /yr"))
    read = ("Dai-Zhang-Zhu treats the market as a hidden bull-or-bear state and estimates the "
            "probability you are in the bull one from the price path. High = the up-trend is "
            "probably intact; the regime is inferred, so read it as an opinion, not a fact.")
    return _box("Regime (Dai-Zhang-Zhu)", rows, read, "regime")


def _stops_box(closes):
    s = stop_study(closes)
    if not s:
        return ""
    verdict = ("helped", "up") if s.helps else ("hurt", "down")
    rows = (_r("A trailing stop would have", verdict[0], verdict[1]) +
            _r("Return vs buy-and-hold", _pctpair(s.stopping_premium) + "/yr") +
            _r("Time in the market", f"{s.pct_in_market*100:.0f}%") +
            _r("Sharpe (stopped vs hold)", f"{s.stopped_sharpe:+.2f} vs {s.buyhold_sharpe:+.2f}"))
    read = ("Backtests a stop-loss on this name. Stops help clean trends but hurt choppy names "
            "(you get whipsawed out and miss the rebound). This tells you which this stock has "
            "been. In-sample, no costs; a guide, not a rule.")
    return _box("Stop study (Kaminski-Lo)", rows, read, "stops")


def _voc_box(closes):
    res = voc_timing(closes, n_features=500)
    if not res:
        return ""
    rows = (_r("Next-month read", res.signal, "up" if res.prediction > 0 else "down") +
            _r("Predicted return", _pctpair(res.prediction)) +
            _r("Out-of-sample R2", f"{res.oos_r2:+.3f}") +
            _r("Timing vs buy-hold Sharpe", f"{res.timing_sharpe:+.2f} vs {res.buyhold_sharpe:+.2f}"))
    read = ("EXPERIMENTAL. A deliberately complex model predicts next month's return. Trust the "
            "out-of-sample R2, not the headline: near zero means no reliable edge here, which is "
            "the usual and honest result. Timing is hard.")
    return _box("Virtue of Complexity (experimental)", rows, read, "voc")


def analysis_html(row, closes=None, refresh_seconds: int = 900) -> str:
    closes = closes or []
    tk = _html.escape(row.ticker)
    name = _html.escape((row.name or row.ticker)[:60])
    price = f"${row.price:,.2f}" if row.price else "n/a"
    dcls, dtxt = _pct(row.changes.get("1d"))
    sig_cls = _SIG_CLASS.get(row.signal, "hold")
    ext = ""
    if getattr(row, "ext_price", None) is not None:
        st = (row.market_state or "").upper()
        lbl = "Pre-market" if st.startswith("PRE") else "After hours"
        ext = f'<div class="a-ext">{lbl} ${row.ext_price:,.2f} {_pctpair(row.ext_change)}</div>'

    boxes = "".join([
        _valuation_box(row), _mc_box(row), _trade_box(row), _sizing_box(row),
        _momentum_box(closes), _regime_box(closes), _stops_box(closes), _voc_box(closes),
    ])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{tk} analysis</title><style>{_CSS}{_CSS_EXTRA}{_ANALYSIS_CSS}</style></head>
<body><div class="wrap">
<div class="a-head"><h1>{tk}</h1><span class="nm">{name}</span>
  <span class="badge {sig_cls}">{_html.escape(row.signal)}</span>
  <span class="a-price">{price} <span class="{dcls}" style="font-size:16px">{dtxt}</span></span></div>
{ext}
<a class="a-back" href="/" onclick="return goBack(event)">&larr; back to board</a>
<div class="agrid">{boxes}</div>
<p class="a-note">Analysis, not advice. Every figure is a model estimate on free,
possibly delayed data; the decision is yours.
<a class="a-help" style="margin:0" href="/interpret" onclick="return openHelp(event)">Full guide &rarr;</a></p>
<div class="a-foot">2026 SMI Investments. All rights reserved.</div>
</div>
<script>
const REFRESH={int(refresh_seconds)}*1000;
function goBack(e){{ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){{ try{{window.opener.focus();}}catch(_){{}}; window.close(); }}
  else location.href='/'; return false; }}
function openHelp(e){{ if(e) e.preventDefault(); window.open(e.currentTarget.getAttribute('href'),'_blank'); return false; }}
let _busy=false;
function refresh(){{ if(_busy) return; _busy=true;
  fetch(location.pathname,{{cache:'no-store'}}).then(r=>r.text()).then(t=>{{
    const d=new DOMParser().parseFromString(t,'text/html');
    ['.agrid','.a-price','.a-ext'].forEach(function(sel){{
      const n=d.querySelector(sel), o=document.querySelector(sel);
      if(n&&o){{ o.innerHTML=n.innerHTML; }} }});
    const nb=d.querySelector('.a-head .badge'), ob=document.querySelector('.a-head .badge');
    if(nb&&ob){{ ob.className=nb.className; ob.textContent=nb.textContent; }}
  }}).catch(function(){{}}).finally(function(){{ _busy=false; }});
}}
if(REFRESH>0 && REFRESH<=3600000) setInterval(refresh, Math.max(60000,REFRESH));
</script>
</body></html>"""
