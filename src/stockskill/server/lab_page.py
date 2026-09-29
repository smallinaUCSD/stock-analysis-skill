"""Portfolio lab: ideas for your account (stocks to add, politicians and funds
to follow), portfolio optimization (Markowitz efficient frontier and
Black-Litterman) and Brownian-motion price paths. Data from /api/lab/*."""

from __future__ import annotations

from ..dashboard.render import _CSS, _THEME_BOOT, icon
from ..dashboard.suggest import SUGGEST_CSS, SUGGEST_JS
from .charts import DONUT_CSS, DONUT_JS


def lab_html() -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Portfolio lab</title>" + _THEME_BOOT + "<style>" + _CSS + SUGGEST_CSS + DONUT_CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Portfolio lab</h1><span class=\"sub\" style=\"margin:0\">Ideas, optimization and simulations "
            "from your watchlist</span><button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" "
            "aria-label=\"Close\">" + icon("x", 17) + "</button></header>"
            "<nav class=\"seg lb-tabs\" id=\"lb-tabs\"><button data-v=\"ideas\" class=\"on\">Ideas for you</button>"
            "<button data-v=\"opt\">Optimize</button><button data-v=\"sim\">Simulate</button></nav>"
            "<section id=\"v-ideas\" class=\"lb-v\"><div class=\"lb-bar\"><span class=\"seg\" id=\"id-style\">"
            "<button data-s=\"similar\" class=\"on\">More like yours</button><button data-s=\"diversify\">Diversify</button></span>"
            "<span class=\"muted small\">Based on the stocks you watch, what tracked funds hold and what politicians buy.</span></div>"
            "<div id=\"id-stocks\" class=\"lb-grid muted\">Loading…</div>"
            "<div class=\"lb-two\"><div><h2>Funds to follow</h2><div id=\"id-funds\" class=\"lb-list muted\">Loading…</div></div>"
            "<div><h2>Politicians to follow</h2><div id=\"id-pols\" class=\"lb-list muted\">Loading…</div></div></div></section>"
            "<section id=\"v-opt\" class=\"lb-v\" hidden><div class=\"lb-bar\"><div id=\"op-chips\" class=\"lb-chips\"></div>"
            "<span class=\"lb-add\"><input id=\"op-add\" placeholder=\"Add a stock\" autocomplete=\"off\"></span>"
            "<span class=\"lb-cap\">Most in one stock <span class=\"seg\" id=\"op-cap\"><button data-c=\"0.1\">10%</button>"
            "<button data-c=\"0.2\">20%</button><button data-c=\"0.25\" class=\"on\">25%</button><button data-c=\"0.35\">35%</button>"
            "<button data-c=\"1\">No limit</button></span></span></div>"
            "<div id=\"op-out\" class=\"muted\">Loading…</div></section>"
            "<section id=\"v-sim\" class=\"lb-v\" hidden><div class=\"lb-bar\"><span class=\"lb-add\"><input id=\"sm-t\" "
            "placeholder=\"A stock, e.g. NVDA\" autocomplete=\"off\"></span><button class=\"tbtn\" id=\"sm-port\">Your best "
            "risk-adjusted mix</button><span class=\"seg\" id=\"sm-days\"><button data-d=\"63\">3 months</button><button data-d=\"126\">6 months</button>"
            "<button data-d=\"252\" class=\"on\">1 year</button><button data-d=\"504\">2 years</button></span></div>"
            "<div id=\"sm-out\" class=\"muted\">Pick a stock, or simulate your optimized mix.</div></section>"
            "<p class=\"lb-note\">Research, not advice. Optimization uses the last three years of daily prices; past "
            "returns are a noisy guide to future ones, which is why the covariance is shrunk and each stock is capped. "
            "Black-Litterman starts from what the market's own weights imply and tilts toward analysts' 12-month price "
            "targets, more where more analysts cover the stock. Brownian-motion paths assume independent, normally "
            "distributed daily moves, so real crashes are more common than they show.</p>"
            "</div><script>" + SUGGEST_JS + DONUT_JS + _JS + "</script></body></html>")


_EXTRA_CSS = """
.lb-tabs{margin:2px 0 14px}
.lb-bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:14px}
.lb-v h2{font-family:var(--font-display);font-weight:500;font-size:24px;margin:22px 0 10px}
.lb-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.lb-card{border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:14px 16px;display:flex;flex-direction:column;gap:6px}
.lb-card .tk{font-weight:500;font-size:17px} .lb-card .nm{color:var(--muted);font-size:13px}
.lb-card ul{margin:4px 0 6px;padding-left:18px;font-size:13.5px;line-height:1.5}
.lb-card .act{display:flex;gap:8px;margin-top:auto}
.lb-btn{height:32px;padding:0 12px;border-radius:16px;border:1px solid var(--border-strong);background:var(--bg);color:var(--ink);font:13px var(--font);cursor:pointer}
.lb-btn.on{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.lb-two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.lb-list .row{display:flex;gap:10px;align-items:center;justify-content:space-between;border-top:1px solid var(--border);padding:10px 0}
.lb-list .row:first-child{border-top:none} .lb-list small{display:block;color:var(--muted);font-size:13px}
.lb-chips{display:flex;flex-wrap:wrap;gap:6px}
.lb-chip{display:inline-flex;align-items:center;gap:6px;height:30px;padding:0 6px 0 12px;border-radius:15px;border:1px solid var(--border);background:var(--surface);font-size:13px}
.lb-chip button{border:none;background:none;color:var(--muted);cursor:pointer;font-size:15px}
.lb-add input{height:34px;border:1px solid var(--border-strong);border-radius:var(--r);background:var(--bg);color:var(--ink);padding:0 10px;font:14px var(--font);width:190px}
.lb-cap{display:inline-flex;align-items:center;gap:8px;color:var(--muted);font-size:13px}
.lb-row2{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:14px;align-items:start}
.lb-box{border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:14px 16px;min-width:0}
.lb-box h3{font-size:12px;letter-spacing:1.3px;text-transform:uppercase;color:var(--muted);font-weight:500;margin:0 0 8px}
.lb-box svg{width:100%;height:auto;display:block}
.dn svg{width:150px!important;height:150px!important}
.lb-v .seg,.lb-tabs{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden}
.lb-v .seg button,.lb-tabs button{height:34px;padding:0 14px;border:none;background:var(--surface);color:var(--muted);font:500 13px var(--font);cursor:pointer}
.lb-v .seg button.on,.lb-tabs button.on{background:var(--surface-3);color:var(--ink)}
.lb-box svg text{fill:var(--muted);font-size:11px;font-family:var(--font)}
.lb-pf{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-bottom:12px}
.lb-pf button{text-align:left;border:1px solid var(--border);border-radius:10px;background:var(--surface);padding:10px 12px;cursor:pointer;color:var(--ink);font:13px var(--font)}
.lb-pf button.on{border-color:var(--accent)} .lb-pf b{display:block;font-weight:500;font-size:14px}
.lb-t{width:100%;border-collapse:collapse;font-size:13.5px;font-variant-numeric:tabular-nums}
.lb-t th,.lb-t td{padding:7px 8px;border-top:1px solid var(--border);text-align:right;white-space:nowrap}
.lb-t th{border-top:none;color:var(--muted);font-weight:500;font-size:12px}
.lb-t td:first-child,.lb-t th:first-child{text-align:left}
.lb-scroll{overflow-x:auto}
.lb-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:12px}
.lb-kpis div{border:1px solid var(--border);border-radius:10px;background:var(--surface);padding:10px 14px}
.lb-kpis span{display:block;font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted)}
.lb-kpis b{font-size:22px;font-weight:500}
.lb-note{font-size:13px;color:var(--muted);line-height:1.55;margin-top:18px}
.up{color:var(--up)} .dn{color:var(--down)}
@media (max-width:860px){.lb-row2,.lb-two{grid-template-columns:1fr}}
"""

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  var here=location.href, back=false, nav=window.navigation;
  if(nav && nav.currentEntry && typeof nav.entries==='function'){
    var i=nav.currentEntry.index, en=nav.entries(); back=i>0 && !!en[i-1] && en[i-1].url.indexOf(location.origin+'/')===0;
  } else { var r=document.referrer||''; back=history.length>1 && r.indexOf(location.origin+'/')===0 && r!==here; }
  function leave(){ try{ if(window.opener && !window.opener.closed) window.opener.focus(); }catch(_){}
    window.close(); setTimeout(function(){ location.href='/'; }, 250); }
  if(back){ history.back(); setTimeout(function(){ if(location.href===here) leave(); }, 450); } else leave();
  return false; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
function pct(x,d){ return x==null?'-':(x*100).toFixed(d==null?1:d)+'%'; }
function spct(x){ return x==null?'-':'<span class="'+(x>=0?'up':'dn')+'">'+(x>=0?'+':'')+(x*100).toFixed(1)+'%</span>'; }
function post(u,b){ return fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})}).then(function(r){return r.json();}); }
function big(v){ if(v==null) return ''; var a=Math.abs(v); return a>=1e12?'$'+(v/1e12).toFixed(1)+'T':a>=1e9?'$'+(v/1e9).toFixed(0)+'B':'$'+(v/1e6).toFixed(0)+'M'; }
var VIEW='ideas', STYLE='similar', TKS=null, CAP=0.25, OPT=null, PICK='max_sharpe', SIMDAYS=252, SIMT='';
function show(v){ VIEW=v; ['ideas','opt','sim'].forEach(function(k){ document.getElementById('v-'+k).hidden=k!==v; });
  document.querySelectorAll('#lb-tabs button').forEach(function(b){ b.classList.toggle('on',b.dataset.v===v); });
  try{ history.replaceState(null,'','/lab#'+v); }catch(_){}
  if(v==='opt' && !OPT) optimize(); }
document.getElementById('lb-tabs').onclick=function(e){ var b=e.target.closest('button'); if(b) show(b.dataset.v); };
function segPick(id,attr,cb){ document.getElementById(id).onclick=function(e){ var b=e.target.closest('button'); if(!b) return;
  this.querySelectorAll('button').forEach(function(x){ x.classList.toggle('on',x===b); }); cb(b.dataset[attr]); }; }

// ---- ideas -------------------------------------------------------------------------
function ideas(){ var st=document.getElementById('id-stocks'); st.className='lb-grid muted'; st.textContent='Finding ideas…';
  fetch('/api/lab/ideas?style='+STYLE).then(function(r){return r.json();}).then(function(d){
    if(d.warming){ st.textContent='Gathering the whole market (the first time takes about a minute)…'; setTimeout(ideas,8000); return; }
    if(!d.ok){ st.textContent=d.error||'Unavailable.'; return; }
    st.className='lb-grid';
    st.innerHTML=(d.stocks||[]).map(function(x){ return '<div class="lb-card"><div><a class="tk" href="/analysis/'+encodeURIComponent(x.ticker)+'">'+esc(x.ticker)+'</a> '+
      '<span class="nm">'+esc(x.name||'')+'</span></div><span class="nm">'+esc([x.sector,x.industry].filter(Boolean).join(' · '))+(x.mcap?' · '+big(x.mcap):'')+'</span>'+
      '<ul>'+x.reasons.map(function(r){ return '<li>'+esc(r)+'</li>'; }).join('')+'</ul>'+
      '<div class="act"><button class="lb-btn" data-add="'+esc(x.ticker)+'">Add to watchlist</button>'+
      '<a class="lb-btn" style="display:inline-flex;align-items:center;text-decoration:none" href="/analysis/'+encodeURIComponent(x.ticker)+'">Open</a></div></div>'; }).join('')||'<p class="muted">No ideas yet: add a few stocks to your watchlist.</p>';
    var f=document.getElementById('id-funds'); f.className='lb-list';
    f.innerHTML=(d.funds||[]).map(function(x){ return '<div class="row"><span><a href="/fund/'+x.cik+'"><b>'+esc(x.fund)+'</b></a> <span class="muted">'+esc(x.manager||'')+'</span>'+
      '<small>'+esc(x.reason)+'</small></span><button class="lb-btn" data-follow="fund:'+x.cik+'" data-name="'+esc(x.fund)+'">Follow</button></div>'; }).join('')||'<p class="muted small">None of the tracked funds hold your stocks.</p>';
    var p=document.getElementById('id-pols'); p.className='lb-list';
    p.innerHTML=(d.politicians||[]).map(function(x){ return '<div class="row"><span><a href="/politician/'+encodeURIComponent(x.id)+'"><b>'+esc(x.name)+'</b></a>'+
      '<small>'+esc(x.reason)+'</small></span><button class="lb-btn" data-follow="'+esc(x.id)+'" data-name="'+esc(x.name)+'">Follow</button></div>'; }).join('')||'<p class="muted small">No politician has traded your stocks this year.</p>';
  }).catch(function(){ st.textContent='Ideas are unavailable right now.'; }); }
segPick('id-style','s',function(s){ STYLE=s; ideas(); });
document.getElementById('v-ideas').addEventListener('click',function(e){
  var a=e.target.closest('[data-add]'), f=e.target.closest('[data-follow]');
  if(a){ post('/api/me/watchlist',{add:[a.dataset.add]}).then(function(d){ a.textContent=d.ok?'Added':'Couldn’t add'; a.classList.add('on'); a.disabled=true; }); }
  if(f){ post('/api/me/follows',{add:[{pid:f.dataset.follow,name:f.dataset.name}]}).then(function(d){ f.textContent=d.ok?'Following':'Couldn’t follow'; f.classList.add('on'); f.disabled=true; }); } });

// ---- optimize -----------------------------------------------------------------------
var PF=[['max_sharpe','Best risk-adjusted','Markowitz: highest return per unit of risk'],['min_var','Lowest risk','Markowitz: the least volatile mix'],
  ['black_litterman','Black-Litterman','Market weights tilted to analysts’ views'],['market','Market weights','By company size'],['equal','Equal weights','The same in each']];
function chips(){ document.getElementById('op-chips').innerHTML=(TKS||[]).map(function(t){ return '<span class="lb-chip">'+esc(t)+'<button data-rm="'+esc(t)+'" aria-label="Remove '+esc(t)+'">×</button></span>'; }).join(''); }
document.getElementById('op-chips').onclick=function(e){ var b=e.target.closest('[data-rm]'); if(!b) return; TKS=TKS.filter(function(t){ return t!==b.dataset.rm; }); chips(); optimize(); };
attachSuggest(document.getElementById('op-add'),{kinds:'stocks',onPick:function(it,i){ i.value=''; if(TKS.indexOf(it.symbol)<0){ TKS.push(it.symbol); chips(); optimize(); } }});
document.getElementById('op-add').addEventListener('keydown',function(e){ if(e.key!=='Enter') return; var t=this.value.trim().toUpperCase(); this.value='';
  if(t && TKS.indexOf(t)<0){ TKS.push(t); chips(); optimize(); } });
segPick('op-cap','c',function(c){ CAP=+c; optimize(); });
function optimize(){ var o=document.getElementById('op-out'); o.className='muted'; o.textContent='Optimizing…';
  fetch('/api/lab/optimize?cap='+CAP+(TKS?'&t='+encodeURIComponent(TKS.join(',')):'')).then(function(r){return r.json();}).then(function(d){
    if(!d.ok){ o.textContent=d.error; return; } OPT=d; if(!TKS){ TKS=d.tickers.slice(); chips(); } drawOpt(); })
    .catch(function(){ o.textContent='Optimization is unavailable right now.'; }); }
function frontierSvg(d){ var W=640,H=360,L=54,B=34,T=14,R=16, pts=d.rows.map(function(r){ return [r.vol,r.ret,r.ticker]; });
  var P=d.portfolios; pts=d.rows.map(function(r){ return [r.vol,r.exp,r.ticker]; });
  var all=pts.map(function(p){ return [p[0],p[1]]; }).concat(d.frontier.map(function(p){ return [p.vol,p.ret]; }))
    .concat(Object.keys(P).map(function(k){ return [P[k].vol,P[k].ret]; }));
  var x0=0, x1=Math.max.apply(null,all.map(function(p){return p[0];}))*1.08, y0=Math.min(0,Math.min.apply(null,all.map(function(p){return p[1];}))), y1=Math.max.apply(null,all.map(function(p){return p[1];}))*1.1;
  var X=function(v){ return L+(v-x0)/(x1-x0)*(W-L-R); }, Y=function(v){ return T+(1-(v-y0)/(y1-y0))*(H-T-B); };
  var s='<svg viewBox="0 0 '+W+' '+H+'">';
  for(var g=0;g<=4;g++){ var yv=y0+(y1-y0)*g/4, xv=x0+(x1-x0)*g/4;
    s+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+Y(yv)+'" y2="'+Y(yv)+'" stroke="var(--border)"/><text x="'+(L-6)+'" y="'+(Y(yv)+4)+'" text-anchor="end">'+pct(yv,0)+'</text>'+
      '<text x="'+X(xv)+'" y="'+(H-14)+'" text-anchor="middle">'+pct(xv,0)+'</text>'; }
  s+='<text x="'+((W+L)/2)+'" y="'+(H-1)+'" text-anchor="middle">Risk (annual volatility)</text>'+
    '<text transform="translate(12 '+((H-B+T)/2)+') rotate(-90)" text-anchor="middle">Expected return</text>';
  s+='<polyline fill="none" stroke="var(--accent)" stroke-width="2.2" points="'+d.frontier.map(function(p){ return X(p.vol).toFixed(1)+','+Y(p.ret).toFixed(1); }).join(' ')+'"/>';
  pts.forEach(function(p){ s+='<circle cx="'+X(p[0])+'" cy="'+Y(p[1])+'" r="3.5" fill="var(--muted)"/><text x="'+(X(p[0])+5)+'" y="'+(Y(p[1])-4)+'">'+esc(p[2])+'</text>'; });
  var mk={max_sharpe:'var(--up)',min_var:'#4f86d9',black_litterman:'#a45fd0',market:'#c99a2e',equal:'var(--ink)'};
  Object.keys(P).forEach(function(k){ s+='<circle cx="'+X(P[k].vol)+'" cy="'+Y(P[k].ret)+'" r="'+(k===PICK?8:6)+'" fill="'+mk[k]+'" stroke="var(--bg)" stroke-width="2"><title>'+k+'</title></circle>'; });
  return s+'</svg>'; }
function drawOpt(){ var d=OPT, o=document.getElementById('op-out'); o.className='';
  var P=d.portfolios, cur=P[PICK];
  var h='<div class="lb-pf">'+PF.map(function(p){ var x=P[p[0]]; return '<button data-pf="'+p[0]+'" class="'+(p[0]===PICK?'on':'')+'"><b>'+p[1]+'</b>'+
    'return '+pct(x.ret)+' · risk '+pct(x.vol)+(x.sharpe!=null?' · Sharpe '+x.sharpe.toFixed(2):'')+'<br><span class="muted">'+p[2]+'</span></button>'; }).join('')+'</div>'+
    '<div class="lb-row2"><div class="lb-box"><h3>Efficient frontier ('+d.years+' years of prices)</h3>'+frontierSvg(d)+
    '<p class="muted small" style="margin:6px 0 0">Each gray dot is one stock; the orange line is the best return available at each level of risk. '+
    'Colored dots are the mixes above.</p></div><div class="dn" id="op-donut"></div></div>'+
    '<div class="lb-box" style="margin-top:14px"><h3>Weights and expected returns</h3><div class="lb-scroll"><table class="lb-t"><thead><tr><th>Stock</th>'+
    '<th>Past return</th><th>Expected (blended)</th><th>Risk</th><th>Market-implied</th><th>Analysts’ view</th><th>Black-Litterman</th>'+
    PF.map(function(p){ return '<th>'+p[1]+'</th>'; }).join('')+'</tr></thead><tbody>'+
    d.rows.map(function(r){ return '<tr><td><a href="/analysis/'+encodeURIComponent(r.ticker)+'">'+esc(r.ticker)+'</a></td><td>'+spct(r.ret)+'</td><td>'+pct(r.exp)+'</td><td>'+pct(r.vol)+'</td><td>'+pct(r.pi)+'</td>'+
      '<td>'+(r.view==null?'<span class="muted">none</span>':spct(r.view)+' <span class="muted">('+Math.round(r.view_conf*100)+'%)</span>')+'</td><td>'+pct(r.posterior)+'</td>'+
      PF.map(function(p){ var w=r['w_'+p[0]]; return '<td>'+(w>=0.0005?pct(w):'<span class="muted">0</span>')+'</td>'; }).join('')+'</tr>'; }).join('')+
    '</tbody></table></div>'+(d.skipped&&d.skipped.length?'<p class="muted small">Left out (not enough shared history): '+esc(d.skipped.join(', '))+'</p>':'')+
    '<p class="muted small" style="margin:6px 0 0">Markowitz uses expected returns blended halfway between each stock\u2019s past return and the market-implied one (capped at \u221230% to +60%), because raw past returns chase recent winners. Risk-free rate '+pct(d.rf)+'. Most in one stock: '+(d.cap>=1?'no limit':pct(d.cap,0))+'. '+
    (d.bl_views?d.bl_views+' stocks have analyst targets to tilt toward.':'No analyst targets found, so Black-Litterman equals market weights.')+'</p></div>';
  o.innerHTML=h;
  var items=d.rows.map(function(r){ return {name:r.ticker,value:r['w_'+PICK]}; }).sort(function(a,b){ return b.value-a.value; });
  donut(document.getElementById('op-donut'), items, {title:(PF.filter(function(p){ return p[0]===PICK; })[0]||[])[1], center:items.filter(function(x){ return x.value>=0.0005; }).length, sub:'stocks'});
  o.querySelectorAll('[data-pf]').forEach(function(b){ b.onclick=function(){ PICK=b.dataset.pf; drawOpt(); }; }); }

// ---- simulate --------------------------------------------------------------------
attachSuggest(document.getElementById('sm-t'),{kinds:'stocks',onPick:function(it,i){ i.value=it.symbol; SIMT=it.symbol; simulate(); }});
document.getElementById('sm-t').addEventListener('keydown',function(e){ if(e.key==='Enter'){ SIMT=this.value.trim().toUpperCase(); if(SIMT) simulate(); } });
document.getElementById('sm-port').onclick=function(){ SIMT=''; if(OPT) simulate(); else { optimize(); var t=setInterval(function(){ if(OPT){ clearInterval(t); simulate(); } },400); } };
segPick('sm-days','d',function(d){ SIMDAYS=+d; if(SIMT||OPT) simulate(); });
function simulate(){ var o=document.getElementById('sm-out'); o.className='muted'; o.textContent='Simulating 4,000 paths…';
  var u='/api/lab/simulate?days='+SIMDAYS+(SIMT?'&t='+encodeURIComponent(SIMT):'&t='+encodeURIComponent(OPT.tickers.join(','))+'&w='+OPT.portfolios[PICK].w.join(','));
  fetch(u).then(function(r){return r.json();}).then(function(d){ if(!d.ok){ o.textContent=d.error; return; } drawSim(d); })
    .catch(function(){ o.textContent='Simulation unavailable right now.'; }); }
function drawSim(d){ var o=document.getElementById('sm-out'); o.className='';
  var b=d.bands, W=900,H=360,L=64,B=28,T=12,R=14, all=[].concat(b.p5,b.p95), n=d.t.length;
  d.samples.forEach(function(p){ all=all.concat(p); });
  var lo=Math.min.apply(null,all), hi=Math.max.apply(null,all), X=function(i){ return L+i/(n-1)*(W-L-R); }, Y=function(v){ return T+(1-(v-lo)/(hi-lo))*(H-T-B); };
  function area(a,c){ return a.map(function(v,i){ return X(i).toFixed(1)+','+Y(v).toFixed(1); }).join(' ')+' '+c.map(function(v,i){ return X(n-1-i).toFixed(1)+','+Y(c[n-1-i]).toFixed(1); }).join(' '); }
  var money=function(v){ return d.kind==='portfolio'?'$'+Math.round(v).toLocaleString():'$'+v.toFixed(2); };
  var s='<svg viewBox="0 0 '+W+' '+H+'">';
  for(var g=0;g<=4;g++){ var yv=lo+(hi-lo)*g/4; s+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+Y(yv)+'" y2="'+Y(yv)+'" stroke="var(--border)"/><text x="'+(L-6)+'" y="'+(Y(yv)+4)+'" text-anchor="end">'+money(yv)+'</text>'; }
  s+='<polygon points="'+area(b.p5,b.p95)+'" fill="var(--accent)" opacity="0.13"/><polygon points="'+area(b.p25,b.p75)+'" fill="var(--accent)" opacity="0.22"/>';
  d.samples.forEach(function(p){ s+='<polyline fill="none" stroke="var(--muted)" stroke-width="0.8" opacity="0.55" points="'+p.map(function(v,i){ return X(i).toFixed(1)+','+Y(v).toFixed(1); }).join(' ')+'"/>'; });
  s+='<polyline fill="none" stroke="var(--accent)" stroke-width="2.2" points="'+b.p50.map(function(v,i){ return X(i).toFixed(1)+','+Y(v).toFixed(1); }).join(' ')+'"/>';
  s+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+Y(d.start)+'" y2="'+Y(d.start)+'" stroke="var(--ink)" stroke-dasharray="4 4" opacity="0.5"/>';
  s+='<text x="'+L+'" y="'+(H-8)+'">today</text><text x="'+(W-R)+'" y="'+(H-8)+'" text-anchor="end">'+Math.round(d.days/21)+' months</text></svg>';
  var who=d.kind==='portfolio'?'Your '+(PF.filter(function(p){ return p[0]===PICK; })[0]||[])[1].toLowerCase()+' mix, $10,000':esc(d.ticker);
  o.innerHTML='<div class="lb-kpis"><div><span>Chance it ends higher</span><b>'+Math.round(d.prob_up*100)+'%</b></div>'+
    '<div><span>Middle outcome</span><b>'+money(b.p50[n-1])+'</b></div><div><span>Likely range (5% to 95%)</span><b>'+money(d.p5_end)+' to '+money(d.p95_end)+'</b></div>'+
    (d.vol!=null?'<div><span>Fitted drift, volatility</span><b>'+pct(d.drift)+', '+pct(d.vol)+'</b></div>':'')+'</div>'+
    '<div class="lb-box"><h3>'+who+': 4,000 Brownian-motion paths</h3>'+s+'<p class="muted small" style="margin:6px 0 0">Shaded: the middle 50% and 90% of paths; '+
    'the line is the median; thin lines are a few sample paths.</p></div>'; }

var _qt=new URLSearchParams(location.search).get('t');                 // from a stock page: simulate it straight away
var h=(location.hash||'').slice(1); if(['ideas','opt','sim'].indexOf(h)>=0) show(h);
if(h==='sim' && _qt && /^[A-Za-z0-9.\-^]{1,12}$/.test(_qt)){ SIMT=_qt.toUpperCase(); document.getElementById('sm-t').value=SIMT; simulate(); }
ideas();
"""
