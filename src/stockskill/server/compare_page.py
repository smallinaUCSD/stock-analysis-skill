"""Compare page: 2-4 stocks or funds side by side.

Growth of $10k and drawdown charts over the tickers' common history, trailing
returns, risk vs the S&P 500, return correlations, a profile table, and what's
inside each fund (top holdings + overlap). Data comes from GET /api/compare and
/api/compare/holdings; every number is computed server-side by tested Python.
"""

from __future__ import annotations

import json
import re

from ..dashboard.render import _CSS, _THEME_BOOT, icon

_TK = re.compile(r"^[A-Z0-9.\-\^]{1,12}$")


def compare_html(initial: str = "") -> str:
    tks = [t for t in re.split(r"[\s,;]+", (initial or "").upper()) if t and _TK.match(t)][:4]
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Compare</title>" + _THEME_BOOT + "<style>" + _CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Compare</h1>"
            "<span class=\"sub\" style=\"margin:0\">Up to four stocks or funds, side by side</span>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" "
            "aria-label=\"Close\">" + icon("x", 17) + "</button></header>"
            + _CONTROLS +
            "<div id=\"cmp-msg\" class=\"muted cmp-msg\">Add two to four tickers to compare.</div>"
            "<div id=\"cmp-out\" style=\"display:none\">"
            "<p id=\"cmp-span\" class=\"muted cmp-span\"></p>"
            "<section class=\"cmp-sec\"><h2>Growth of $10,000</h2>"
            "<div id=\"leg-g\" class=\"cmp-leg\"></div>"
            "<svg id=\"ch-g\" class=\"cmp-svg\" viewBox=\"0 0 900 300\" preserveAspectRatio=\"xMidYMid meet\"></svg>"
            "<div id=\"ro-g\" class=\"cmp-ro muted\"></div></section>"
            "<section class=\"cmp-sec\"><h2>Drawdown from the previous high</h2>"
            "<svg id=\"ch-d\" class=\"cmp-svg\" viewBox=\"0 0 900 190\" preserveAspectRatio=\"xMidYMid meet\"></svg>"
            "<div id=\"ro-d\" class=\"cmp-ro muted\"></div></section>"
            "<section class=\"cmp-sec\"><h2>Returns</h2><div id=\"t-ret\" class=\"cmp-tw\"></div>"
            "<p class=\"cmp-note\">3Y and 5Y are per year. Each ticker uses its own full history here.</p></section>"
            "<section class=\"cmp-sec\"><h2 id=\"risk-h\">Risk and return</h2><div id=\"t-risk\" class=\"cmp-tw\"></div>"
            "<p class=\"cmp-note\">Beta and alpha are measured against the S&amp;P 500 (SPY). "
            "Alpha marked &ldquo;noise&rdquo; is too small, for the time span, to tell apart from luck.</p></section>"
            "<section class=\"cmp-sec\"><h2>How closely they move together</h2><div id=\"t-corr\" class=\"cmp-tw\"></div>"
            "<p class=\"cmp-note\">Correlation of daily returns: 1 moves in lockstep, 0 unrelated, "
            "negative tends to move opposite.</p></section>"
            "<section class=\"cmp-sec\" id=\"pair-sec\" style=\"display:none\"><h2>Pair spread</h2>"
            "<p id=\"pair-read\" class=\"cmp-span\"></p>"
            "<svg id=\"ch-z\" class=\"cmp-svg\" viewBox=\"0 0 900 170\" preserveAspectRatio=\"xMidYMid meet\"></svg>"
            "<p class=\"cmp-note\">How far the price ratio sits from its average over the past year, in standard "
            "deviations. Beyond &plusmn;2 is unusually stretched. That is not a prediction: see the track record below.</p></section>"
            "<section class=\"cmp-sec\"><h2>Profile</h2><div id=\"t-prof\" class=\"cmp-tw\"></div></section>"
            "<section class=\"cmp-sec\"><h2>What's inside</h2><div id=\"hold\" class=\"muted\">Loading holdings…</div></section>"
            "</div>"
            "<section class=\"cmp-sec\" id=\"wl-pairs\"><h2>Pairs on your watchlist</h2>"
            "<div id=\"wl-pairs-body\" class=\"muted\" style=\"font-size:14px\">Loading…</div></section>"
            "<p class=\"muted\" style=\"font-size:13px;margin-top:18px\">"
            "Past performance, not a forecast. Analysis, not advice. Free data may be delayed. "
            "All numbers computed by tested Python.</p>"
            "</div><script>var INIT=" + json.dumps(tks) + ";\n" + _JS + "</script></body></html>")


_CONTROLS = """
<div class="cmp-bar">
  <div id="chips" class="cmp-chips"></div>
  <div class="addwrap" style="flex:0 1 220px">
    <input id="ctk" placeholder="Add a ticker (e.g. VOO)" autocomplete="off"
      oninput="csearch()" onkeydown="ckey(event)">
    <div id="csug" class="addsug"></div>
  </div>
  <span class="seg" id="perseg">
    <button data-p="1y">1Y</button><button data-p="3y">3Y</button>
    <button data-p="5y" class="on">5Y</button><button data-p="max">Max</button>
  </span>
  <label class="cmp-chk"><input type="checkbox" id="logsc" onchange="drawAll()"> Log scale</label>
</div>
<div class="cmp-presets muted">Try:
  <a href="#" onclick="return preset('VOO,FNGU')">VOO vs FNGU</a>
  <a href="#" onclick="return preset('QQQ,TQQQ')">QQQ vs TQQQ</a>
  <a href="#" onclick="return preset('NVDA,AMD,AVGO')">NVDA vs AMD vs AVGO</a>
</div>
"""

_EXTRA_CSS = """
.cmp-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:6px}
.cmp-chips{display:flex;flex-wrap:wrap;gap:6px}
.cmp-chip{display:inline-flex;align-items:center;gap:6px;height:36px;padding:0 6px 0 12px;
  border:1px solid var(--border);border-radius:var(--r);background:var(--surface);font-size:14px;font-weight:500}
.cmp-chip i{width:10px;height:10px;border-radius:50%;display:inline-block}
.cmp-chip button{width:24px;height:24px;border:none;background:transparent;color:var(--muted);cursor:pointer;
  border-radius:50%;display:flex;align-items:center;justify-content:center;font:500 16px var(--font)}
.cmp-chip button:hover{background:var(--surface-2);color:var(--ink)}
.cmp-bar #ctk{width:100%;height:36px;padding:0 11px;border-radius:var(--r);border:1px solid var(--border);
  background:var(--surface);color:var(--ink);font:14px var(--font)}
.cmp-bar .seg{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden}
.cmp-bar .seg button{font:500 13px var(--font);padding:0 12px;height:34px;border:none;background:var(--surface);
  color:var(--muted);cursor:pointer}
.cmp-bar .seg button:hover{color:var(--ink)}
.cmp-bar .seg button.on{background:var(--surface-3);color:var(--ink)}
.cmp-chk{font-size:13px;color:var(--muted);display:flex;align-items:center;gap:5px}
.cmp-presets{font-size:13px;margin:4px 0 14px}
.cmp-presets a{color:var(--link);margin-left:8px;text-decoration:underline;text-decoration-color:transparent;
  text-underline-offset:3px;transition:text-decoration-color .15s ease}
.cmp-presets a:hover{text-decoration-color:currentColor}
.cmp-msg{font-size:14px;margin:6px 0}
.cmp-span{font-size:14px;margin:0 0 6px}
.cmp-sec{margin-top:22px}
.cmp-sec h2{font-family:var(--font-display);font-weight:500;font-size:28px;line-height:1.15;margin:0 0 8px}
.cmp-svg{width:100%;height:auto;background:var(--surface);border:1px solid var(--border);border-radius:10px;display:block}
.cmp-svg text{fill:var(--muted);font-size:12px;font-family:var(--font)}
.cmp-leg{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:14px;margin-bottom:8px}
.cmp-leg span{display:inline-flex;align-items:center;gap:7px}
.cmp-leg i{width:14px;height:3px;border-radius:2px;display:inline-block}
.cmp-ro{font-size:13px;min-height:20px;margin-top:6px}
.cmp-ro b{color:var(--ink);font-weight:500}
.cmp-tw{overflow-x:auto;border:1px solid var(--border);border-radius:10px;background:var(--surface)}
.cmp-t{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
.cmp-t th,.cmp-t td{padding:9px 12px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap}
.cmp-t th{font-size:12px;font-weight:500;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px}
.cmp-t tr:last-child td{border-bottom:none}
.cmp-t td:first-child,.cmp-t th:first-child{text-align:left}
.cmp-t .pn{display:block;text-align:left;white-space:normal;min-width:160px}
.cmp-t .tk{font-weight:500;display:inline-flex;align-items:center;gap:7px}
.cmp-t .tk i{width:10px;height:10px;border-radius:50%;display:inline-block}
.cmp-t .up{color:var(--up)} .cmp-t .down{color:var(--down)} .cmp-t .mu{color:var(--muted)}
.cmp-note{font-size:13px;color:var(--muted);margin:6px 0 0;line-height:1.5}
.hold-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.hold-card{border:1px solid var(--border);border-radius:10px;background:var(--surface);padding:12px 14px}
.hold-card h3{margin:0;font-size:16px;font-weight:500;display:flex;align-items:center;gap:7px}
.hold-card h3 i{width:10px;height:10px;border-radius:50%;display:inline-block}
.hold-card .hn{font-size:13px;color:var(--muted);margin:2px 0 10px}
.hrow{display:grid;grid-template-columns:62px 1fr 48px;gap:8px;align-items:center;font-size:13px;margin:4px 0}
.hrow .bar{height:6px;border-radius:3px;background:var(--surface-3);overflow:hidden}
.hrow .bar b{display:block;height:100%;border-radius:3px}
.hrow .w{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}
.pair-list{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 10px}
.pair-chip{display:inline-flex;align-items:center;gap:8px;height:36px;padding:0 12px;border:1px solid var(--border);
  border-radius:var(--r);background:var(--surface);font:500 14px var(--font);color:var(--ink);cursor:pointer}
.pair-chip:hover{background:var(--surface-2)}
.pair-chip .z{font-weight:500}
.addsug{display:none;position:absolute;z-index:60;left:0;right:0;top:calc(100% + 4px);
  background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden;
  box-shadow:var(--shadow-pop)}
.sug{padding:7px 11px;font-size:14px;cursor:pointer;display:flex;gap:8px;align-items:baseline}
.sug:hover{background:var(--surface-2)} .sug b{color:var(--ink)} .sug span{color:var(--muted);font-size:13px}
"""

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  // came here inside this tab: step back; opened as its own tab: close it
  var r=document.referrer||'';
  if(history.length>1 && r.indexOf(location.origin+'/')===0 && r!==location.href){ history.back(); return false; }
  try{ if(window.opener && !window.opener.closed) window.opener.focus(); }catch(_){}
  window.close();
  setTimeout(function(){ location.href='/'; }, 200);          // the browser refused to close it
  return false; }
var COLORS=['var(--accent)','#5db8a6','#e8a55a','#8b7fc7'];
var TICKERS=[], PERIOD='5y', DATA=null, HOLD=null, _req=0;
var W=900, ML=62, MR=14, MT=12, MB=22;

function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
function col(t){ var i=TICKERS.indexOf(t); return COLORS[i<0?0:i%COLORS.length]; }
function dot(t){ return '<i style="background:'+col(t)+'"></i>'; }
function pct(v,dp,signed){ if(v==null||isNaN(v)) return '<span class="mu">n/a</span>';
  var s=(v*100).toFixed(dp==null?1:dp)+'%'; if(signed!==false && v>0) s='+'+s;
  return '<span class="'+(signed===false?'':(v>=0?'up':'down'))+'">'+s+'</span>'; }
function num(v,dp){ return (v==null||isNaN(v))?'<span class="mu">n/a</span>':Number(v).toFixed(dp==null?2:dp); }
function money(v){ return '$'+Math.round(v).toLocaleString(); }
function big(v){ if(v==null) return '<span class="mu">n/a</span>'; var a=Math.abs(v);
  if(a>=1e12) return '$'+(v/1e12).toFixed(2)+'T'; if(a>=1e9) return '$'+(v/1e9).toFixed(1)+'B';
  if(a>=1e6) return '$'+(v/1e6).toFixed(1)+'M'; return '$'+Math.round(v).toLocaleString(); }
function fdate(iso){ var p=iso.split('-'); return (+p[1])+'/'+(+p[2])+'/'+p[0].slice(2); }
function svgEl(tag,a){ var e=document.createElementNS('http://www.w3.org/2000/svg',tag); for(var k in a) e.setAttribute(k,a[k]); return e; }
function niceStep(range,target){ var raw=(range||1)/Math.max(1,target); var p=Math.pow(10,Math.floor(Math.log10(raw)));
  var n=raw/p; var s=n<1.5?1:(n<3?2:(n<7?5:10)); return s*p; }

// ---- chips / input -------------------------------------------------------
function renderChips(){
  document.getElementById('chips').innerHTML=TICKERS.map(function(t){
    return '<span class="cmp-chip">'+dot(t)+esc(t)+'<button title="Remove '+esc(t)+'" aria-label="Remove '+esc(t)+'" onclick="removeT(\''+esc(t)+'\')">&times;</button></span>'; }).join('');
  var inp=document.getElementById('ctk'); inp.disabled=TICKERS.length>=4;
  inp.placeholder=TICKERS.length>=4?'Four is the maximum':'Add a ticker (e.g. VOO)';
}
function addT(t){ t=(t||'').trim().toUpperCase(); if(!t||TICKERS.indexOf(t)>=0||TICKERS.length>=4) return;
  if(!/^[A-Z0-9.\-\^]{1,12}$/.test(t)) return; TICKERS.push(t); changed(); }
function removeT(t){ TICKERS=TICKERS.filter(function(x){return x!==t;}); changed(); }
function preset(s){ TICKERS=s.split(','); changed(); return false; }
function changed(){ renderChips(); syncUrl(); load(); }
function syncUrl(){ try{ var q=TICKERS.length?('?t='+TICKERS.join(',')+(PERIOD!=='5y'?'&p='+PERIOD:'')):'';
  history.replaceState(null,'','/compare'+q); }catch(_){} }

// ---- data ------------------------------------------------------------------
function msg(t){ var m=document.getElementById('cmp-msg'); m.textContent=t||''; m.style.display=t?'':'none'; }
function load(){
  if(TICKERS.length<2){ document.getElementById('cmp-out').style.display='none';
    msg(TICKERS.length?'Add at least one more ticker.':'Add two to four tickers to compare.'); return; }
  var id=++_req; msg('Loading '+TICKERS.join(', ')+'…');
  fetch('/api/compare?t='+encodeURIComponent(TICKERS.join(','))+'&period='+PERIOD)
    .then(function(r){return r.json();}).then(function(d){ if(id!==_req) return;
      if(!d.ok){ msg(d.error||'Could not compare those.'); document.getElementById('cmp-out').style.display='none'; return; }
      DATA=d; msg(''); document.getElementById('cmp-out').style.display=''; drawAll(); loadHoldings(id);
    }).catch(function(){ if(id===_req) msg('Failed to load. Try again.'); });
}
function loadHoldings(id){
  var box=document.getElementById('hold'); box.className='muted'; box.textContent='Loading holdings…';
  fetch('/api/compare/holdings?t='+encodeURIComponent(TICKERS.join(','))).then(function(r){return r.json();})
    .then(function(d){ if(id!==_req) return; HOLD=d; renderHoldings(); })
    .catch(function(){ if(id===_req) box.textContent='Holdings unavailable right now.'; });
}

// ---- charts ----------------------------------------------------------------
function lineChart(svgId, H, key, opts){
  var svg=document.getElementById(svgId); svg.innerHTML='';
  // a narrower drawing on phones keeps the axis text legible once scaled down
  W=(svg.parentNode.clientWidth||900)<640?520:900; if(W<900) H=Math.round(H*0.85);
  svg.setAttribute('viewBox','0 0 '+W+' '+H);
  var d=DATA, n=d.dates.length, y0=H-MB, y1=MT, log=!!opts.log;
  var tf=function(v){ return log?Math.log(v):v; };
  var lo=Infinity, hi=-Infinity;
  d.rows.forEach(function(r){ r[key].forEach(function(v){ var x=tf(v); if(x<lo)lo=x; if(x>hi)hi=x; }); });
  if(opts.zeroTop){ hi=Math.max(hi,0); }
  if(lo===hi){ lo-=1; hi+=1; } var pad=(hi-lo)*0.05; lo-=pad; if(!opts.zeroTop) hi+=pad; else hi+=pad*0.3;
  var X=function(i){ return ML+(n<2?0:i/(n-1)*(W-ML-MR)); };
  var Y=function(v){ return y0-(tf(v)-lo)/(hi-lo)*(y0-y1); };
  // gridlines + y labels
  var ticks=[];
  if(log){ var a=Math.exp(lo), b=Math.exp(hi), m=Math.pow(10,Math.floor(Math.log10(a)));
    for(var p=m; p<=b*1.0001; p*=10){ [1,2,5].forEach(function(k){ var v=p*k; if(v>=a&&v<=b) ticks.push(v); }); } }
  else { var st=niceStep(hi-lo,5); for(var v=Math.ceil(lo/st)*st; v<=hi+1e-9; v+=st) ticks.push(v); }
  ticks.forEach(function(v){ var yy=Y(v);
    svg.appendChild(svgEl('line',{x1:ML,y1:yy,x2:W-MR,y2:yy,stroke:'var(--border)','stroke-width':0.7,opacity:0.7}));
    var t=svgEl('text',{x:ML-6,y:yy+4,'text-anchor':'end'}); t.textContent=opts.fmt(v); svg.appendChild(t); });
  if(opts.base!=null){ var yb=Y(opts.base); svg.appendChild(svgEl('line',{x1:ML,y1:yb,x2:W-MR,y2:yb,stroke:'var(--muted)','stroke-width':0.8,'stroke-dasharray':'4 4'})); }
  // x labels
  [0,Math.floor((n-1)/2),n-1].forEach(function(i,k){ var t=svgEl('text',{x:X(i),y:H-6,'text-anchor':k===0?'start':(k===2?'end':'middle')});
    t.textContent=fdate(d.dates[i]); svg.appendChild(t); });
  // series (last drawn on top: draw in reverse so the first ticker is on top)
  d.rows.slice().reverse().forEach(function(r){
    var pts=r[key].map(function(v,i){ return X(i).toFixed(1)+','+Y(v).toFixed(1); }).join(' ');
    svg.appendChild(svgEl('polyline',{points:pts,fill:'none',stroke:col(r.ticker),'stroke-width':1.8,'stroke-linejoin':'round'})); });
  svg.appendChild(svgEl('line',{'class':'cx',x1:0,y1:y1,x2:0,y2:y0,stroke:'var(--muted)','stroke-width':1,style:'display:none'}));
  svg._geom={X:X,n:n,W:W};
  svg.onmousemove=function(e){ hoverAt(e, svg, opts); }; svg.onmouseleave=function(){ hoverOff(svg, opts); };
}
function hoverAt(e, svg, opts){
  W=svg._geom.W; var g=svg._geom, r=svg.getBoundingClientRect(), sx=r.width/W, vx=(e.clientX-r.left)/sx;
  var i=Math.round((vx-ML)/(W-ML-MR)*(g.n-1)); i=Math.max(0,Math.min(g.n-1,i));
  var cx=svg.querySelector('.cx'); cx.setAttribute('x1',g.X(i)); cx.setAttribute('x2',g.X(i)); cx.style.display='';
  document.getElementById(opts.ro).innerHTML=readout(i, opts);
}
function hoverOff(svg, opts){ var cx=svg.querySelector('.cx'); if(cx) cx.style.display='none';
  document.getElementById(opts.ro).innerHTML=readout(DATA.dates.length-1, opts); }
function readout(i, opts){ var d=DATA;
  return '<span>'+fdate(d.dates[i])+'</span> &nbsp; '+d.rows.map(function(r){
    return '<span style="white-space:nowrap">'+dot2(r.ticker)+' '+esc(r.ticker)+' <b>'+opts.fmtRo(r[opts.key][i])+'</b></span>'; }).join(' &nbsp; '); }
function dot2(t){ return '<i style="display:inline-block;width:8px;height:8px;border-radius:50%;background:'+col(t)+'"></i>'; }

function drawAll(){ if(!DATA) return; var d=DATA, log=document.getElementById('logsc').checked;
  var lim=d.limited_by?(' Starts when '+esc(d.limited_by)+' has data, so every line begins on the same day.'):'';
  document.getElementById('cmp-span').innerHTML='Shared history: '+fdate(d.start)+' to '+fdate(d.end)+
    ' ('+d.years.toFixed(1)+' years).'+lim;
  document.getElementById('leg-g').innerHTML=d.rows.map(function(r){ var last=r.growth[r.growth.length-1];
    return '<span><i style="background:'+col(r.ticker)+'"></i><b>'+esc(r.ticker)+'</b> '+money(last)+' '+pct(r.total_return,0)+'</span>'; }).join('');
  lineChart('ch-g',300,'growth',{log:log,base:10000,ro:'ro-g',key:'growth',
    fmt:function(v){ return v>=1000?'$'+(v/1000).toFixed(v>=100000?0:(v>=10000?0:1))+'k':'$'+Math.round(v); },
    fmtRo:function(v){ return money(v); }});
  lineChart('ch-d',190,'drawdown',{log:false,zeroTop:true,ro:'ro-d',key:'drawdown',
    fmt:function(v){ return Math.round(v*100)+'%'; }, fmtRo:function(v){ return (v*100).toFixed(1)+'%'; }});
  hoverOff(document.getElementById('ch-g'),{ro:'ro-g',key:'growth',fmtRo:function(v){return money(v);}});
  hoverOff(document.getElementById('ch-d'),{ro:'ro-d',key:'drawdown',fmtRo:function(v){return (v*100).toFixed(1)+'%';}});
  renderTables();
  renderPair();
}
function renderPair(){ var sec=document.getElementById('pair-sec'), pr=DATA.pair;
  if(!pr||!pr.z||!pr.z.some(function(v){return v!=null;})){ sec.style.display='none'; return; }
  sec.style.display='';
  var zn=pr.z_now, rich=zn>0?pr.a:pr.b, cheap=zn>0?pr.b:pr.a;
  document.getElementById('pair-read').innerHTML=zn==null?'':('<b>'+esc(rich)+'</b> is '+Math.abs(zn).toFixed(1)+
    ' standard deviations rich relative to <b>'+esc(cheap)+'</b> versus the past year'+(Math.abs(zn)>=2?' (stretched).':'.'));
  var svg=document.getElementById('ch-z'); svg.innerHTML=''; var Wz=(svg.parentNode.clientWidth||900)<640?520:900, H=170;
  svg.setAttribute('viewBox','0 0 '+Wz+' '+H);
  var n=pr.z.length, lo=-3.5, hi=3.5; pr.z.forEach(function(v){ if(v!=null){ lo=Math.min(lo,v-0.3); hi=Math.max(hi,v+0.3); } });
  var X=function(i){ return ML+(n<2?0:i/(n-1)*(Wz-ML-MR)); }, Y=function(v){ return (H-MB)-(v-lo)/(hi-lo)*((H-MB)-MT); };
  [-2,0,2].forEach(function(v){ svg.appendChild(svgEl('line',{x1:ML,y1:Y(v),x2:Wz-MR,y2:Y(v),stroke:v?'var(--down)':'var(--muted)','stroke-width':0.8,'stroke-dasharray':v?'4 4':'',opacity:v?0.6:0.8}));
    var t=svgEl('text',{x:ML-6,y:Y(v)+4,'text-anchor':'end'}); t.textContent=(v>0?'+':'')+v+'σ'; svg.appendChild(t); });
  var pts=[]; pr.z.forEach(function(v,i){ if(v!=null) pts.push(X(i).toFixed(1)+','+Y(v).toFixed(1)); });
  svg.appendChild(svgEl('polyline',{points:pts.join(' '),fill:'none',stroke:'var(--accent)','stroke-width':1.6}));
  [0,Math.floor((n-1)/2),n-1].forEach(function(i,k){ var t=svgEl('text',{x:X(i),y:H-6,'text-anchor':k===0?'start':(k===2?'end':'middle')});
    t.textContent=fdate(pr.dates[i]); svg.appendChild(t); });
}
function loadWlPairs(){ fetch('/api/pairs').then(function(r){return r.json();}).then(function(d){
    var box=document.getElementById('wl-pairs-body');
    if(!d.ok){ box.textContent='Not available until the watchlist history is cached.'; return; }
    var bt=d.backtest, pairs=(d.pairs||[]).filter(function(x){return Math.abs(x.z)>=1.5;}).slice(0,8);
    var chips=pairs.length?('<div class="pair-list">'+pairs.map(function(x){
      return '<button class="pair-chip" onclick="preset(\''+esc(x.rich)+','+esc(x.cheap)+'\')">'+esc(x.rich)+' / '+esc(x.cheap)+
        ' <span class="z '+(Math.abs(x.z)>=2?'down':'')+'">'+Math.abs(x.z).toFixed(1)+'σ</span></button>'; }).join('')+'</div>')
      :'<p>No same-sector pairs are unusually far apart right now.</p>';
    var track='';
    if(bt&&bt.trades){
      var good=bt.mean>0;
      track='<p class="cmp-note" style="font-size:14px;color:var(--ink-2)"><b>How this has worked here:</b> testing the classic pairs rule '+
        '(Gatev, Goetzmann &amp; Rouwenhorst, 2006) on this watchlist over the past '+bt.years.toFixed(0)+' years: '+bt.trades+' trades, '+
        '<span class="'+(good?'up':'down')+'">'+(bt.mean>=0?'+':'')+(bt.mean*100).toFixed(1)+'% per trade on average</span> '+
        '(median '+(bt.median>=0?'+':'')+(bt.median*100).toFixed(1)+'%), '+Math.round(bt.win_rate*100)+'% winners, and only '+
        Math.round(bt.converged*100)+'% of spreads closed back within six months. '+
        (good?'A thin edge before trading costs and short-borrow fees.':'On these trending names, stretched pairs have tended to keep drifting rather than snap back, so treat this list as "what has moved apart", not as trades.')+'</p>';
    }
    box.className=''; box.innerHTML='<p class="cmp-note" style="margin-top:0">Same-sector stocks that have tracked each other over the past year, '+
      'sorted by how far apart they are now (click one to compare).</p>'+chips+track;
  }).catch(function(){ document.getElementById('wl-pairs-body').textContent='Pairs unavailable right now.'; }); }
var _rsz=null; window.addEventListener('resize',function(){ clearTimeout(_rsz); _rsz=setTimeout(drawAll,150); });

// ---- tables ----------------------------------------------------------------
function tk(t){ return '<span class="tk">'+dot(t)+esc(t)+'</span>'; }
function table(head, rows){ return '<table class="cmp-t"><thead><tr>'+head.map(function(h){return '<th>'+h+'</th>';}).join('')+
  '</tr></thead><tbody>'+rows.map(function(r){ return '<tr>'+r.map(function(c){return '<td>'+c+'</td>';}).join('')+'</tr>'; }).join('')+'</tbody></table>'; }
function renderTables(){ var d=DATA;
  var W_=['1M','3M','6M','YTD','1Y','3Y','5Y'];
  document.getElementById('t-ret').innerHTML=table(['']
    .concat(W_), d.rows.map(function(r){ return [tk(r.ticker)].concat(W_.map(function(w){ return pct(r.returns[w]); })); }));
  var span={'1y':'1 year','3y':'3 years','5y':'5 years'}[PERIOD];
  document.getElementById('risk-h').textContent='Risk and return, '+
    ((PERIOD==='max'||d.limited_by)?'over the shared '+d.years.toFixed(1)+' years':'last '+span);
  document.getElementById('t-risk').innerHTML=table(['','Total','Per year','Volatility','Max drawdown','Sharpe','Sortino','Beta','Alpha / yr'],
    d.rows.map(function(r){
      var a=r.alpha==null?'<span class="mu">n/a</span>':(pct(r.alpha)+(r.alpha_significant?'':' <span class="mu">noise</span>'));
      return [tk(r.ticker), pct(r.total_return,0), pct(r.cagr), pct(r.vol,0,false), pct(r.max_drawdown,0),
              num(r.sharpe), num(r.sortino), num(r.beta), a]; }));
  var cells=d.tickers.map(function(a,i){ return [tk(a)].concat(d.tickers.map(function(b,j){ var v=d.correlation[i][j];
    return v==null?'<span class="mu">n/a</span>':(i===j?'<span class="mu">1.00</span>':v.toFixed(2)); })); });
  document.getElementById('t-corr').innerHTML=table([''].concat(d.tickers.map(esc)), cells);
  // profile: only the columns at least one ticker has a value for
  var P=d.profiles||[], mu='<span class="mu">-</span>';
  var cols=[['Type',function(p){return p.type?esc(p.type):null;}],
    ['Sector',function(p){return p.sector?esc(p.sector):null;}],
    ['Market cap',function(p){return p.market_cap==null?null:big(p.market_cap);}],
    ['P/E',function(p){return p.pe==null?null:p.pe.toFixed(1);}],
    ['Dividend yield',function(p){return p.dividend_yield==null?null:(p.dividend_yield*100).toFixed(2)+'%';}],
    ['Leverage',function(p){return p.leverage?p.leverage+'x daily':null;}],
    ['Expense ratio',function(p){return p.expense_ratio==null?null:(p.expense_ratio*100).toFixed(2)+'%';}]]
    .filter(function(c){ return P.some(function(p){ return c[1](p)!=null; }); });
  document.getElementById('t-prof').innerHTML=table(['',''].concat(cols.map(function(c){return c[0];})),
    P.map(function(p){ return [tk(p.ticker), '<span class="pn">'+esc(p.name||'')+'</span>']
      .concat(cols.map(function(c){ var v=c[1](p); return v==null?mu:v; })); }));
}
function renderHoldings(){ var d=HOLD, box=document.getElementById('hold');
  if(!d||!d.ok){ box.textContent='Holdings unavailable right now.'; return; }
  var sec=box.closest('section');
  if(!d.funds.some(function(f){ return f.kind!=='stock'; })){ sec.style.display='none'; return; }
  sec.style.display='';
  box.className='';
  var cards=d.funds.map(function(f){
    var mx=Math.max.apply(null,f.holdings.map(function(h){return h.weight;}).concat([0.0001]));
    var rows=f.available?f.holdings.map(function(h){ return '<div class="hrow"><span>'+esc(h.underlying)+'</span>'+
      '<span class="bar"><b style="width:'+(h.weight/mx*100).toFixed(1)+'%;background:'+col(f.ticker)+'"></b></span>'+
      '<span class="w">'+(h.weight*100).toFixed(1)+'%</span></div>'; }).join('')
      :'<div class="muted" style="font-size:13px">Holdings not available for this fund.</div>';
    return '<div class="hold-card"><h3>'+dot(f.ticker)+esc(f.ticker)+'</h3><div class="hn">'+esc(f.note)+'</div>'+rows+'</div>'; }).join('');
  var anyFund=d.funds.some(function(f){ return f.kind!=='stock'; });
  var ov='';
  if(anyFund){
    var ts=d.funds.map(function(f){return f.ticker;});
    ov='<h3 style="font-size:16px;font-weight:500;margin:18px 0 8px">Holdings overlap</h3><div class="cmp-tw">'+
      table([''].concat(ts.map(esc)), ts.map(function(a,i){ return [tk(a)].concat(ts.map(function(b,j){
        return i===j?'<span class="mu">-</span>':(d.overlap[i][j]*100).toFixed(0)+'%'; })); }))+'</div>'+
      '<p class="cmp-note">Share of weight two funds hold in the same companies. Funds only report their top holdings here, '+
      'so the true overlap can be higher. A leveraged fund\'s overlap is of its basket, before the leverage.</p>';
  }
  box.innerHTML='<div class="hold-grid">'+cards+'</div>'+ov;
}

// ---- search ----------------------------------------------------------------
var _res=[], _tmr=null;
function csearch(){ clearTimeout(_tmr); var q=document.getElementById('ctk').value.trim(), s=document.getElementById('csug');
  if(!q){ s.style.display='none'; return; }
  _tmr=setTimeout(function(){ fetch('/api/search?q='+encodeURIComponent(q)).then(function(r){return r.json();}).then(function(d){
    _res=(d.results||[]).slice(0,8); if(!_res.length){ s.style.display='none'; return; }
    s.innerHTML=_res.map(function(x,i){ return '<div class="sug" onclick="pick('+i+')"><b>'+esc(x.symbol)+'</b> <span>'+esc(x.name||'')+'</span></div>'; }).join('');
    s.style.display='block'; }).catch(function(){ s.style.display='none'; }); },180); }
function pick(i){ var x=_res[i]; if(x){ document.getElementById('ctk').value=''; document.getElementById('csug').style.display='none'; addT(x.symbol); } }
function ckey(e){ var inp=document.getElementById('ctk');
  if(e.key==='Enter'){ e.preventDefault(); inp.value.split(/[\s,;]+/).forEach(addT); inp.value=''; document.getElementById('csug').style.display='none'; }
  if(e.key==='Escape') document.getElementById('csug').style.display='none';
  if(e.key==='Backspace' && !inp.value && TICKERS.length) removeT(TICKERS[TICKERS.length-1]); }
document.addEventListener('click', function(e){ if(!e.target.closest('.addwrap')) document.getElementById('csug').style.display='none'; });
document.getElementById('perseg').addEventListener('click', function(e){ var b=e.target.closest('button'); if(!b) return;
  [].forEach.call(this.querySelectorAll('button'),function(x){x.classList.toggle('on',x===b);}); PERIOD=b.dataset.p; syncUrl(); load(); });
(function(){
  var q=new URLSearchParams(location.search), p=q.get('p');
  if(p && ['1y','3y','5y','max'].indexOf(p)>=0){ PERIOD=p;
    [].forEach.call(document.querySelectorAll('#perseg button'),function(x){x.classList.toggle('on',x.dataset.p===p);}); }
  TICKERS=(INIT||[]).slice(0,4); renderChips(); load(); loadWlPairs();
  if(TICKERS.length<4) document.getElementById('ctk').focus();
})();
"""
