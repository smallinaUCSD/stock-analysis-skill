"""One politician's trading profile: who they are (party, office, time in
office, committees), what their filings imply they hold, a copy-their-trades
performance chart vs the S&P 500, a timeline of buys and sells, and the trades
themselves. Data from /api/politician/<id> and /api/politician/<id>/performance.
"""

from __future__ import annotations

import html
import json

from ..dashboard.render import _CSS, _THEME_BOOT, icon


def politician_html(pid: str) -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Politician</title>" + _THEME_BOOT + "<style>" + _CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header class=\"pp-head\"><div id=\"who\" class=\"pp-who\"><span class=\"muted\">Loading…</span></div>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" aria-label=\"Close\">"
            + icon("x", 17) + "</button></header>"
            "<div id=\"tiles\" class=\"pp-tiles\"></div>"
            "<section class=\"pp-sec\"><h2>Performance if you copied their trades</h2>"
            "<div id=\"perf\" class=\"pp-box muted\">Pricing their trades…</div></section>"
            "<section class=\"pp-sec\"><h2>Timeline</h2><div id=\"tl\" class=\"pp-box muted\">Loading…</div></section>"
            "<section class=\"pp-sec\"><h2>What their filings say they hold</h2><div id=\"pos\" class=\"pp-tw muted\">Loading…</div>"
            "<p class=\"pp-note\">Estimated from reported trades since the first one we have: bought and not reported sold. "
            "It is not their whole portfolio (annual reports cover that), and amounts are midpoints of the reported ranges.</p></section>"
            "<section class=\"pp-sec\" id=\"comm-sec\" style=\"display:none\"><h2>Trades in industries their committees oversee</h2>"
            "<div id=\"comm\" class=\"pp-tw\"></div></section>"
            "<section class=\"pp-sec\"><h2>All reported trades</h2><div id=\"trades\" class=\"pp-tw muted\">Loading…</div></section>"
            "<p class=\"pp-note\" id=\"src-note\"></p>"
            "</div><script>var PID=" + json.dumps(html.escape(pid)) + ";\n" + _JS + "</script></body></html>")


_EXTRA_CSS = """
.pp-head{display:flex;align-items:flex-start;gap:16px}
.tl-dot{cursor:pointer;transition:opacity .15s} .tl-dot:hover,.tl-dot.on{opacity:1;stroke:var(--ink);stroke-width:1.5}
.tl-tip{position:absolute;z-index:5;pointer-events:none;background:var(--bg);border:1px solid var(--border-strong);border-radius:var(--r);
  padding:8px 10px;font-size:13px;line-height:1.45;box-shadow:0 10px 24px -10px rgba(0,0,0,.35);white-space:nowrap}
.tl-tip .up{color:var(--up)} .tl-tip .dn{color:var(--down)} .tl-tip .m{color:var(--muted);font-size:12px}
.pp-follow{margin-top:10px;height:34px;padding:0 14px;border-radius:17px;border:1px solid var(--accent);background:var(--surface);
  color:var(--accent);font:500 13px var(--font);cursor:pointer}
.pp-follow.on{background:var(--accent);color:var(--accent-ink)}
.pp-who{display:flex;gap:18px;align-items:center;flex:1;min-width:0}
.pp-photo{width:96px;height:118px;border-radius:12px;object-fit:cover;background:var(--surface-2);flex:0 0 auto}
.pp-mono{width:96px;height:118px;border-radius:12px;background:var(--surface-3);display:flex;align-items:center;
  justify-content:center;font:500 32px var(--font-display);color:var(--ink-2);flex:0 0 auto}
.pp-who h1{margin:0;font-size:40px;line-height:1.1}
.pp-who .sub{margin:6px 0 0;font-size:15px}
.party{display:inline-block;border-radius:6px;padding:0 7px;font-size:13px;font-weight:500;margin-right:6px}
.party.R{background:color-mix(in srgb,#c0392b 16%,transparent);color:#b03a2e}
.party.D{background:color-mix(in srgb,#2e6db4 16%,transparent);color:#2e6db4}
.party.I{background:var(--surface-3);color:var(--ink-2)}
.comms{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
.comms span{font-size:12px;border:1px solid var(--border);border-radius:5px;padding:1px 6px;color:var(--ink-2)}
.pp-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:18px 0 6px}
.pp-tile{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:10px 14px}
.pp-tile span{display:block;font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px}
.pp-tile b{font-size:22px;font-weight:500} .pp-tile small{display:block;font-size:13px;color:var(--muted)}
.pp-sec{margin-top:22px}
.pp-sec h2{font-family:var(--font-display);font-weight:500;font-size:28px;margin:0 0 8px}
.pp-box{border:1px solid var(--border);border-radius:10px;background:var(--surface);padding:12px 14px}
.pp-box.muted{font-size:14px}
.pp-tw{overflow-x:auto;border:1px solid var(--border);border-radius:10px;background:var(--surface)}
.pp-tw.muted{padding:14px;font-size:14px}
.pp-t{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
.pp-t th,.pp-t td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap}
.pp-t th{font-size:12px;font-weight:500;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px}
.pp-t tr:last-child td{border-bottom:none} .pp-t .r{text-align:right} .pp-t .wrap{white-space:normal;min-width:200px}
.pp-t .up{color:var(--up)} .pp-t .down{color:var(--down)} .pp-t .mu{color:var(--muted)}
.pp-t a{color:var(--link);text-decoration:none} .pp-t a:hover{text-decoration:underline}
.pp-svg{width:100%;height:auto;display:block}
.pp-svg text{fill:var(--muted);font-size:11px;font-family:var(--font)}
.pp-leg{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;margin-bottom:6px}
.pp-leg i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}
.pp-ro{font-size:13px;min-height:18px;margin-top:4px}
.pp-note{font-size:13px;color:var(--muted);line-height:1.55;margin:8px 0 0}
@media (max-width:640px){.pp-who{flex-direction:column;align-items:flex-start}.pp-who h1{font-size:30px}}
"""

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  // came here inside this tab: step back; opened as its own tab: close it
  var r=document.referrer||'';
  if(history.length>1 && r.indexOf(location.origin+'/')===0 && r!==location.href){ history.back(); return false; }
  try{ if(window.opener && !window.opener.closed) window.opener.focus(); }catch(_){}
  window.close();
  setTimeout(function(){ location.href='/trades'; }, 200);          // the browser refused to close it
  return false; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
function fdate(iso){ if(!iso) return '-'; var p=iso.split('-'); return ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+p[1]-1]+' '+(+p[2])+', '+p[0]; }
function big(v){ if(v==null) return '-'; var a=Math.abs(v); return a>=1e9?'$'+(v/1e9).toFixed(1)+'B':(a>=1e6?'$'+(v/1e6).toFixed(1)+'M':(a>=1e3?'$'+(v/1e3).toFixed(0)+'k':'$'+Math.round(v))); }
function pct(v){ if(v==null) return '<span class="mu">-</span>'; return '<span class="'+(v>=0?'up':'down')+'">'+(v>=0?'+':'')+(v*100).toFixed(1)+'%</span>'; }
function tk(t){ return t?'<a href="/analysis/'+encodeURIComponent(t)+'">'+esc(t)+'</a>':'<span class="mu">-</span>'; }
function yrs(iso){ if(!iso) return ''; var y=(new Date()-new Date(iso))/3.15576e10; return y<1?'less than a year':(Math.floor(y)+' year'+(Math.floor(y)===1?'':'s')); }
var D=null;
function renderWho(p){
  var party=(p.party||'')[0]||'I';
  var img='<img class="pp-photo" src="'+esc(p.photo)+'" alt="" onerror="this.outerHTML=\'<div class=&quot;pp-mono&quot;>'+esc((p.name||'?').split(' ').map(function(w){return w[0];}).slice(0,2).join(''))+'</div>\'">';
  var office=p.office||((p.chamber==='Senate'?'Senator':'Representative')+(p.state?', '+p.state+(p.district!=null&&p.chamber==='House'?'-'+p.district:''):''));
  var comms=(p.committees||[]).map(function(c){ return '<span>'+esc(c.name.replace(/^(House|Senate) Committee on (the )?/,'').replace(/^Committee on (the )?/,''))+(c.role?' · '+esc(c.role):'')+'</span>'; }).join('');
  document.getElementById('who').innerHTML=img+'<div><h1>'+esc(p.name)+'</h1><p class="sub"><span class="party '+party+'">'+esc(p.party||'')+'</span>'+esc(office)+
    '</p><p class="sub muted">In office since '+fdate(p.since)+' ('+yrs(p.since)+(p.since_note?'; '+esc(p.since_note):'')+')</p>'+(comms?'<div class="comms">'+comms+'</div>':'')+'</div>';
  document.title=p.name;
}
function renderTiles(s){
  var t=[['Trades',s.trades,s.first?fdate(s.first)+' to '+fdate(s.last):''],['Bought (est.)',big(s.bought),s.buys+' buys'],
    ['Sold (est.)',big(s.sold),s.sells+' sells'],['Reported after',s.avg_lag!=null?Math.round(s.avg_lag)+' days':'-','on average'],
    ['Late filings',s.late,'reported over 45 days after']];
  document.getElementById('tiles').innerHTML=t.map(function(x){ return '<div class="pp-tile"><span>'+x[0]+'</span><b>'+x[1]+'</b><small>'+x[2]+'</small></div>'; }).join('');
}
function renderPos(pos){ var box=document.getElementById('pos'), open=pos.filter(function(p){return p.open;});
  if(!open.length){ box.textContent='No open positions implied by their reported trades.'; return; }
  box.className='pp-tw'; box.innerHTML='<table class="pp-t"><thead><tr><th>Ticker</th><th>Company</th><th class="r">Net bought (est.)</th><th>First trade</th><th>Latest</th></tr></thead><tbody>'+
    open.map(function(p){ return '<tr><td>'+tk(p.ticker)+'</td><td class="wrap">'+esc(p.asset)+'</td><td class="r">'+big(p.cost)+'</td><td>'+fdate(p.first)+'</td><td>'+fdate(p.last)+'</td></tr>'; }).join('')+'</tbody></table>'; }
function renderTrades(tr){ var box=document.getElementById('trades');
  if(!tr.length){ box.textContent='No trades found.'; return; }
  box.className='pp-tw'; box.innerHTML='<table class="pp-t"><thead><tr><th>Traded</th><th>Ticker</th><th>Asset</th><th>Type</th><th class="r">Amount</th><th>Owner</th><th>Reported</th></tr></thead><tbody>'+
    tr.slice(0,600).map(function(t){ var c=(t.type||'').indexOf('Buy')===0?'up':((t.type||'').indexOf('Sell')===0?'down':'mu');
      return '<tr><td>'+fdate(t.traded)+'</td><td>'+tk(t.ticker)+'</td><td class="wrap">'+esc(t.asset)+'</td><td class="'+c+'">'+esc(t.type)+'</td><td class="r">'+esc(t.amount)+
        '</td><td>'+esc(t.owner)+'</td><td><a href="'+esc(t.url)+'" target="_blank" rel="noopener">'+fdate(t.filed)+'</a></td></tr>'; }).join('')+'</tbody></table>'+
    (tr.length>600?'<p class="pp-note" style="padding:0 10px 10px">Showing the latest 600 of '+tr.length+'.</p>':''); }

// timeline: one lane per most-traded ticker; green buys above, red sells, sized by amount
function renderTimeline(tr){ var box=document.getElementById('tl');
  var rows=tr.filter(function(t){ return t.ticker&&t.traded; });
  if(!rows.length){ box.textContent='No stock trades to plot.'; return; }
  var cnt={}; rows.forEach(function(t){ cnt[t.ticker]=(cnt[t.ticker]||0)+1; });
  var lanes=Object.keys(cnt).sort(function(a,b){return cnt[b]-cnt[a];}).slice(0,14);
  rows=rows.filter(function(t){ return lanes.indexOf(t.ticker)>=0; });
  var ds=rows.map(function(t){return +new Date(t.traded);}), lo=Math.min.apply(null,ds), hi=Math.max.apply(null,ds)||lo+1;
  if(hi===lo) hi=lo+86400000;
  var W=900, L=64, R=16, T=10, LH=24, H=T+lanes.length*LH+26;
  var X=function(ms){ return L+(ms-lo)/(hi-lo)*(W-L-R); };
  var s='<svg class="pp-svg" viewBox="0 0 '+W+' '+H+'">';
  lanes.forEach(function(l,i){ var y=T+i*LH+LH/2; s+='<line x1="'+L+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'" stroke="var(--border)" stroke-width="0.8"/><text x="'+(L-8)+'" y="'+(y+4)+'" text-anchor="end">'+esc(l)+'</text>'; });
  rows.forEach(function(t){ var i=lanes.indexOf(t.ticker), y=T+i*LH+LH/2, amt=((t.amount_low||0)+(t.amount_high||t.amount_low||0))/2;
    var r=Math.max(3,Math.min(10,2+Math.log10(Math.max(amt,1000))*1.4-3)); var buy=(t.type||'').indexOf('Buy')===0;
    var tip='<b>'+esc(t.ticker)+'</b> '+(buy?'<span class=up>bought</span>':'<span class=dn>sold</span>')+'<br>'+esc(t.amount||'amount not given')+
      '<br><span class=m>Traded '+fdate(t.traded)+(t.filed?' · disclosed '+fdate(t.filed):'')+'</span>'+(t.asset&&t.asset!==t.ticker?'<br><span class=m>'+esc(t.asset)+'</span>':'');
    s+='<circle class="tl-dot" cx="'+X(+new Date(t.traded)).toFixed(1)+'" cy="'+y+'" r="'+Math.max(r,4.5).toFixed(1)+'" fill="'+(buy?'var(--up)':'var(--down)')+'" opacity="0.75" data-tip="'+esc(tip)+'"></circle>'; });
  [lo,(lo+hi)/2,hi].forEach(function(ms,k){ s+='<text x="'+X(ms)+'" y="'+(H-6)+'" text-anchor="'+['start','middle','end'][k]+'">'+fdate(new Date(ms).toISOString().slice(0,10))+'</text>'; });
  s+='</svg>';
  box.className='pp-box'; box.style.position='relative';
  box.innerHTML='<div class="pp-leg"><span><i style="background:var(--up)"></i>Buy</span><span><i style="background:var(--down)"></i>Sell</span><span class="muted">Bigger dot, bigger trade. Hover or tap a dot for details.</span></div>'+s+'<div class="tl-tip" hidden></div>';
  var tipEl=box.querySelector('.tl-tip');
  function show(dot, ev){ tipEl.innerHTML=dot.getAttribute('data-tip'); tipEl.hidden=false;
    var b=box.getBoundingClientRect(), d=dot.getBoundingClientRect();
    var x=d.left-b.left+d.width/2, y=d.top-b.top;
    tipEl.style.left=Math.max(4,Math.min(b.width-tipEl.offsetWidth-4,x-tipEl.offsetWidth/2))+'px';
    tipEl.style.top=(y-tipEl.offsetHeight-8<0?y+d.height+8:y-tipEl.offsetHeight-8)+'px';
    box.querySelectorAll('.tl-dot.on').forEach(function(o){ o.classList.remove('on'); }); dot.classList.add('on'); }
  function hide(){ tipEl.hidden=true; box.querySelectorAll('.tl-dot.on').forEach(function(o){ o.classList.remove('on'); }); }
  box.addEventListener('mouseover',function(e){ var d=e.target.closest('.tl-dot'); if(d) show(d,e); });
  box.addEventListener('mouseout',function(e){ if(e.target.closest('.tl-dot')) hide(); });
  box.addEventListener('click',function(e){ var d=e.target.closest('.tl-dot'); if(d){ show(d,e); e.stopPropagation(); } else hide(); }); }

function renderPerf(r){ var box=document.getElementById('perf');
  if(r.working){ setTimeout(loadPerf,4000); return; }
  if(!r.ok||!r.performance){ box.className='pp-box muted'; box.textContent=r.error||'Not enough priced stock trades to chart.'; return; }
  var p=r.performance, sm=p.summary, n=p.dates.length, W=900, H=260, L=64, R=12, T=10, B=22;
  var all=p.value.concat(p.bench,p.invested), lo=Math.min.apply(null,all), hi=Math.max.apply(null,all); if(hi===lo) hi=lo+1;
  var X=function(i){return L+i/(Math.max(n-1,1))*(W-L-R);}, Y=function(v){return T+(hi-v)/(hi-lo)*(H-T-B);};
  var line=function(arr,col,w,dash){ return '<polyline points="'+arr.map(function(v,i){return X(i).toFixed(1)+','+Y(v).toFixed(1);}).join(' ')+'" fill="none" stroke="'+col+'" stroke-width="'+w+'"'+(dash?' stroke-dasharray="4 4"':'')+'/>'; };
  var s='<svg class="pp-svg" viewBox="0 0 '+W+' '+H+'">';
  [hi,(hi+lo)/2,lo].forEach(function(v){ s+='<line x1="'+L+'" y1="'+Y(v)+'" x2="'+(W-R)+'" y2="'+Y(v)+'" stroke="var(--border)" stroke-width="0.7"/><text x="'+(L-6)+'" y="'+(Y(v)+4)+'" text-anchor="end">'+big(v)+'</text>'; });
  s+=line(p.invested,'var(--muted)',1.2,true)+line(p.bench,'#5db8a6',1.6)+line(p.value,'var(--accent)',2);
  [0,Math.floor((n-1)/2),n-1].forEach(function(i,k){ s+='<text x="'+X(i)+'" y="'+(H-6)+'" text-anchor="'+['start','middle','end'][k]+'">'+fdate(p.dates[i])+'</text>'; });
  s+='</svg>';
  box.className='pp-box'; box.innerHTML='<div class="pp-leg"><span><i style="background:var(--accent)"></i>Copying their trades '+pct(sm.gain)+'</span><span><i style="background:#5db8a6"></i>Same dollars in the S&amp;P 500 '+pct(sm.bench_gain)+
    '</span><span><i style="background:var(--muted)"></i>Money put in ('+big(sm.invested)+')</span></div>'+s+
    '<p class="pp-note">Each buy puts the midpoint of its reported range into the stock on the trade date; each reported sale sells it. '+sm.priced_trades+' trades in '+r.priced_tickers+
    ' tickers were priced (bonds and unlisted funds can\'t be). Because trades are disclosed up to 45 days late, you couldn\'t actually have copied them on the day.</p>';
  var ov=r.committee_trades||[];
  if(ov.length){ document.getElementById('comm-sec').style.display=''; document.getElementById('comm').innerHTML='<table class="pp-t"><thead><tr><th>Traded</th><th>Ticker</th><th>Sector</th><th>Type</th><th class="r">Amount</th></tr></thead><tbody>'+
    ov.map(function(t){ return '<tr><td>'+fdate(t.traded)+'</td><td>'+tk(t.ticker)+'</td><td>'+esc(t.sector)+'</td><td>'+esc(t.type)+'</td><td class="r">'+esc(t.amount)+'</td></tr>'; }).join('')+'</tbody></table>'; }
}
function loadPerf(){ fetch('/api/politician/'+encodeURIComponent(PID)+'/performance').then(function(r){return r.json();}).then(renderPerf)
  .catch(function(){ document.getElementById('perf').textContent='Performance unavailable right now.'; }); }
fetch('/api/politician/'+encodeURIComponent(PID)).then(function(r){return r.json();}).then(function(d){
  if(!d.ok){ document.getElementById('who').textContent=d.error||'Not found.'; return; }
  D=d; renderWho(d.person); renderTiles(d.stats); renderPos(d.positions); renderTimeline(d.trades); renderTrades(d.trades);
  document.getElementById('src-note').textContent=d.person.chamber==='President'?
    'From the President\'s OGE Form 278-T reports (scanned filings read by OCR'+(d.coverage?': '+d.coverage.read+' of '+d.coverage.filings+' listed filings were legible enough to read':'')+
    '; within those, about 9 in 10 rows are read). The accounts are trustee-managed. Research on officials\' trades finds no reliable market-beating edge.':
    'From STOCK Act periodic transaction reports (House Clerk / Senate eFD), up to 45 days after each trade. Research finds members\' trades have not beaten the market on average since 2012 (Belmont et al., 2022).';
  loadPerf(); followBtn(d.person); }).catch(function(){ document.getElementById('who').textContent='Could not load this profile.'; });
// signed-in users (public site) can follow this person to be notified of new trades
function followBtn(p){
  fetch('/api/me').then(function(r){ return r.ok?r.json():null; }).then(function(me){
    if(!me||!me.ok) return;
    var on=(me.follows||[]).some(function(f){ return f.pid===PID; });
    var b=document.createElement('button'); b.className='pp-follow'+(on?' on':'');
    function paint(){ b.textContent=on?'Following':'Follow for trade alerts'; b.classList.toggle('on',on); }
    paint();
    b.onclick=function(){ fetch('/api/me/follows',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify(on?{remove:[PID]}:{add:[{pid:PID,name:p.name}]})}).then(function(r){return r.json();})
      .then(function(d){ if(d.ok){ on=!on; paint(); } }); };
    document.getElementById('who').appendChild(b);
  }).catch(function(){});
}
"""
