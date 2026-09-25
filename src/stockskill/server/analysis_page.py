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

from ..dashboard.render import _CSS, _THEME_BOOT, icon
from ..watchlist.render import _CSS_EXTRA, _pct, _SIG_CLASS, glance_html
from ..trade.setup import atr_trade_setup, position_size
from ..trade.sizing import (win_prob_barrier, kelly_risk_fraction,
                            vol_target_fraction, sizing_plan)
from ..regime import tsmom, dzz_rule, stop_study, voc_timing

_ANALYSIS_CSS = """
body{font-size:14px}
.wrap{max-width:min(1080px,100%);padding:22px clamp(16px,3vw,40px) 28px}
.a-tk{font-family:var(--font-mono);font-size:14px;font-weight:500;color:var(--ink-2)}
.a-head{display:flex;align-items:flex-end;gap:16px;flex-wrap:wrap;padding-bottom:18px;
  border-bottom:1px solid var(--border)}
.a-id{display:flex;flex-direction:column;gap:4px;min-width:0}
.a-id-top{display:flex;align-items:center;gap:10px}
.a-head h1{margin:2px 0 0;font-size:48px}
.a-pricebox{margin-left:auto;text-align:right}
.a-head{position:relative}
.a-head .page-x{position:absolute;top:0;right:0;margin:0}
.a-id{padding-right:48px}
.a-pricebox{padding-top:44px}
@media (max-width:640px){.a-pricebox{padding-top:0}}
.a-price{font-size:28px;font-weight:500;line-height:1.1}
.a-price .chg{font-size:16px;font-weight:500;margin-left:4px}
.a-ext{font-size:13px;color:var(--muted);margin-top:3px}
.agroup{margin-top:40px}
.agroup>h2{font-family:var(--font-display);font-size:28px;font-weight:500;letter-spacing:-.02em;
  line-height:1.15;margin:0 0 14px}
.agroup>h2 small{font-family:var(--font);font-size:14px;font-weight:400;color:var(--muted);margin-left:10px}
.agrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(440px,100%),1fr));gap:14px;align-items:start}
.asec{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);padding:20px 22px}
.a-h{font-size:16px;font-weight:500;margin:0 0 12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.a-h .stance{margin-left:0}
.a-row{display:flex;justify-content:space-between;align-items:baseline;gap:16px;font-size:14px;
  padding:6px 0;border-top:1px solid var(--border)}
.a-row:first-of-type{border-top:none}
.a-row>span{color:var(--ink-2)}
.a-row b{color:var(--ink);font-weight:500;text-align:right;text-wrap:balance}
.a-read{font-size:13px;color:var(--muted);line-height:1.55;margin-top:10px;padding-top:10px;
  border-top:1px solid var(--border);max-width:68ch;text-wrap:pretty}
.fvtab{width:100%;font-size:14px;border-collapse:collapse;margin-top:2px}
.fvtab td{padding:6px 4px;border-top:1px solid var(--border)}.fvtab tr:first-child td{border-top:none}
.a-note{color:var(--muted);font-size:13px;margin-top:26px;line-height:1.55}
.a-help{color:var(--link);text-decoration:none;font-weight:500}
.a-help:hover{text-decoration:underline}
.a-foot{color:var(--on-band-soft);background:var(--band);font-size:13px;text-align:center;
  margin:24px 0 4px;padding:22px 16px;border-radius:var(--r-lg)}
.up{color:var(--up)}.down{color:var(--down)}.muted{color:var(--muted)}
.fc-svg{width:100%;height:auto;display:block;margin:6px 0 4px}
.fc-svg text{fill:var(--muted);font-size:11px;font-family:var(--font)}
.idea{border-top:1px solid var(--border);padding:10px 0}
.idea:first-of-type{border-top:none;padding-top:2px}
.idea-h{font-size:14px;font-weight:500;display:flex;justify-content:space-between;gap:10px}
.idea-why{font-size:13px;color:var(--muted);margin:3px 0 6px;line-height:1.5}
.idea-legs{font-size:13px;margin-bottom:6px}
.idea-legs span{display:inline-block;border:1px solid var(--border);border-radius:5px;padding:0 6px;margin:0 4px 4px 0}
.idea-nums{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:4px 12px;font-size:13px}
.idea-nums b{font-weight:500;color:var(--ink)}
.calc{margin-top:12px;padding-top:10px;border-top:1px solid var(--border)}
.calc-h{font-size:14px;font-weight:500;margin-bottom:6px}
.calc label{display:grid;grid-template-columns:1fr auto;gap:2px 10px;font-size:13px;color:var(--ink-2);margin:6px 0}
.calc label input{grid-column:1/-1;width:100%;accent-color:var(--accent)}
.calc label b{font-weight:500;color:var(--ink)}
.calc-out{font-size:14px;margin-top:6px}
.calc-out b{font-weight:500;color:var(--ink)}
.apx-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}
.apx-bar .seg{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden}
.apx-bar .seg button{font:500 13px var(--font);padding:0 12px;height:34px;border:none;background:var(--surface);
  color:var(--muted);cursor:pointer}
.apx-bar .seg button:hover{color:var(--ink)}
.apx-bar .seg button.on{background:var(--surface-3);color:var(--ink)}
.apx-int{font-size:13px;color:var(--muted);margin-left:auto}
#apx{width:100%;height:auto;display:block}
#apx text{fill:var(--muted);font-size:12px;font-family:var(--font)}
.apx-ro{font-size:13px;min-height:20px;margin-top:8px;font-variant-numeric:tabular-nums}
.apx-ro b{color:var(--ink);font-weight:500}
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
def _big(x):
    if x is None:
        return "n/a"
    a = abs(x)
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if a >= div:
            return f"${x/div:,.1f}{unit}"
    return f"${x:,.0f}"


def _valuation_box(r):
    d = r.valuation or {}
    v = d.get("valuation") or {}
    c = d.get("consensus") or {}
    if not v.get("reliable"):
        return _box("Valuation", f'<div class="muted">{_html.escape(v.get("signal") or "no reliable basis (ETF or no fundamentals)")}</div>',
                    help_id="dcf")
    gap = v.get("gap_vs_price")
    gtxt = f" {gap*100:+.0f}% vs price" if gap is not None else ""
    if v.get("priced_on_growth"):
        title = f'Valuation <span class="stance midtone">Priced on future growth</span>'
    else:
        mos = v.get("margin_of_safety") or 0.0
        stance = ("pos", "Undervalued") if mos >= 0.10 else (("neg", "Overvalued") if mos <= -0.10 else ("midtone", "Fairly valued"))
        title = f'Valuation <span class="stance {stance[0]}">{stance[1]}{gtxt}</span>'
    price = v.get("price") or r.price
    rows = ""
    if v.get("bear") and v.get("base") and v.get("bull"):
        def frow(lbl, val, c):
            dv = f' <span class="muted">({val/price*100-100:+.0f}% vs price)</span>' if price and val else ""
            return f'<tr><td class="{c}">{lbl}</td><td style="text-align:right"><b>${val:,.0f}</b>{dv}</td></tr>'
        rows = ('<table class="fvtab">' + frow("Bear", v["bear"], "down") +
                frow("Base", v["base"], "") + frow("Bull", v["bull"], "up") + '</table>')
    asm = v.get("assumptions") or {}
    ig = v.get("implied_market_growth")
    if ig is not None:
        rows += _r("Price needs", f"{ig*100:.0f}%/yr growth for 10 yrs")
    if asm.get("reported_growth") is not None:
        rows += _r("Revenue grew", f'{asm["reported_growth"]*100:.0f}%/yr '
                   f'<span class="muted">({_html.escape(asm.get("growth_source") or "")})</span>')
    inp = v.get("inputs") or {}
    if inp.get("cash_flow") is not None:
        rows += _r("Cash flow used", f'{_big(inp["cash_flow"])}/yr '
                   f'<span class="muted">({_html.escape(inp.get("cash_flow_basis") or "")})</span>')
    if v.get("discount_rate") is not None:
        b, src = v.get("beta_used"), v.get("beta_source") or ""
        btxt = (f' <span class="muted">(beta {b:.2f}, {_html.escape(src)})</span>' if b is not None else "")
        rows += _r("Discount rate", f'{v["discount_rate"]*100:.1f}%{btxt}')
    pe = v.get("peers")
    if pe and pe.get("names"):
        mult = " · ".join(f"{lbl} {pe[k]:.1f}" for k, lbl in (("pe", "P/E"), ("ev_ebitda", "EV/EBITDA"),
                                                                ("ps", "P/S")) if pe.get(k))
        rows += _r("Industry peers", f'{_html.escape(", ".join(pe["names"][:5]))}'
                   + (f' <span class="muted">({mult})</span>' if mult else ""))
    reco = c.get("reco")
    if reco and reco != "n/a":
        tvp = c.get("target_vs_price")
        tv = f', target {_pctpair(tvp)}' if tvp is not None else ""
        rows += _r("Analyst consensus", f"{_html.escape(reco)}{tv}")
    if v.get("dcf_base"):
        g0 = round((asm.get("stage1_growth") or 0.08) * 100)
        r0 = round((v.get("discount_rate") or 0.09) * 200) / 2
        rows += (f'<div class="calc" data-calc="{_html.escape(r.ticker)}"><div class="calc-h">What you\'d have to believe</div>'
                 f'<label>Growth for 10 years <b class="calc-g">{g0}%</b>'
                 f'<input type="range" class="calc-gs" min="0" max="60" step="1" value="{g0}"></label>'
                 f'<label>Discount rate <b class="calc-r">{r0:g}%</b>'
                 f'<input type="range" class="calc-rs" min="6" max="16" step="0.5" value="{r0}"></label>'
                 f'<div class="calc-out muted">Move the sliders to re-run the DCF.</div></div>')
    read = ("A two-stage discounted cash flow shown as a bear / base / bull range. It starts "
            "from the average cash flow of the last three annual reports (after capital spending "
            "and stock pay) and grows it at the company's 3-year revenue growth; banks and insurers "
            "are valued on peers instead. \"Priced on future growth\" means today's cash flows "
            "can't explain the price: the market is paying for growth the company hasn't shown yet.")
    return _box(title, rows + '<div class="a-read vbt" data-vbt="1"></div>', read, "dcf")


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
    rows = (_r("Direction", f"{d.capitalize()}, {s.rr_ratio:.0f}:1 reward/risk") +
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
                rows += _r("Position ($)", ", ".join(dollars))
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


def _risk_box(r):
    rk = getattr(r, "risk", None) or {}
    spy, qqq = rk.get("SPY") or {}, rk.get("QQQ") or {}
    if not spy:
        return ""

    def n2(x):
        return "n/a" if x is None else f"{x:.2f}"
    rows = _r("Beta vs S&amp;P 500", n2(spy.get("beta")))
    if qqq.get("beta") is not None:
        rows += _r("Beta vs Nasdaq-100", n2(qqq.get("beta")))
    if spy.get("alpha") is not None:
        sig = spy.get("alpha_significant")
        t = spy.get("alpha_t")
        note = "" if sig else ' <span class="muted">(within noise'
        note += (f", t {t:+.1f})</span>" if (not sig and t is not None) else (")</span>" if not sig else ""))
        rows += _r("Alpha, per year", _pctpair(spy["alpha"]) + note)
    rows += _r("Sharpe · Sortino", f'{n2(spy.get("sharpe"))} · {n2(spy.get("sortino"))}')
    if spy.get("vol") is not None:
        rows += _r("Volatility", f'{spy["vol"]*100:.0f}% a year')
    if spy.get("max_drawdown") is not None:
        rows += _r("Max drawdown", _pctpair(spy["max_drawdown"]))
    if spy.get("up_capture") is not None and spy.get("down_capture") is not None:
        rows += _r("Up · down capture", f'{spy["up_capture"]*100:.0f}% · {spy["down_capture"]*100:.0f}%')
    if spy.get("correlation") is not None:
        rows += _r("Correlation with the S&amp;P 500", n2(spy["correlation"]))
    read = ("Measured over the last year of daily returns. Beta is how much it tends to move "
            "when the market moves (Welch's robust estimate, which damps one-off jumps). Alpha "
            "is the return left over after accounting for that market exposure; over one year "
            "it is usually too noisy to trust, which is what &ldquo;within noise&rdquo; means. "
            "Capture compares its average up-day and down-day moves with the market's.")
    return _box("Risk vs the market", rows, read, "risk")


# Filled in the browser from /api/options/<ticker> (Yahoo can be slow; the page
# must not wait on it). Re-rendered after each auto-refresh swaps the sections.
_OPTIONS_BOX = ('<div class="asec" data-opt="1"><div class="a-h">Options market</div>'
                '<div class="opt-body muted">Loading option prices…</div></div>')


from .analyst_js import ANALYST_CSS, ANALYST_JS

# fetched once per page; re-drawn after each auto-refresh swaps the sections
_AN_JS = r"""
var _AN=null;
function anRender(){ var el=document.querySelector('[data-an] .an-body'); if(!el) return;
  if(_AN){ el.classList.remove('muted'); el.innerHTML=anHTML(_AN); return; }
  fetch('/api/analysts/'+encodeURIComponent(TK)).then(function(r){return r.json();}).then(function(d){ _AN=d; anRender(); })
    .catch(function(){ el.textContent='Analyst ratings unavailable.'; }); }
anRender();
var _DV=null;
function dvRender(){ var el=document.querySelector('[data-dv] .dv-body'); if(!el) return;
  if(_DV){ el.classList.remove('muted'); el.innerHTML=dvHTML(_DV); return; }
  fetch('/api/dividends/'+encodeURIComponent(TK)).then(function(r){return r.json();}).then(function(d){ _DV=d; dvRender(); })
    .catch(function(){ el.textContent='Dividend data unavailable.'; }); }
dvRender();
"""

# Tabs: the other research pages load inside this one (no new browser tabs).
_TABS_JS = r"""
var TABS={financials:'/financials?t=',earnings:'/earnings?t=',connections:'/graph?t='};
function showTab(t){ if(!document.getElementById('tab-'+t)) t='overview';
  document.querySelectorAll('.a-tabs button').forEach(function(b){ b.classList.toggle('on',b.getAttribute('data-tab')===t); });
  document.querySelectorAll('.a-tab').forEach(function(el){ el.hidden=el.id!=='tab-'+t; });
  var box=document.getElementById('tab-'+t);
  if(TABS[t] && !box.firstChild){ var f=document.createElement('iframe'); f.src=TABS[t]+encodeURIComponent(TK)+'&embed=1';
    f.title=t; box.appendChild(f); }
  try{ history.replaceState(null,'',t==='overview'?location.pathname:'#'+t); }catch(_){} }
document.querySelectorAll('.a-tabs button').forEach(function(b){ b.addEventListener('click',function(){ showTab(b.getAttribute('data-tab')); }); });
window.addEventListener('message',function(e){ if(e.origin!==location.origin||!e.data||!e.data.embedHeight) return;
  document.querySelectorAll('.a-tab iframe').forEach(function(f){ if(f.contentWindow===e.source) f.style.height=(e.data.embedHeight+20)+'px'; }); });
if(location.hash) showTab(location.hash.slice(1));
function glance(key, value, sub){ var c=document.querySelector('.g-c[data-g="'+key+'"]'); if(!c) return;
  c.querySelector('.g-v').textContent=value; c.querySelector('.g-s').textContent=sub||''; }
fetch('/api/analysts/'+encodeURIComponent(TK)).then(function(r){return r.json();}).then(function(d){
  if(!d.ok){ glance('an','n/a','no coverage'); return; }
  glance('an', d.label||'n/a', d.upside!=null?'target '+(d.upside>=0?'+':'')+(d.upside*100).toFixed(0)+'% vs price':(d.analysts?d.analysts+' analysts':'')); })
  .catch(function(){ glance('an','n/a'); });
fetch('/api/dividends/'+encodeURIComponent(TK)).then(function(r){return r.json();}).then(function(d){
  if(!d.ok){ glance('dv','n/a'); return; }
  if(!d.pays){ glance('dv','None','doesn\'t pay one'); return; }
  glance('dv', d.yield!=null?(d.yield*100).toFixed(2)+'%':'n/a', '$'+d.ttm.toFixed(2)+' a year'+(d.streak?' · raised '+d.streak+' yrs':'')); })
  .catch(function(){ glance('dv','n/a'); });
"""


_ANALYST_BOX = ('<div class="asec" data-an="1"><div class="a-h">Analyst ratings</div>'
                '<div class="an-body muted">Loading…</div></div>')
_DIV_BOX = ('<div class="asec" data-dv="1"><div class="a-h">Dividends</div>'
            '<div class="dv-body muted">Loading…</div></div>')


_FORECAST_BOX = ('<div class="asec" data-fc="1"><div class="a-h">Price range forecast</div>'
                 '<div class="fc-body muted">Loading…</div></div>')
_IDEAS_BOX = ('<div class="asec" data-oi="1"><div class="a-h">Option trade ideas</div>'
              '<div class="oi-body muted">Loading option chain…</div></div>')

# Filled in the browser from /api/signals/<ticker> (Finnhub Form 4 + Yahoo).
_SIGNAL_BOXES = tuple(
    f'<div class="asec" data-sig="{k}"><div class="a-h">{t}</div>'
    f'<div class="sig-body muted">Loading…</div></div>'
    for k, t in (("insiders", "Insider trades"), ("short", "Short interest"),
                 ("quality", "Accounting quality"), ("holders", "Politicians &amp; funds")))


_VOL_UP = {"accumulation", "bullish-divergence"}
_VOL_DOWN = {"distribution", "bearish-divergence"}


def _volume_box(r):
    vs = getattr(r, "volume_signal", None) or {}
    mfi = getattr(r, "mfi", None)
    rvol = getattr(r, "rvol", None)
    if mfi is None and rvol is None and not vs:
        return ""
    rows = ""
    if rvol is not None:
        rows += _r("Relative volume", f"{rvol:.1f}x average",
                   "up" if rvol >= 1.5 else ("muted" if rvol < 0.7 else ""))
    if mfi is not None:
        tag = " (oversold)" if mfi <= 20 else (" (overbought)" if mfi >= 80 else "")
        mcls = "up" if mfi <= 20 else ("down" if mfi >= 80 else "")
        rows += _r("Money Flow Index", f"{mfi:.0f}{tag}", mcls)
    if vs.get("label"):
        st = vs.get("state", "")
        cls = "up" if st in _VOL_UP else ("down" if st in _VOL_DOWN else "muted")
        rows += (f'<div class="a-row"><span>Read</span>'
                 f'<b class="{cls}">{_html.escape(vs["label"])}</b></div>')
    read = ("Volume confirms a price move when money flow agrees with it: rising OBV and "
            "above-average volume back a trend, while a divergence (price and volume "
            "disagreeing) is an early warning of a fakeout. MFI is a volume-weighted RSI "
            "(over 80 overbought, under 20 oversold).")
    return _box("Volume & money flow", rows, read, "volume")


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

    rv = ((getattr(row, "risk", None) or {}).get("SPY") or {}).get("vol") or row.vol_annual
    rvol = "null" if rv is None else f"{rv:.4f}"

    def group(title, note, *boxes):
        inner = "".join(b for b in boxes if b)
        if not inner:
            return ""
        sub = f"<small>{note}</small>" if note else ""
        return f'<section class="agroup"><h2>{title}{sub}</h2><div class="agrid">{inner}</div></section>'

    # Grouped by the question each answers, most decision-relevant first, so the
    # experimental model no longer carries the same weight as the valuation.
    sections = (
        group("Valuation", "what the business is worth", _valuation_box(row), _mc_box(row), _ANALYST_BOX, _DIV_BOX)
        + group("Forecast and option ideas", "a range, not a target", _FORECAST_BOX, _IDEAS_BOX)
        + group("Risk", "how it moves with the market", _risk_box(row))
        + group("Filings and positioning", "insiders, short sellers, the accounts", *_SIGNAL_BOXES)
        + group("Trade plan", "entry, exits and size", _trade_box(row), _sizing_box(row),
                _OPTIONS_BOX)
        + group("Trend and flow", "is the move backed?", _momentum_box(closes),
                _volume_box(row), _regime_box(closes), _stops_box(closes))
        + group("Experimental", "", _voc_box(closes))
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{tk} analysis</title>{_THEME_BOOT}<style>{_CSS}{_CSS_EXTRA}{_ANALYSIS_CSS}{ANALYST_CSS}</style></head>
<body><div class="wrap">
<header class="a-head">
  <div class="a-id"><div class="a-id-top"><span class="a-tk">{tk}</span>
    <span class="badge {sig_cls}">{_html.escape(row.signal)}</span></div>
    <h1>{name}</h1></div>
  <div class="a-pricebox"><div class="a-price">{price}<span class="chg {dcls}">{dtxt}</span></div>{ext}
    </div>
  <button class="page-x" onclick="return goBack(event)" title="Close" aria-label="Close">{icon("x", 17)}</button>
</header>
{glance_html(row)}
<nav class="a-tabs" role="tablist"><button data-tab="overview" class="on">Overview</button><button data-tab="financials">Financials</button>
<button data-tab="earnings">Earnings</button><button data-tab="connections">Connections</button></nav>
<div id="tab-overview" class="a-tab">
<section class="agroup"><h2>Price<small>candles and volume</small></h2>
<div class="asec">
  <div class="apx-bar">
    <span class="seg" id="apx-per"><button data-p="1mo">1M</button><button data-p="3mo">3M</button><button data-p="6mo" class="on">6M</button><button data-p="1y">1Y</button><button data-p="2y">2Y</button><button data-p="5y">5Y</button></span>
    <span class="seg" id="apx-mode"><button data-m="candle" class="on">Candles</button><button data-m="line">Line</button></span>
    <span id="apx-int" class="apx-int"></span>
  </div>
  <svg id="apx" viewBox="0 0 1000 340" preserveAspectRatio="xMidYMid meet" role="img" aria-label="{tk} price chart"></svg>
  <div id="apx-ro" class="apx-ro muted">Loading price history…</div>
</div></section>
<div class="asections">{sections}</div>
</div>
<div id="tab-financials" class="a-tab" hidden></div><div id="tab-earnings" class="a-tab" hidden></div>
<div id="tab-connections" class="a-tab" hidden></div>
<p class="a-note">Analysis, not advice. Every figure is a model estimate on free,
possibly delayed data; the decision is yours.
<a class="a-help" href="/interpret" onclick="return openHelp(event)">Read the full guide</a></p>
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
    ['.asections','.a-price','.a-ext'].forEach(function(sel){{
      const n=d.querySelector(sel), o=document.querySelector(sel);
      if(n&&o){{ o.innerHTML=n.innerHTML; }} }});
    if(window.optRender) optRender();
    if(window.sigRender) sigRender();
    if(window.holdRender) holdRender();
    if(window.calcInit) calcInit();
    if(window.fcRender) {{ fcRender(); oiRender(); }}
    if(window.anRender) anRender();
    if(window.dvRender) dvRender();
    const nb=d.querySelector('.a-head .badge'), ob=document.querySelector('.a-head .badge');
    if(nb&&ob){{ ob.className=nb.className; ob.textContent=nb.textContent; }}
  }}).catch(function(){{}}).finally(function(){{ _busy=false; }});
}}
if(REFRESH>0 && REFRESH<=3600000) setInterval(refresh, Math.max(60000,REFRESH));
</script>
<script>var TK="{tk}", RVOL={rvol};
""" + _PRICE_JS + _OPT_JS + _SIG_JS + _CALC_JS + _FC_JS + ANALYST_JS + _AN_JS + _TABS_JS + """</script>
</body></html>"""


_PRICE_JS = r"""
var APX={per:'6mo', mode:'candle', d:null}, AW=1000, AH=340, AML=58, AMR=12, AMT=10;
function apxEl(t,a){ var e=document.createElementNS('http://www.w3.org/2000/svg',t); for(var k in a) e.setAttribute(k,a[k]); return e; }
function apxStep(r,t){ var raw=(r||1)/Math.max(1,t), p=Math.pow(10,Math.floor(Math.log10(raw))), n=raw/p;
  return (n<1.5?1:(n<3?2:(n<7?5:10)))*p; }
function apxMoney(v){ return '$'+Number(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}); }
function apxVol(v){ var a=Math.abs(v); return a>=1e9?(v/1e9).toFixed(2)+'B':(a>=1e6?(v/1e6).toFixed(1)+'M':(a>=1e3?(v/1e3).toFixed(0)+'k':''+v)); }
function apxDate(iso){ var p=iso.split('-'); return (+p[1])+'/'+(+p[2])+'/'+p[0].slice(2); }
function apxLoad(){
  document.getElementById('apx-ro').textContent='Loading price history…';
  fetch('/api/ohlc/'+encodeURIComponent(TK)+'?period='+APX.per).then(function(r){return r.json();}).then(function(d){
    if(d.error){ document.getElementById('apx-ro').textContent=d.error; return; }
    APX.d=d; apxDraw(); }).catch(function(){ document.getElementById('apx-ro').textContent='Price history unavailable.'; });
}
function apxDraw(){
  var d=APX.d; if(!d) return; var svg=document.getElementById('apx'); svg.innerHTML='';
  AW=(svg.parentNode.clientWidth||1000)<640?560:1000; AH=AW<1000?300:340; svg.setAttribute('viewBox','0 0 '+AW+' '+AH);
  var n=d.close.length, VH=AW<1000?46:58, gap=10, xb=AH-20, py0=xb-VH-gap, py1=AMT;
  var slot=(AW-AML-AMR)/n, X=function(i){ return AML+slot*(i+0.5); };
  var candle=APX.mode==='candle';
  var lo=Math.min.apply(null,candle?d.low:d.close), hi=Math.max.apply(null,candle?d.high:d.close);
  var pad=(hi-lo)*0.05||1; lo-=pad; hi+=pad;
  var Y=function(v){ return py0-(v-lo)/(hi-lo)*(py0-py1); };
  var st=apxStep(hi-lo,5);
  for(var g=Math.ceil(lo/st)*st; g<=hi; g+=st){ if(g<=0) continue; var yy=Y(g);
    svg.appendChild(apxEl('line',{x1:AML,y1:yy,x2:AW-AMR,y2:yy,stroke:'var(--border)','stroke-width':0.7,opacity:0.7}));
    var t=apxEl('text',{x:AML-6,y:yy+4,'text-anchor':'end'}); t.textContent='$'+(g>=1000?(g/1000).toFixed(1)+'k':(g<10?g.toFixed(2):g.toFixed(0))); svg.appendChild(t); }
  var vmax=Math.max.apply(null,d.volume.concat([1]));
  var bw=Math.max(1,Math.min(14,slot*0.66));
  for(var i=0;i<n;i++){
    var up=d.close[i]>=d.open[i], col=up?'var(--up)':'var(--down)', x=X(i);
    var vh=(d.volume[i]||0)/vmax*VH;
    svg.appendChild(apxEl('rect',{x:x-bw/2,y:xb-vh,width:bw,height:Math.max(0,vh),fill:col,opacity:0.28}));
    if(candle){
      svg.appendChild(apxEl('line',{x1:x,y1:Y(d.high[i]),x2:x,y2:Y(d.low[i]),stroke:col,'stroke-width':1}));
      var yo=Y(d.open[i]), yc=Y(d.close[i]);
      svg.appendChild(apxEl('rect',{x:x-bw/2,y:Math.min(yo,yc),width:bw,height:Math.max(1,Math.abs(yo-yc)),fill:col}));
    }
  }
  if(!candle){
    var up2=d.close[n-1]>=d.close[0], lc=up2?'var(--up)':'var(--down)';
    var pts=d.close.map(function(v,i){ return X(i).toFixed(1)+','+Y(v).toFixed(1); }).join(' ');
    svg.appendChild(apxEl('polygon',{points:X(0).toFixed(1)+','+py0+' '+pts+' '+X(n-1).toFixed(1)+','+py0,fill:lc,opacity:0.08}));
    svg.appendChild(apxEl('polyline',{points:pts,fill:'none',stroke:lc,'stroke-width':1.7}));
  }
  svg.appendChild(apxEl('line',{x1:AML,y1:xb,x2:AW-AMR,y2:xb,stroke:'var(--border)','stroke-width':0.8}));
  var tv=apxEl('text',{x:AML-6,y:xb-VH+10,'text-anchor':'end'}); tv.textContent='Vol'; svg.appendChild(tv);
  var ticks=AW<1000?[0,Math.floor((n-1)/2),n-1]:[0,Math.floor((n-1)/4),Math.floor((n-1)/2),Math.floor(3*(n-1)/4),n-1];
  ticks.forEach(function(i,k){ var t=apxEl('text',{x:X(i),y:AH-5,'text-anchor':k===0?'start':(k===ticks.length-1?'end':'middle')});
    t.textContent=apxDate(d.dates[i]); svg.appendChild(t); });
  svg.appendChild(apxEl('line',{id:'apx-cx',x1:0,y1:py1,x2:0,y2:xb,stroke:'var(--muted)','stroke-width':1,style:'display:none'}));
  svg._g={X:X,n:n,slot:slot};
  document.getElementById('apx-int').textContent=d.interval==='1wk'?'Weekly bars':'Daily bars';
  apxRead(n-1);
}
function apxRead(i){ var d=APX.d, ch=i>0?d.close[i]/d.close[i-1]-1:null;
  var cls=ch==null?'':(ch>=0?'up':'down');
  document.getElementById('apx-ro').innerHTML='<span>'+apxDate(d.dates[i])+(d.interval==='1wk'?' (week)':'')+'</span> &nbsp; '+
    'O <b>'+apxMoney(d.open[i])+'</b> &nbsp; H <b>'+apxMoney(d.high[i])+'</b> &nbsp; L <b>'+apxMoney(d.low[i])+
    '</b> &nbsp; C <b>'+apxMoney(d.close[i])+'</b>'+(ch==null?'':' <span class="'+cls+'">'+(ch>=0?'+':'')+(ch*100).toFixed(2)+'%</span>')+
    ' &nbsp; Vol <b>'+apxVol(d.volume[i]||0)+'</b>'; }
(function(){
  var svg=document.getElementById('apx');
  svg.addEventListener('mousemove',function(e){ var g=svg._g; if(!g) return; var r=svg.getBoundingClientRect();
    var vx=(e.clientX-r.left)*(AW/r.width), i=Math.floor((vx-AML)/g.slot); i=Math.max(0,Math.min(g.n-1,i));
    var cx=document.getElementById('apx-cx'); cx.setAttribute('x1',g.X(i)); cx.setAttribute('x2',g.X(i)); cx.style.display=''; apxRead(i); });
  svg.addEventListener('mouseleave',function(){ var cx=document.getElementById('apx-cx'); if(cx) cx.style.display='none'; if(APX.d) apxRead(APX.d.close.length-1); });
  function seg(id,key,after){ document.getElementById(id).addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return;
    [].forEach.call(this.querySelectorAll('button'),function(x){ x.classList.toggle('on',x===b); }); APX[key]=b.dataset[key==='per'?'p':'m']; after(); }); }
  seg('apx-per','per',apxLoad); seg('apx-mode','mode',apxDraw);
  var t=null; window.addEventListener('resize',function(){ clearTimeout(t); t=setTimeout(apxDraw,150); });
  apxLoad();
})();
"""

_OPT_JS = r"""
var OPT=null;
function optMoney(v){ return '$'+Number(v).toLocaleString(undefined,{maximumFractionDigits:v<100?2:0}); }
function optDate(iso){ var p=iso.split('-'); return ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+p[1]-1]+' '+(+p[2]); }
function optRender(){
  var box=document.querySelector('[data-opt] .opt-body'); if(!box) return;
  if(!OPT){ return; }
  if(!OPT.available){ box.className='opt-body muted'; box.textContent='No option prices available for this ticker right now.'; return; }
  var rows=OPT.moves.map(function(m){
    return '<div class="a-row"><span>'+m.label+' <span class="muted">('+optDate(m.expiry)+')</span></span>'+
      '<b>&plusmn;'+(m.move_pct*100).toFixed(1)+'% <span class="muted">('+optMoney(m.low)+' to '+optMoney(m.high)+')</span></b></div>'; }).join('');
  var iv=OPT.moves.length?OPT.moves[Math.min(1,OPT.moves.length-1)].iv:null;
  if(iv!=null){
    var cmp=RVOL?(' <span class="muted">vs '+(RVOL*100).toFixed(0)+'% realized</span>'):'';
    rows+='<div class="a-row"><span>Implied volatility</span><b>'+(iv*100).toFixed(0)+'% a year'+cmp+'</b></div>'; }
  var read='What the options market is charging for a move either way: the price of an at-the-money call plus put. '+
    'About 58% of outcomes land inside that range if the market is right. Implied volatility above realized means '+
    'options are pricing in more movement than the stock has lately shown (often around earnings).'+
    (OPT.stale?' Priced from last trades while the market is closed, so approximate.':'');
  box.className='opt-body'; box.innerHTML=rows+'<div class="a-read">'+read+'</div>';
}
(function(){ fetch('/api/options/'+encodeURIComponent(TK)).then(function(r){return r.json();})
  .then(function(d){ OPT=d; optRender(); }).catch(function(){ OPT={available:false}; optRender(); }); })();
"""

_SIG_JS = r"""
var SIG=null;
function sigEsc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
function sigMoney(v){ var a=Math.abs(v||0); return a>=1e9?'$'+(v/1e9).toFixed(2)+'B':(a>=1e6?'$'+(v/1e6).toFixed(1)+'M':(a>=1e3?'$'+(v/1e3).toFixed(0)+'k':'$'+Math.round(v||0))); }
function sigRow(k,v){ return '<div class="a-row"><span>'+k+'</span><b>'+v+'</b></div>'; }
function sigSet(key, html, muted){ var b=document.querySelector('[data-sig="'+key+'"] .sig-body'); if(!b) return;
  b.className='sig-body'+(muted?' muted':''); b.innerHTML=html; }
function sigRender(){
  if(!SIG) return;
  var ins=SIG.insiders;
  if(!ins){ sigSet('insiders','Insider data unavailable right now.',true); }
  else {
    var h='<div class="a-row"><span>Last '+ins.days+' days</span><b class="'+(ins.tone==='up'?'up':(ins.tone==='down'?'down':''))+'">'+sigEsc(ins.label)+'</b></div>'+
      sigRow('Open-market buys', ins.buys+(ins.buys?' <span class="muted">('+sigMoney(ins.buy_value)+', '+ins.opportunistic_buys+' opportunistic)</span>':''))+
      sigRow('Open-market sells', ins.sells+(ins.sells?' <span class="muted">('+sigMoney(ins.sell_value)+')</span>':''));
    if(ins.buyers&&ins.buyers.length) h+=sigRow('Buyers', '<span style="font-weight:400">'+ins.buyers.slice(0,4).map(sigEsc).join(', ')+'</span>');
    h+='<div class="a-read">From SEC Form 4 filings. Only open-market trades count; grants, option exercises and tax '+
      'withholding are ignored. Insiders who trade in the same month every year are routine and tell you little. '+
      'Research (Cohen, Malloy &amp; Pomorski, 2012) found the out-of-pattern, opportunistic trades carried the information, '+
      'buys especially. Selling is common for diversification and taxes.</div>';
    sigSet('insiders', h);
  }
  var si=SIG.short;
  if(!si){ sigSet('short','Short interest unavailable for this ticker.',true); }
  else {
    var pf=si.pct_float, cls=pf==null?'':(pf>=0.10?'down':'');
    var h2=sigRow('Short interest', pf==null?'n/a':'<span class="'+cls+'">'+(pf*100).toFixed(1)+'% of float</span>')+
      sigRow('Days to cover', si.days_to_cover==null?'n/a':si.days_to_cover.toFixed(1)+' days of volume')+
      (si.change_vs_prior==null?'':sigRow('vs prior month', (si.change_vs_prior>=0?'+':'')+(si.change_vs_prior*100).toFixed(1)+'%'))+
      (si.as_of?sigRow('As of', si.as_of):'')+
      '<div class="a-read">Shares sold short as a share of the tradable float, reported twice a month. Above about 10% '+
      'means a lot of investors are betting against it: on average heavily shorted stocks have lagged, but a crowded '+
      'short can also force a sharp squeeze when news turns good. Days to cover is how long shorts would need to buy '+
      'back at normal volume.</div>';
    sigSet('short', h2);
  }
  var q=SIG.quality;
  if(!q){ sigSet('quality','Financial statements unavailable (funds and some foreign listings have none).',true); }
  else {
    var h3='<div class="a-row"><span>Piotroski F-score</span><b class="'+(q.tone==='up'?'up':(q.tone==='down'?'down':''))+'">'+
      q.score+' of '+q.max+'</b></div><div class="a-row"><span>Read</span><b style="font-weight:400">'+sigEsc(q.label)+'</b></div>';
    h3+=q.checks.map(function(c){ var mark=c[1]===true?'<span class="up">&#10003;</span>':(c[1]===false?'<span class="down">&#10007;</span>':'<span class="muted">&ndash;</span>');
      return '<div class="a-row"><span>'+mark+' '+sigEsc(c[0])+'</span><b class="muted" style="font-weight:400">'+sigEsc(c[2])+'</b></div>'; }).join('');
    if(q.accruals!=null) h3+=sigRow('Accruals (Sloan)', '<span class="'+(q.accruals>0.10?'down':(q.accruals<0?'up':''))+'">'+(q.accruals*100).toFixed(1)+'% of assets</span>');
    h3+='<div class="a-read">Nine pass/fail checks on the last two annual reports (Piotroski, 2000): profitable, '+
      'cash-generating, less indebted, not diluting, and getting more efficient. 8 or 9 is strong, 0 to 2 weak. '+
      'Accruals are profit not yet backed by cash; high accruals have tended to precede weaker earnings (Sloan, 1996). '+
      'A dash means the data isn\'t reported (banks have no gross margin, for example).</div>';
    sigSet('quality', h3);
  }
}
var HOLD=null;
function holdRender(){ if(!HOLD) return;
  var f=HOLD.funds||[], c=HOLD.congress||[];
  var buys=c.filter(function(t){return (t.type||'').indexOf('Buy')===0;}).length, sells=c.filter(function(t){return (t.type||'').indexOf('Sell')===0;}).length;
  var h=sigRow('Tracked funds holding it', f.length?f.slice(0,3).map(function(x){ return sigEsc(x.fund)+' <span class="muted">('+(x.weight*100).toFixed(1)+'%, '+sigEsc((x.change||'').toLowerCase())+')</span>'; }).join('<br>'):'<span class="muted">none</span>');
  h+=sigRow('Congress, last 90 days', c.length?'<span class="up">'+buys+' buys</span> · <span class="down">'+sells+' sells</span>':'<span class="muted">no trades reported</span>');
  if(c.length){ var t=c[0]; h+=sigRow('Latest', sigEsc(t.member)+' <span class="muted">('+sigEsc(t.chamber)+')</span> '+sigEsc((t.type||'').toLowerCase())+' '+sigEsc(t.amount)); }
  h+='<div class="a-read">Funds: SEC 13F filings of well-known managers (long positions, up to 45 days old). Congress: members\' '+
    'reported trades (up to 45 days late; not market-beating on average). <a class="a-help" href="/trades?q='+encodeURIComponent(TK)+'" target="_blank" rel="noopener">See all on Trades</a></div>';
  sigSet('holders', h); }
fetch('/api/holders/'+encodeURIComponent(TK)).then(function(r){return r.json();}).then(function(d){ HOLD=d; holdRender(); }).catch(function(){ sigSet('holders','Unavailable right now.',true); });
(function(){ fetch('/api/signals/'+encodeURIComponent(TK)).then(function(r){return r.json();})
  .then(function(d){ SIG=d; sigRender(); }).catch(function(){ SIG={}; sigRender(); }); })();
"""

_CALC_JS = r"""
var VBT=null, _ct=null;
function calcRun(box){
  var g=+box.querySelector('.calc-gs').value, r=+box.querySelector('.calc-rs').value;
  box.querySelector('.calc-g').textContent=g+'%'; box.querySelector('.calc-r').textContent=r+'%';
  clearTimeout(_ct); _ct=setTimeout(function(){
    fetch('/api/dcf/'+encodeURIComponent(box.dataset.calc)+'?g='+(g/100)+'&r='+(r/100)).then(function(x){return x.json();})
      .then(function(d){ var out=box.querySelector('.calc-out');
        if(d.error){ out.textContent=d.error; return; }
        var cls=d.gap>=0?'up':'down';
        out.className='calc-out';
        out.innerHTML='Worth <b>$'+Math.round(d.fair_value).toLocaleString()+'</b> a share <span class="'+cls+'">('+
          (d.gap>=0?'+':'')+Math.round(d.gap*100)+'% vs price)</span>'+
          (d.implied_growth!=null?'. At '+r+'%, the price needs <b>'+Math.round(d.implied_growth*100)+'%/yr</b> growth.':'.');
      }).catch(function(){}); }, 200);
}
function calcInit(){
  document.querySelectorAll('[data-calc]').forEach(function(box){
    box.querySelectorAll('input').forEach(function(i){ i.addEventListener('input', function(){ calcRun(box); }); });
  });
  vbtRender();
}
function vbtRender(){ var el=document.querySelector('[data-vbt]'); if(!el||!VBT) return;
  var n=VBT.normalized; if(!n){ el.style.display='none'; return; }
  var worked=n.spread>0 && n.ic>0.05;
  el.innerHTML='<b>Track record on this watchlist:</b> rebuilding this DCF from the filings public at the time ('+
    n.years.map(function(y){return y.year;}).join(', ')+', '+n.n_obs+' stock-years), the stocks it called cheapest returned '+
    (n.spread>=0?'<span class="up">':'<span class="down">')+(n.spread>=0?'+':'')+Math.round(n.spread*100)+
    ' pts a year</span> vs the priciest third (rank correlation '+n.ic.toFixed(2)+'). '+
    (worked?'A modest edge, not a timing tool.':'So far it has not predicted next-year returns here: read it as what today\'s cash flows support, not as a timing signal.');
}
(function(){ calcInit();
  fetch('/api/valuation/backtest').then(function(x){return x.json();}).then(function(d){ if(d.ok){ VBT=d; vbtRender(); } }).catch(function(){}); })();
"""

_FC_JS = r"""
var FC=null, OI=null;
function fcMoney(v){ return '$'+Number(v).toLocaleString(undefined,{maximumFractionDigits:v<100?2:0}); }
function fcRender(){ var box=document.querySelector('[data-fc] .fc-body'); if(!box||!FC) return;
  if(!FC.ok){ box.className='fc-body muted'; box.textContent=FC.error||'Unavailable.'; return; }
  var lbl={21:'1 month',63:'3 months',126:'6 months',252:'1 year'};
  var rows=FC.ranges.map(function(r){ return '<div class="a-row"><span>'+lbl[r.days]+'</span><b>'+fcMoney(r.p10)+' to '+fcMoney(r.p90)+
    ' <span class="muted">(middle half '+fcMoney(r.p25)+' to '+fcMoney(r.p75)+')</span></b></div>'; }).join('');
  // fan chart
  var c=FC.cone, W=480, H=150, L=46, R=8, T=8, B=18, n=c.days.length;
  var lo=Math.min.apply(null,c.p10), hi=Math.max.apply(null,c.p90);
  var X=function(i){ return L+i/(n-1)*(W-L-R); }, Y=function(v){ return T+(hi-v)/(hi-lo)*(H-T-B); };
  var band=function(a,b,op){ var top=c[b].map(function(v,i){return X(i).toFixed(1)+','+Y(v).toFixed(1);}), bot=c[a].map(function(v,i){return X(i).toFixed(1)+','+Y(v).toFixed(1);}).reverse();
    return '<polygon points="'+top.concat(bot).join(' ')+'" fill="var(--accent)" opacity="'+op+'"/>'; };
  var mid='<polyline points="'+c.p50.map(function(v,i){return X(i).toFixed(1)+','+Y(v).toFixed(1);}).join(' ')+'" fill="none" stroke="var(--accent)" stroke-width="1.5"/>';
  var sp='<line x1="'+L+'" y1="'+Y(FC.spot)+'" x2="'+(W-R)+'" y2="'+Y(FC.spot)+'" stroke="var(--muted)" stroke-dasharray="3 3" stroke-width="0.8"/>';
  var ax=[hi,FC.spot,lo].map(function(v){ return '<text x="'+(L-4)+'" y="'+(Y(v)+4)+'" text-anchor="end">'+fcMoney(v)+'</text>'; }).join('')+
    ['Now','6 mo','1 yr'].map(function(t,k){ return '<text x="'+X([0,(n-1)/2,n-1][k])+'" y="'+(H-4)+'" text-anchor="'+['start','middle','end'][k]+'">'+t+'</text>'; }).join('');
  var svg='<svg class="fc-svg" viewBox="0 0 '+W+' '+H+'">'+band('p10','p90',0.12)+band('p25','p75',0.22)+mid+sp+ax+'</svg>';
  var cv=FC.coverage||{}, cov=cv.inside!=null?' On this stock\'s own history, the 3-month 80% range held the real price '+Math.round(cv.inside*100)+'% of the time ('+cv.n+' tests).':'';
  box.className='fc-body'; box.innerHTML=svg+rows+'<div class="a-read">The shaded bands are where the price lands 80% (light) and 50% (dark) of the time if it moves with '+
    (FC.source==='implied'?'the <b>'+Math.round(FC.sigma*100)+'%</b> volatility the options market implies':'its past-year volatility of <b>'+Math.round(FC.sigma*100)+'%</b>')+
    ', drifting like cash. It is a range, not a prediction of direction; big moves happen more often than this bell-shaped model assumes.'+cov+'</div>';
}
function oiMoney(v){ return v==null?'unlimited':'$'+(Math.abs(v)*100).toLocaleString(undefined,{maximumFractionDigits:0}); }
function oiRender(){ var box=document.querySelector('[data-oi] .oi-body'); if(!box||!OI) return;
  if(!OI.ok){ box.className='oi-body muted'; box.textContent=OI.error||'No option ideas right now.'; return; }
  if(!OI.ideas.length){ box.className='oi-body muted'; box.textContent='No ideas fit right now.'; return; }
  var head='<div class="a-row"><span>Expiry</span><b>'+OI.expiry+' <span class="muted">('+OI.days+' days)</span></b></div>'+
    '<div class="a-row"><span>Read</span><b>'+OI.view.charAt(0).toUpperCase()+OI.view.slice(1)+' trend · options '+
    (OI.rv&&OI.iv>OI.rv*1.1?'rich':(OI.rv&&OI.iv<OI.rv*0.9?'cheap':'fairly priced'))+' <span class="muted">(IV '+Math.round(OI.iv*100)+'% vs '+(OI.rv?Math.round(OI.rv*100)+'% realized':'n/a')+')</span></b></div>'+
    (OI.earnings_before_expiry?'<div class="a-row"><span>Note</span><b class="down">Earnings before expiry: moves can be larger</b></div>':'');
  var cards=OI.ideas.map(function(i){
    var legs=i.legs.map(function(l){ return '<span>'+(l.side==='buy'?'Buy':'Sell')+' '+(l.kind==='stock'?'100 shares':'$'+l.strike+' '+l.kind)+(l.kind==='stock'?'':' @ $'+l.price.toFixed(2))+'</span>'; }).join('');
    var net=i.net>=0?'Costs '+oiMoney(i.net):'Collects '+oiMoney(i.net);
    return '<div class="idea"><div class="idea-h"><span>'+i.name+'</span><span class="muted" style="font-weight:400">'+net+' per contract</span></div>'+
      '<div class="idea-why">'+i.why+'</div><div class="idea-legs">'+legs+'</div><div class="idea-nums">'+
      '<span>Max profit <b>'+oiMoney(i.max_profit)+'</b></span><span>Max loss <b class="down">'+oiMoney(i.max_loss)+'</b></span>'+
      '<span>Breakeven <b>'+(i.breakevens.length?i.breakevens.map(function(b){return '$'+b.toFixed(2);}).join(', '):'-')+'</b></span>'+
      '<span>Chance of profit <b>'+Math.round(i.pop*100)+'%</b></span></div></div>'; }).join('');
  box.className='oi-body'; box.innerHTML=head+cards+'<div class="a-read">Priced from the live option chain'+(OI.stale?' (last trades while the market is closed, so approximate)':'')+
    '. Per contract of 100 shares, held to expiry; chance of profit uses the implied volatility. Options can lose their full cost quickly. '+
    'Implied volatility has usually run above what followed (the variance risk premium), which is why selling premium needs rich options. Ideas, not advice.</div>';
}
(function(){
  fetch('/api/option-ideas/'+encodeURIComponent(TK)).then(function(r){return r.json();}).then(function(d){ OI=d; oiRender();
    return fetch('/api/forecast/'+encodeURIComponent(TK)); }).catch(function(){ OI={ok:false}; oiRender(); return fetch('/api/forecast/'+encodeURIComponent(TK)); })
    .then(function(r){ return r && r.json(); }).then(function(d){ if(d){ FC=d; fcRender(); } }).catch(function(){ FC={ok:false}; fcRender(); });
})();
"""
