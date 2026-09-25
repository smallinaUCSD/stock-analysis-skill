"""Hedge-fund profile: latest 13F holdings, what copying the portfolio would
have returned, reported value by quarter, and a timeline of buys and sells.
Data from /api/funds/<cik> and /api/fund/<cik>/history."""

from __future__ import annotations

from ..dashboard.render import _CSS, _THEME_BOOT, icon
from .politician_page import _EXTRA_CSS as _PP_CSS


def fund_html(cik: int) -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Fund</title>" + _THEME_BOOT + "<style>" + _CSS + _PP_CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header class=\"pp-head\"><div id=\"who\" class=\"pp-who\"><span class=\"muted\">Loading…</span></div>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" aria-label=\"Close\">"
            + icon("x", 17) + "</button></header>"
            "<div id=\"tiles\" class=\"pp-tiles\"></div>"
            "<section class=\"pp-sec\"><h2>Performance if you copied their portfolio</h2>"
            "<div id=\"perf\" class=\"pp-box muted\">Reading their past filings and pricing them (the first load takes a minute)…</div></section>"
            "<section class=\"pp-sec\"><h2>Reported portfolio by quarter</h2><div id=\"val\" class=\"pp-box muted\">Loading…</div></section>"
            "<section class=\"pp-sec\"><h2>Timeline of buys and sells</h2><div id=\"tl\" class=\"pp-box muted\">Loading…</div></section>"
            "<section class=\"pp-sec\"><h2>What they hold now</h2><div id=\"hold\" class=\"pp-tw muted\">Loading…</div></section>"
            "<section class=\"pp-sec\" id=\"sold-sec\" style=\"display:none\"><h2>Sold out this quarter</h2><div id=\"sold\" class=\"pp-tw\"></div></section>"
            "<p class=\"pp-note\">From SEC Form 13F, which large managers file within 45 days after each quarter. It lists US-listed "
            "stocks, some funds and options they held on the last day of the quarter; it leaves out short positions, bonds, "
            "cash and foreign shares, so it is not their whole portfolio or their actual returns.</p>"
            "</div><script>var CIK=" + str(int(cik)) + ";\n" + _JS + "</script></body></html>")


_EXTRA_CSS = """
.fd-mono{width:96px;height:96px;border-radius:18px;background:var(--surface-3);display:flex;align-items:center;justify-content:center;
  font-family:var(--font-display);font-size:34px;flex:0 0 auto}
.fd-bar{display:inline-block;height:8px;border-radius:4px;background:var(--accent);vertical-align:middle;margin-right:8px}
.fd-badge{font-size:12px;padding:2px 8px;border-radius:10px;border:1px solid var(--border-strong)}
.fd-badge.New{background:color-mix(in srgb,var(--up) 18%,transparent);border-color:transparent;color:var(--up)}
.fd-badge.Added{color:var(--up)} .fd-badge.Trimmed{color:var(--down)}
.fd-badge.Sold{background:color-mix(in srgb,var(--down) 16%,transparent);border-color:transparent;color:var(--down)}
"""

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){ try{window.opener.focus();}catch(_){}; window.close(); }
  else location.href='/trades'; return false; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
function big(v){ var a=Math.abs(v); return (v<0?'-':'')+'$'+(a>=1e12?(a/1e12).toFixed(2)+'T':a>=1e9?(a/1e9).toFixed(1)+'B':a>=1e6?(a/1e6).toFixed(0)+'M':Math.round(a).toLocaleString()); }
function fdate(iso){ if(!iso) return '-'; var p=iso.split('-'); return ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+p[1]-1]+' '+(+p[2])+', '+p[0]; }
function qlabel(p){ return p?'Q'+(Math.floor((+p.slice(5,7)-1)/3)+1)+' '+p.slice(0,4):''; }
var REP=null;
function renderWho(d){
  var ini=(d.fund||'?').split(' ').map(function(w){return w[0];}).slice(0,2).join('');
  document.title=d.fund;
  document.getElementById('who').innerHTML='<span class="fd-mono">'+esc(ini)+'</span><div><h1>'+esc(d.fund)+'</h1>'+
    '<p class="sub muted">'+esc(d.manager||d.filer)+' · latest filing covers '+qlabel(d.period)+' (filed '+fdate(d.filed)+')</p></div>';
  followBtn(d); }
function renderTiles(d){ var h=(d.holdings||[]), top10=h.slice(0,10).reduce(function(a,r){return a+(r.weight||0);},0), c=d.counts||{};
  document.getElementById('tiles').innerHTML=[
    ['Reported portfolio',big(d.total_value),'US stocks and funds'],['Positions',d.positions,''],
    ['Top 10',(top10*100).toFixed(0)+'%','of the portfolio'],
    ['This quarter',(c.New||0)+' new · '+(c.Added||0)+' added',(c.Trimmed||0)+' trimmed · '+(c['Sold out']||0)+' sold out']]
    .map(function(t){ return '<div class="pp-tile"><span>'+t[0]+'</span><b>'+t[1]+'</b><small>'+t[2]+'</small></div>'; }).join(''); }
function renderHold(d){
  var mx=Math.max.apply(null,(d.holdings||[]).map(function(r){return r.weight||0;}))||1;
  var t='<table class="pp-t"><thead><tr><th>Company</th><th class="r">Value</th><th>Share of portfolio</th><th>Change</th></tr></thead><tbody>'+
    (d.holdings||[]).map(function(r){ var ch=r.change==='Held'?'':'<span class="fd-badge '+(r.change==='Sold out'?'Sold':r.change)+'">'+esc(r.change)+
      (r.share_change!=null&&r.change!=='New'?' '+(r.share_change>0?'+':'')+(r.share_change*100).toFixed(0)+'%':'')+'</span>';
      return '<tr><td class="wrap">'+(r.ticker?'<a href="/analysis/'+encodeURIComponent(r.ticker)+'" target="_blank" rel="noopener"><b>'+esc(r.ticker)+'</b></a> ':'')+
        '<span class="mu">'+esc(r.name)+(r.put_call?' ('+esc(r.put_call.toLowerCase())+'s)':'')+'</span></td><td class="r">'+big(r.value)+'</td>'+
        '<td><span class="fd-bar" style="width:'+Math.max(2,(r.weight||0)/mx*140).toFixed(0)+'px"></span>'+((r.weight||0)*100).toFixed(1)+'%</td><td>'+ch+'</td></tr>'; }).join('')+'</tbody></table>';
  var el=document.getElementById('hold'); el.className='pp-tw'; el.innerHTML=t;
  if((d.sold_out||[]).length){ document.getElementById('sold-sec').style.display='';
    document.getElementById('sold').innerHTML='<table class="pp-t"><thead><tr><th>Company</th><th class="r">Value last quarter</th></tr></thead><tbody>'+
      d.sold_out.map(function(r){ return '<tr><td class="wrap">'+(r.ticker?'<b>'+esc(r.ticker)+'</b> ':'')+'<span class="mu">'+esc(r.name)+'</span></td><td class="r">'+big(r.prev_value||0)+'</td></tr>'; }).join('')+'</tbody></table>'; } }
function renderPerf(h){ var box=document.getElementById('perf'), p=h.performance;
  if(!p){ box.className='pp-box muted'; box.textContent='Not enough priced holdings to chart.'; return; }
  var n=p.dates.length, W=900, H=260, L=64, R=12, T=10, B=22, all=p.value.concat(p.bench), lo=Math.min.apply(null,all), hi=Math.max.apply(null,all);
  var X=function(i){return L+i/Math.max(n-1,1)*(W-L-R);}, Y=function(v){return T+(hi-v)/((hi-lo)||1)*(H-T-B);};
  var line=function(a,c,w){ return '<polyline points="'+a.map(function(v,i){return X(i).toFixed(1)+','+Y(v).toFixed(1);}).join(' ')+'" fill="none" stroke="'+c+'" stroke-width="'+w+'"/>'; };
  var s='<svg class="pp-svg" viewBox="0 0 '+W+' '+H+'">';
  [hi,(hi+lo)/2,lo].forEach(function(v){ s+='<line x1="'+L+'" y1="'+Y(v)+'" x2="'+(W-R)+'" y2="'+Y(v)+'" stroke="var(--border)" stroke-width="0.7"/><text x="'+(L-6)+'" y="'+(Y(v)+4)+'" text-anchor="end">'+big(v)+'</text>'; });
  s+=line(p.bench,'#5db8a6',1.6)+line(p.value,'var(--accent)',2);
  [0,Math.floor((n-1)/2),n-1].forEach(function(i,k){ s+='<text x="'+X(i)+'" y="'+(H-6)+'" text-anchor="'+['start','middle','end'][k]+'">'+fdate(p.dates[i])+'</text>'; });
  s+='</svg>'; var sm=p.summary, pc=function(x){ return (x>=0?'+':'')+(x*100).toFixed(1)+'%'; };
  box.className='pp-box'; box.innerHTML='<div class="pp-leg"><span><i style="background:var(--accent)"></i>Copying their top '+h.copied_top+' holdings</span><span><i style="background:#5db8a6"></i>S&amp;P 500</span></div>'+s+
    '<p class="pp-ro">$10,000 from '+fdate(p.dates[0])+' would be '+big(p.value[n-1])+' ('+pc(sm.return)+') vs '+big(p.bench[n-1])+' ('+pc(sm.bench_return)+') in the S&amp;P 500. '+
    '<span class="muted">Rebalanced into each filing\'s top holdings on the day it became public, so it trails their real moves by 45+ days.</span></p>'; }
function renderVal(h){ var q=h.quarters||[], box=document.getElementById('val'); if(!q.length){ box.textContent='No history.'; return; }
  var mx=Math.max.apply(null,q.map(function(x){return x.value;}))||1, W=900, H=180, L=12, bw=(W-L*2)/q.length;
  var s='<svg class="pp-svg" viewBox="0 0 '+W+' '+(H+34)+'">'+q.map(function(x,i){ var h=x.value/mx*(H-24), xx=L+i*bw+bw*0.2;
    return '<rect x="'+xx.toFixed(1)+'" y="'+(H-h).toFixed(1)+'" width="'+(bw*0.6).toFixed(1)+'" height="'+h.toFixed(1)+'" rx="3" fill="var(--accent)" opacity="'+(i===q.length-1?1:0.55)+'"/>'+
      '<text x="'+(xx+bw*0.3).toFixed(1)+'" y="'+(H-h-6).toFixed(1)+'" text-anchor="middle">'+big(x.value)+'</text>'+
      '<text x="'+(xx+bw*0.3).toFixed(1)+'" y="'+(H+16)+'" text-anchor="middle">'+esc(x.label)+'</text>'+
      '<text x="'+(xx+bw*0.3).toFixed(1)+'" y="'+(H+30)+'" text-anchor="middle">'+x.positions+' positions</text>'; }).join('')+'</svg>';
  box.className='pp-box'; box.innerHTML=s; }
var COL={New:'var(--up)',Added:'color-mix(in srgb,var(--up) 55%,var(--surface))',Trimmed:'color-mix(in srgb,var(--down) 55%,var(--surface))','Sold out':'var(--down)'};
function renderTl(h){ var box=document.getElementById('tl'), ev=(h.events||[]).filter(function(e){return e.ticker;}), q=h.quarters||[];
  if(!ev.length||q.length<2){ box.textContent='Not enough quarters yet.'; return; }
  var cnt={}; ev.forEach(function(e){ cnt[e.ticker]=(cnt[e.ticker]||0)+1; });
  var lanes=Object.keys(cnt).sort(function(a,b){return cnt[b]-cnt[a];}).slice(0,16); ev=ev.filter(function(e){ return lanes.indexOf(e.ticker)>=0; });
  var periods=q.map(function(x){return x.period;}), W=900, L=64, R=16, T=10, LH=24, H=T+lanes.length*LH+26;
  var X=function(p){ return L+periods.indexOf(p)/Math.max(periods.length-1,1)*(W-L-R); };
  var s='<svg class="pp-svg" viewBox="0 0 '+W+' '+H+'">';
  lanes.forEach(function(l,i){ var y=T+i*LH+LH/2; s+='<line x1="'+L+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'" stroke="var(--border)" stroke-width="0.8"/><text x="'+(L-8)+'" y="'+(y+4)+'" text-anchor="end">'+esc(l)+'</text>'; });
  ev.forEach(function(e){ var y=T+lanes.indexOf(e.ticker)*LH+LH/2, r=Math.max(4.5,Math.min(10,2+Math.log10(Math.max(e.value,1e6))*1.2-5));
    var tip='<b>'+esc(e.ticker)+'</b> '+esc(e.change.toLowerCase())+(e.share_change!=null&&e.change!=='New'&&e.change!=='Sold out'?' ('+(e.share_change>0?'+':'')+(e.share_change*100).toFixed(0)+'% shares)':'')+
      '<br>'+(e.change==='Sold out'?'was ':'now ')+big(e.value)+'<br><span class=m>'+qlabel(e.period)+', disclosed '+fdate(e.filed)+'</span>';
    s+='<circle class="tl-dot" cx="'+X(e.period).toFixed(1)+'" cy="'+y+'" r="'+r.toFixed(1)+'" fill="'+COL[e.change]+'" opacity="0.85" data-tip="'+esc(tip)+'"/>'; });
  periods.forEach(function(p){ s+='<text x="'+X(p).toFixed(1)+'" y="'+(H-6)+'" text-anchor="middle">'+qlabel(p)+'</text>'; });
  s+='</svg>'; box.className='pp-box'; box.style.position='relative';
  box.innerHTML='<div class="pp-leg">'+Object.keys(COL).map(function(k){ return '<span><i style="background:'+COL[k]+';height:8px;width:8px;border-radius:50%"></i>'+k+'</span>'; }).join('')+
    '<span class="muted">Bigger dot, bigger position. Hover or tap a dot.</span></div>'+s+'<div class="tl-tip" hidden></div>';
  var tipEl=box.querySelector('.tl-tip');
  function show(dot){ tipEl.innerHTML=dot.getAttribute('data-tip'); tipEl.hidden=false; var b=box.getBoundingClientRect(), d=dot.getBoundingClientRect();
    tipEl.style.left=Math.max(4,Math.min(b.width-tipEl.offsetWidth-4,d.left-b.left+d.width/2-tipEl.offsetWidth/2))+'px';
    tipEl.style.top=(d.top-b.top-tipEl.offsetHeight-8<0?d.top-b.top+d.height+8:d.top-b.top-tipEl.offsetHeight-8)+'px'; }
  box.addEventListener('mouseover',function(e){ var d=e.target.closest('.tl-dot'); if(d) show(d); });
  box.addEventListener('mouseout',function(e){ if(e.target.closest('.tl-dot')) tipEl.hidden=true; });
  box.addEventListener('click',function(e){ var d=e.target.closest('.tl-dot'); if(d) show(d); else tipEl.hidden=true; }); }
function followBtn(d){
  fetch('/api/me').then(function(r){ return r.ok?r.json():null; }).then(function(me){
    if(!me||!me.ok) return; var pid='fund:'+CIK, on=(me.follows||[]).some(function(f){ return f.pid===pid; });
    var b=document.createElement('button'); b.className='pp-follow';
    function paint(){ b.textContent=on?'Following':'Follow for new filings'; b.classList.toggle('on',on); } paint();
    b.onclick=function(){ fetch('/api/me/follows',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(on?{remove:[pid]}:{add:[{pid:pid,name:d.fund}]})}).then(function(r){return r.json();}).then(function(x){ if(x.ok){ on=!on; paint(); } }); };
    document.querySelector('#who > div').appendChild(b); }).catch(function(){}); }
fetch('/api/funds/'+CIK).then(function(r){return r.json();}).then(function(d){
  if(!d.ok){ document.getElementById('who').textContent=d.error||'Not found.'; return; }
  REP=d; renderWho(d); renderTiles(d); renderHold(d); }).catch(function(){ document.getElementById('who').textContent='Could not load this fund.'; });
fetch('/api/fund/'+CIK+'/history').then(function(r){return r.json();}).then(function(h){
  if(!h.ok){ ['perf','val','tl'].forEach(function(id){ document.getElementById(id).textContent=h.error||'History unavailable.'; }); return; }
  renderPerf(h); renderVal(h); renderTl(h); }).catch(function(){ document.getElementById('perf').textContent='History unavailable.'; });
"""
