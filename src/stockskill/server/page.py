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
.searchwrap{position:relative}
.sug{position:absolute;left:0;right:0;top:calc(100% + 4px);z-index:20;
  background:var(--surface);border:1px solid var(--border);border-radius:10px;
  overflow:hidden;box-shadow:0 8px 24px rgba(0,0,0,.18);display:none}
.sug-item{display:flex;gap:8px;align-items:baseline;padding:9px 12px;cursor:pointer}
.sug-item:hover,.sug-item.active{background:var(--surface-2)}
.sug-item b{font-variant-numeric:tabular-nums}
.sug-item .nm{flex:1;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sug-item .ex{color:var(--muted);font-size:11px}
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
.vnote{font-size:12.5px;color:var(--ink);background:var(--surface-2);
  border:1px solid var(--warn);border-radius:8px;padding:8px 10px;margin-bottom:10px}
.disclaimer{font-size:11.5px;color:var(--muted);margin-top:14px;line-height:1.5;
  border-top:1px solid var(--border);padding-top:10px}
table.methods{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:6px}
table.methods td{padding:3px 0;border-bottom:1px solid var(--border)}
table.methods td.r{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
/* market climate */
.climate{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:12px 16px;margin:14px 0}
.climate .lab{font-size:15px;font-weight:700}
.climate.good .lab{color:var(--good)} .climate.warn .lab{color:var(--warn)} .climate.crit .lab{color:var(--crit)}
.climate .notes{font-size:12.5px;color:var(--muted);margin-top:4px}
.climate .metrics{font-size:12px;margin-top:6px;font-variant-numeric:tabular-nums}
/* trade evaluator */
.evalcard{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:14px 16px;margin:16px 0}
.evalcard h2{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:0 0 10px}
.evform{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.evform input,.evform select{font-size:13px;padding:8px 10px;border-radius:9px;
  border:1px solid var(--border);background:var(--surface-2);color:var(--ink)}
.evform input{width:110px} .evform #ev-ticker{width:120px}
.evform button{font-size:13px;padding:8px 16px;border-radius:9px;border:none;
  background:var(--accent);color:#fff;font-weight:650;cursor:pointer}
.factor{display:flex;gap:8px;align-items:baseline;font-size:13px;padding:3px 0;border-bottom:1px solid var(--border)}
.factor .mk{font-weight:700;width:16px}
.factor.support .mk{color:var(--good)} .factor.against .mk{color:var(--crit)} .factor.neutral .mk{color:var(--muted)}
.factor .fn{font-weight:600;min-width:120px} .factor .fd{color:var(--muted)}
.align{margin-top:10px;padding:8px 12px;border-radius:9px;font-weight:650;font-size:13px}
.align.pos{background:var(--good);color:#fff} .align.neg{background:var(--crit);color:#fff}
.align.mid{background:var(--surface-2);border:1px solid var(--border)}
"""

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stock Analyzer</title><style>__CSS____EXTRA__</style></head>
<body><div class="wrap">
<header><h1>Stock Analyzer</h1><span class="muted">search any ticker</span></header>
<div class="searchwrap">
  <div class="search">
    <input id="q" placeholder="Company or ticker, e.g. oracle, NVDA, costco" autofocus
           autocomplete="off">
    <input id="g" style="max-width:150px;flex:0 0 auto" placeholder="growth % (auto)"
           title="Override base-case growth; blank = data-driven"
           onkeydown="if(event.key==='Enter')go()">
    <button onclick="go()">Analyze</button>
  </div>
  <div id="sug" class="sug"></div>
</div>
<div class="quick" id="quick"></div>
<div id="out"></div>

<div class="evalcard">
  <h2>🎯 Trade Evaluator</h2>
  <div class="evform">
    <input id="ev-ticker" placeholder="Ticker" autocomplete="off">
    <select id="ev-action"><option value="buy">Buy</option>
      <option value="short">Short</option><option value="sell">Sell</option></select>
    <input id="ev-price" placeholder="Entry $ (opt)">
    <input id="ev-stop" placeholder="Stop $ (opt)">
    <input id="ev-target" placeholder="Target $ (opt)">
    <button onclick="runEval()">Evaluate</button>
  </div>
  <div id="eval-out" style="margin-top:12px"></div>
</div>
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

function esc(s){return (s==null?'':String(s)).replace(/[&<>"']/g,c=>(
  {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

// Analyze one exact symbol. Returns {ok:true} or {ok:false, code}.
async function analyze(sym, g){
  const out = document.getElementById('out');
  out.innerHTML = '<div class="loader">Analyzing '+esc(sym)+' …</div>';
  let url = '/api/stock/'+encodeURIComponent(sym);
  if(g) url += '?growth='+(parseFloat(g)/100);
  try{
    const r = await fetch(url);
    const d = await r.json();
    if(!r.ok || d.error) return {ok:false};
    out.innerHTML = render(d);
    return {ok:true};
  }catch(e){ out.innerHTML='<div class="card">Request failed: '+esc(e)+'</div>'; return {ok:true}; }
}

async function go(){
  hideSug();
  const raw = document.getElementById('q').value.trim();
  if(!raw) return;
  const g = document.getElementById('g').value.trim();
  const out = document.getElementById('out');
  // 1) try as an exact ticker
  const res = await analyze(raw.toUpperCase(), g);
  if(res.ok) return;
  // 2) fall back to name search and use the best match
  out.innerHTML = '<div class="loader">Searching for “'+esc(raw)+'” …</div>';
  try{
    const s = await (await fetch('/api/search?q='+encodeURIComponent(raw))).json();
    const list = s.results||[];
    if(list.length){
      const top = list[0];
      document.getElementById('q').value = top.symbol;
      const r2 = await analyze(top.symbol, g);
      if(r2.ok){
        const note = document.createElement('div');
        note.className='muted'; note.style='font-size:12px;margin:6px 2px';
        note.textContent = 'Showing '+top.symbol+' ('+top.name+') for “'+raw+'”.';
        out.prepend(note);
      }
      return;
    }
    out.innerHTML = '<div class="card">No match for “'+esc(raw)+'”. Try a company name (e.g. “oracle”) or a ticker.</div>';
  }catch(e){ out.innerHTML = '<div class="card">Search failed: '+esc(e)+'</div>'; }
}

// ---- live suggestions ----
let sugTimer;
function hideSug(){ const s=document.getElementById('sug'); s.style.display='none'; s.innerHTML=''; }
function pick(sym){ document.getElementById('q').value=sym; hideSug(); go(); }
function renderSug(list, q){
  const s=document.getElementById('sug');
  if(!list.length){
    s.innerHTML = '<div class="sug-item" style="cursor:default"><span class="nm ex">'
      + 'No matches for “'+esc(q||'')+'”. Press Analyze to try it as a ticker.</span></div>';
    s.style.display='block';
    return;
  }
  s.innerHTML = list.map(x=>
    '<div class="sug-item" data-sym="'+esc(x.symbol)+'"><b>'+esc(x.symbol)+'</b>'
    + '<span class="nm">'+esc(x.name)+'</span><span class="ex">'+esc(x.exchange||'')+'</span></div>'
  ).join('');
  s.querySelectorAll('.sug-item').forEach(el=>el.onclick=()=>pick(el.dataset.sym));
  s.style.display='block';
}
const qEl = document.getElementById('q');
qEl.addEventListener('input', e=>{
  clearTimeout(sugTimer);
  const v = e.target.value.trim();
  if(v.length<2){ hideSug(); return; }
  sugTimer = setTimeout(async ()=>{
    try{ const d=await (await fetch('/api/search?q='+encodeURIComponent(v))).json();
      renderSug(d.results||[], v); }catch(_){ renderSug([], v); }
  }, 220);
});
qEl.addEventListener('keydown', e=>{ if(e.key==='Enter'){ hideSug(); go(); }
  else if(e.key==='Escape'){ hideSug(); } });
document.addEventListener('click', e=>{ if(!e.target.closest('.searchwrap')) hideSug(); });

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
   + '<div class="card"><h2>Valuation - bear / base / bull fair value</h2>'
     + (v.note ? '<div class="vnote">'+esc(v.note)+'</div>' : '')
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

// ---- trade evaluator ----
async function runEval(){
  const t = document.getElementById('ev-ticker').value.trim().toUpperCase();
  if(!t){ document.getElementById('ev-ticker').focus(); return; }
  const out = document.getElementById('eval-out');
  const params = new URLSearchParams({action: document.getElementById('ev-action').value});
  for(const k of ['price','stop','target']){
    const v = document.getElementById('ev-'+k).value.trim();
    if(v) params.set(k, v);
  }
  out.innerHTML = '<div class="loader">Evaluating '+esc(t)+' …</div>';
  try{
    const r = await fetch('/api/evaluate/'+encodeURIComponent(t)+'?'+params.toString());
    const d = await r.json();
    if(d.error){ out.innerHTML='<div class="muted">'+esc(d.error)+'</div>'; return; }
    out.innerHTML = renderEval(d);
  }catch(e){ out.innerHTML='<div class="muted">Failed: '+esc(e)+'</div>'; }
}
function renderEval(d){
  const mark = {support:'✓', against:'✗', neutral:'·'};
  const facs = d.factors.map(f=>
    '<div class="factor '+f.stance+'"><span class="mk">'+mark[f.stance]+'</span>'
    + '<span class="fn">'+esc(f.name)+'</span><span class="fd">'+esc(f.detail)+'</span></div>').join('');
  const net = d.n_support - d.n_against;
  const acls = net>=2?'pos':(net<=-2?'neg':'mid');
  const rr = d.rr!=null ? ' · R:R '+d.rr.toFixed(1)+':1' : '';
  return '<div style="font-weight:700;margin-bottom:6px">'+esc(d.action)+' '+esc(d.ticker)
    + ' @ '+money(d.price)+'</div>'+facs
    + '<div class="align '+acls+'">Support '+d.n_support+' · Against '+d.n_against+rr
    + ' - '+esc(d.alignment)+'</div>'
    + '<div class="muted" style="font-size:11px;margin-top:6px">Analysis, not advice - the decision is yours.</div>';
}
document.getElementById('ev-ticker').addEventListener('keydown', e=>{ if(e.key==='Enter') runEval(); });
</script>
</body></html>"""


def analyzer_html() -> str:
    return PAGE.replace("__CSS__", _CSS).replace("__EXTRA__", _EXTRA_CSS)
