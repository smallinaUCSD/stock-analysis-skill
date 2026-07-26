"""HTML for the interactive analyzer page (served by the Flask app).

Search any ticker -> client-side fetch of /api/stock/<t> -> rendered detail:
price, valuation signal (vs. our DCF fair value), bear/base/bull, reported
analyst consensus, and an options snapshot. No buy/sell/hold instruction is
emitted -- the page shows analysis and reported data; the decision is the user's.
"""

from __future__ import annotations

from ..dashboard.render import _CSS

_EXTRA_CSS = """
.search{display:flex;gap:8px;margin:14px 0 4px}
.search input{flex:1;font-size:15px;padding:10px 12px;border-radius:10px;
  border:1px solid var(--border);background:var(--surface);color:var(--ink)}
.search button{font-size:14px;padding:10px 16px;border-radius:10px;border:none;
  background:var(--accent);color:#fff;font-weight:650;cursor:pointer}
.quick{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.quick button{font-size:12px;padding:4px 10px;border-radius:999px;cursor:pointer;
  background:var(--surface-2);border:1px solid var(--border);color:var(--ink)}
.signal{display:inline-block;font-weight:750;font-size:13px;padding:5px 12px;
  border-radius:999px;margin-left:8px}
.signal.good{background:var(--good);color:#fff}
.signal.warn{background:var(--warn);color:#111}
.signal.crit{background:var(--crit);color:#fff}
.signal.mid{background:var(--surface-2);color:var(--ink);border:1px solid var(--border)}
.big{font-size:28px;font-weight:720;font-variant-numeric:tabular-nums}
.kv{display:grid;grid-template-columns:1fr auto;gap:6px 14px;font-size:13px}
.kv .k{color:var(--muted)} .kv .v{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
.scenario{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0}
.scn{background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:10px}
.scn .lab{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.scn .val{font-size:18px;font-weight:680;font-variant-numeric:tabular-nums;margin-top:3px}
.scn.bear .val{color:var(--down)} .scn.bull .val{color:var(--up)}
.muted{color:var(--muted)} .up{color:var(--up)} .down{color:var(--down)}
.hidden{display:none}
.loader{color:var(--muted);font-size:13px;padding:14px 0}
.disclaimer{font-size:11.5px;color:var(--muted);margin-top:14px;line-height:1.5;
  border-top:1px solid var(--border);padding-top:10px}
table.methods{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:6px}
table.methods td{padding:3px 0;border-bottom:1px solid var(--border)}
table.methods td.r{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
"""

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stock Analyzer</title><style>__CSS____EXTRA__</style></head>
<body><div class="wrap">
<header><h1>Stock Analyzer</h1><span class="muted">search any ticker</span></header>
<div class="search">
  <input id="q" placeholder="Ticker, e.g. NVDA, AAPL, COST" autofocus
         onkeydown="if(event.key==='Enter')go()">
  <input id="g" style="max-width:150px;flex:0 0 auto" placeholder="growth % (auto)"
         title="Override base-case growth; blank = data-driven"
         onkeydown="if(event.key==='Enter')go()">
  <button onclick="go()">Analyze</button>
</div>
<div class="quick" id="quick"></div>
<div id="out"></div>
<div class="disclaimer">Analysis, not investment advice. The valuation signal is price vs.
this tool's DCF-based fair value (assumptions shown); bear/base/bull vary growth and discount
rate; analyst consensus is reported third-party data. Options figures are informational.
The buy / sell / hold decision is yours. Free data (yfinance) may be delayed or incomplete.</div>
<p class="muted" style="font-size:12px;margin-top:16px">
Market pulse &amp; your portfolio: run <code>stockskill dashboard --open</code>.</p>
</div>
<script>
const QUICK = ["NVDA","AAPL","META","MSFT","COST","PLTR"];
const qd = document.getElementById('quick');
QUICK.forEach(t=>{const b=document.createElement('button');b.textContent=t;
  b.onclick=()=>{document.getElementById('q').value=t;go();};qd.appendChild(b);});

function pct(x){return (x==null)?'n/a':(x*100).toFixed(1)+'%';}
function pctS(x){return (x==null)?'n/a':((x>=0?'+':'')+(x*100).toFixed(1)+'%');}
function money(x){return (x==null)?'n/a':'$'+Number(x).toLocaleString(undefined,{maximumFractionDigits:2});}
function num(x,d){return (x==null)?'n/a':Number(x).toFixed(d==null?2:d);}

function signalClass(sig){
  if(!sig) return 'mid';
  if(sig.includes('discount')||sig.includes('undervalued')) return 'good';
  if(sig.includes('perfection')) return 'crit';
  if(sig.includes('expensive')) return 'warn';
  return 'mid';
}

async function go(){
  const t = document.getElementById('q').value.trim().toUpperCase();
  if(!t) return;
  const g = document.getElementById('g').value.trim();
  let url = '/api/stock/'+encodeURIComponent(t);
  if(g) url += '?growth='+(parseFloat(g)/100);
  const out = document.getElementById('out');
  out.innerHTML = '<div class="loader">Analyzing '+t+' …</div>';
  try{
    const r = await fetch(url);
    const d = await r.json();
    if(d.error){ out.innerHTML = '<div class="card">Could not analyze '+t+': '+d.error+'</div>'; return; }
    out.innerHTML = render(d);
  }catch(e){ out.innerHTML = '<div class="card">Request failed: '+e+'</div>'; }
}

function render(d){
  const v = d.valuation, c = d.consensus, o = d.options;
  const sig = v.signal||'';
  const methods = (v.methods||[]).map(m=>
    '<tr><td>'+m.method+'</td><td class="r">'+money(m.fair_value)+'</td><td class="muted">'+(m.note||'')+'</td></tr>').join('');
  const opt = (!o||o.available===false)
    ? '<div class="muted" style="font-size:12.5px">Options: '+((o&&o.note)||'n/a')+'</div>'
    : '<div class="kv">'
      + '<div class="k">Nearest expiry</div><div class="v">'+(o.expiry||'n/a')+'</div>'
      + '<div class="k">ATM call ($'+num(o.atm_call?.strike,0)+')</div><div class="v">'+money(o.atm_call?.last_price)+' · IV '+pct(o.atm_call?.implied_vol)+'</div>'
      + '<div class="k">ATM put ($'+num(o.atm_put?.strike,0)+')</div><div class="v">'+money(o.atm_put?.last_price)+' · IV '+pct(o.atm_put?.implied_vol)+'</div>'
      + '<div class="k">Put−call IV skew</div><div class="v">'+pctS(o.put_call_iv_skew)+'</div></div>';

  return '<div class="grid">'
   + '<div class="card wide"><h2 style="text-transform:none;font-size:15px;color:var(--ink)">'
     + d.name+' <span class="muted">'+d.ticker+'</span>'
     + '<span class="signal '+signalClass(sig)+'">'+sig+'</span></h2>'
     + '<div class="big">'+money(d.price)+'</div>'
     + '<div class="muted" style="font-size:12px">as of '+d.as_of+' · beta '+num(d.beta)+' · div yield '+pct(d.dividend_yield)+'</div>'
   + '</div>'
   + '<div class="card"><h2>Valuation — bear / base / bull fair value</h2>'
     + '<div class="scenario">'
     + '<div class="scn bear"><div class="lab">Bear</div><div class="val">'+money(v.bear)+'</div></div>'
     + '<div class="scn"><div class="lab">Base</div><div class="val">'+money(v.base)+'</div></div>'
     + '<div class="scn bull"><div class="lab">Bull</div><div class="val">'+money(v.bull)+'</div></div>'
     + '</div>'
     + '<div class="kv">'
     + '<div class="k">Price vs base fair value</div><div class="v '+(v.margin_of_safety>=0?'up':'down')+'">'+pctS(v.margin_of_safety)+'</div>'
     + '<div class="k">Reverse-DCF: implied growth in price</div><div class="v">'+pct(v.implied_market_growth)+'</div>'
     + '<div class="k">Discount rate · base growth</div><div class="v">'+pct(v.discount_rate)+' · '+pct(v.assumptions?.stage1_growth)+'</div>'
     + '<div class="k muted" style="font-size:11px">growth source</div><div class="v muted" style="font-size:11px;font-weight:400">'+(v.assumptions?.growth_source||'')+'</div>'
     + '</div>'
     + '<table class="methods">'+methods+'</table></div>'
   + '<div class="card"><h2>Analyst consensus (reported) &amp; options</h2>'
     + '<div class="kv">'
     + '<div class="k">Consensus</div><div class="v">'+(c.reco||'n/a')+(c.mean?(' ('+num(c.mean,1)+'/5)'):'')+'</div>'
     + '<div class="k">Analysts</div><div class="v">'+(c.count??'n/a')+'</div>'
     + '<div class="k">Avg price target</div><div class="v">'+money(c.target_mean)+'</div>'
     + '<div class="k">Target vs price</div><div class="v '+(c.target_vs_price>=0?'up':'down')+'">'+pctS(c.target_vs_price)+'</div>'
     + '</div><div style="height:8px"></div>'+opt+'</div>'
   + '</div>';
}
</script>
</body></html>"""


def analyzer_html() -> str:
    return PAGE.replace("__CSS__", _CSS).replace("__EXTRA__", _EXTRA_CSS)
