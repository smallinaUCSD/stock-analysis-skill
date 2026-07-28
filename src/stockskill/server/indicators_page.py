"""Technical-indicators page: plot price + Bollinger Bands + SMAs, RSI and MACD.

Self-contained. Data comes from GET /api/indicators/<ticker>; the client draws
three stacked SVG panels with a shared x-axis and a hover readout.
"""

from __future__ import annotations

import html

from ..dashboard.render import _CSS


def indicators_html(initial: str = "") -> str:
    init = html.escape(initial.upper())
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Technical indicators</title><style>" + _CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Technical indicators</h1>"
            "<span class=\"sub\" style=\"margin:0\">RSI · MACD · Bollinger Bands · SMAs</span>"
            "<button class=\"h-close\" onclick=\"window.close()\" title=\"Close tab\" "
            "style=\"margin-left:auto\">✕</button></header>"
            "<p style=\"font-size:12px;margin:-6px 0 12px\">"
            "<a class=\"h-back\" href=\"/\" onclick=\"return goBack(event)\">← back to watchlist</a></p>"
            + _CONTROLS +
            "<div id=\"ind-msg\" class=\"muted\" style=\"font-size:13px;margin:8px 0\"></div>"
            "<div id=\"readout\" class=\"ind-readout\"></div>"
            "<div id=\"panels\">"
            "<svg id=\"p-price\" class=\"ind-svg\" viewBox=\"0 0 900 320\" preserveAspectRatio=\"xMidYMid meet\"></svg>"
            "<svg id=\"p-rsi\" class=\"ind-svg\" viewBox=\"0 0 900 130\" preserveAspectRatio=\"xMidYMid meet\"></svg>"
            "<svg id=\"p-macd\" class=\"ind-svg\" viewBox=\"0 0 900 150\" preserveAspectRatio=\"xMidYMid meet\"></svg>"
            "</div>"
            "<p class=\"muted\" style=\"font-size:11.5px;margin-top:12px\">"
            "Indicator states, not advice. Free data (yfinance) may be delayed. "
            "All series computed by tested Python.</p>"
            "</div><script>var INIT=\"" + init + "\";\n" + _JS + "</script></body></html>")


_CONTROLS = """
<div class="ind-bar">
  <div class="addwrap" style="flex:0 1 260px">
    <input id="itk" placeholder="Ticker (e.g. NVDA)" autocomplete="off"
      oninput="isearch()" onkeydown="ikey(event)">
    <div id="isug" class="addsug"></div>
  </div>
  <button class="tbtn add" onclick="loadInd()">Plot</button>
  <span class="seg" id="perseg">
    <button data-p="3mo">3M</button><button data-p="6mo">6M</button>
    <button data-p="1y" class="on">1Y</button><button data-p="2y">2Y</button>
    <button data-p="5y">5Y</button>
  </span>
  <label class="ind-chk"><input type="checkbox" id="c-bb" checked onchange="redraw()"> Bollinger</label>
  <label class="ind-chk"><input type="checkbox" id="c-sma" checked onchange="redraw()"> SMA 20/50</label>
  <label class="ind-chk"><input type="checkbox" id="c-rsi" checked onchange="redraw()"> RSI</label>
  <label class="ind-chk"><input type="checkbox" id="c-macd" checked onchange="redraw()"> MACD</label>
</div>
"""

_EXTRA_CSS = """
.ind-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}
.ind-bar #itk{width:100%;padding:8px 11px;border-radius:9px;border:1px solid var(--border);
  background:var(--surface);color:var(--ink);font-size:13px}
.ind-bar .seg button{font-size:12px;padding:6px 11px;border:none;background:var(--surface);
  color:var(--muted);cursor:pointer}
.ind-bar .seg button.on{background:var(--accent);color:#fff;font-weight:650}
.ind-chk{font-size:12.5px;color:var(--muted);display:flex;align-items:center;gap:4px}
.h-back{color:var(--muted);text-decoration:none}.h-back:hover{color:var(--ink);text-decoration:underline}
.h-close{width:34px;height:34px;border:1px solid var(--border);border-radius:50%;background:var(--surface-2);
  color:var(--ink);font-size:17px;cursor:pointer;display:flex;align-items:center;justify-content:center}
.h-close:hover{background:var(--crit);color:#fff;border-color:transparent}
#panels{display:flex;flex-direction:column;gap:6px}
.ind-svg{width:100%;height:auto;background:var(--surface);border:1px solid var(--border);border-radius:10px}
.ind-svg text{fill:var(--muted);font-size:10px;font-family:inherit}
.ind-readout{font-size:12.5px;min-height:20px;font-variant-numeric:tabular-nums;margin-bottom:4px}
.ind-readout b{color:var(--ink)} .ind-readout .k{color:var(--muted)}
.addsug{display:none;position:absolute;z-index:60;left:0;right:0;top:calc(100% + 4px);
  background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden;
  box-shadow:0 10px 30px rgba(0,0,0,.25)}
.sug{padding:7px 11px;font-size:13px;cursor:pointer;display:flex;gap:8px;align-items:baseline}
.sug:hover{background:var(--surface-2)} .sug b{color:var(--ink)} .sug span{color:var(--muted);font-size:11.5px}
"""

# --- client: fetch + draw the three panels, shared x-axis, hover readout ---
_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){ try{window.opener.focus();}catch(_){}; window.close(); }
  else location.href='/'; return false; }
var W=900, ML=52, MR=12, MT=10, PH=320, RH=130, MH=150, MB=18;
var DATA=null, PERIOD='1y';
var C={close:'var(--ink)', sma20:'#e0a800', sma50:'#8a63d2', bb:'var(--muted)',
       up:'var(--up)', down:'var(--down)', rsi:'#3b82f6', macd:'#3b82f6', sig:'#e0a800'};

function _fmt(v,d){ return v==null?'—':'$'+Number(v).toLocaleString(undefined,{minimumFractionDigits:d||2,maximumFractionDigits:d||2}); }
function _date(iso){ var d=new Date(iso); return (d.getMonth()+1)+'/'+d.getDate()+'/'+String(d.getFullYear()).slice(2); }
function L(pts){ return pts.filter(function(p){return p;}).map(function(p){return p[0].toFixed(1)+','+p[1].toFixed(1);}).join(' '); }
function el(tag,attr){ var e=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for(var k in attr) e.setAttribute(k,attr[k]); return e; }

function minmax(arrs){ var lo=Infinity,hi=-Infinity;
  arrs.forEach(function(a){ a.forEach(function(v){ if(v==null||isNaN(v))return; if(v<lo)lo=v; if(v>hi)hi=v; }); });
  if(lo===Infinity){lo=0;hi=1;} if(lo===hi){lo-=1;hi+=1;} return [lo,hi]; }

function xAt(i,n){ return ML + (n<2?0:i/(n-1)*(W-ML-MR)); }

function drawPrice(){
  var svg=document.getElementById('p-price'); svg.innerHTML='';
  var d=DATA, n=d.close.length, y0=PH-MB, y1=MT;
  var showBB=document.getElementById('c-bb').checked, showSMA=document.getElementById('c-sma').checked;
  var series=[d.close]; if(showBB){series.push(d.bb_upper,d.bb_lower);} if(showSMA){series.push(d.sma20,d.sma50);}
  var mm=minmax(series), lo=mm[0], hi=mm[1], pad=(hi-lo)*0.05; lo-=pad; hi+=pad;
  var Y=function(v){ return y0-(v-lo)/(hi-lo)*(y0-y1); };
  // y grid + labels
  var step=niceStep(hi-lo,5);
  for(var g=Math.ceil(lo/step)*step; g<=hi; g+=step){ var yy=Y(g);
    svg.appendChild(el('line',{x1:ML,y1:yy,x2:W-MR,y2:yy,stroke:'var(--border)','stroke-width':0.5,opacity:0.5}));
    var t=el('text',{x:ML-5,y:yy+3,'text-anchor':'end'}); t.textContent='$'+(g>=1000?(g/1000).toFixed(1)+'k':g.toFixed(0)); svg.appendChild(t); }
  // Bollinger shaded band + lines
  if(showBB){
    var top=[],bot=[]; for(var i=0;i<n;i++){ if(d.bb_upper[i]!=null){top.push(xAt(i,n).toFixed(1)+','+Y(d.bb_upper[i]).toFixed(1));} }
    for(var j=n-1;j>=0;j--){ if(d.bb_lower[j]!=null){bot.push(xAt(j,n).toFixed(1)+','+Y(d.bb_lower[j]).toFixed(1));} }
    if(top.length) svg.appendChild(el('polygon',{points:top.concat(bot).join(' '),fill:C.bb,opacity:0.08}));
    [['bb_upper'],['bb_lower']].forEach(function(k){ var p=[]; for(var i=0;i<n;i++){ if(d[k[0]][i]!=null)p.push([xAt(i,n),Y(d[k[0]][i])]); }
      svg.appendChild(el('polyline',{points:L(p),fill:'none',stroke:C.bb,'stroke-width':1,'stroke-dasharray':'3 3',opacity:0.7})); });
  }
  if(showSMA){ [['sma20',C.sma20],['sma50',C.sma50]].forEach(function(k){ var p=[]; for(var i=0;i<n;i++){ if(d[k[0]][i]!=null)p.push([xAt(i,n),Y(d[k[0]][i])]); }
    svg.appendChild(el('polyline',{points:L(p),fill:'none',stroke:k[1],'stroke-width':1.3})); }); }
  var pc=[]; for(var i=0;i<n;i++) pc.push([xAt(i,n),Y(d.close[i])]);
  svg.appendChild(el('polyline',{points:L(pc),fill:'none',stroke:C.close,'stroke-width':1.6}));
  crosshair(svg,'cx-price',y1,y0);
  legend(svg, showBB, showSMA);
}
function legend(svg,bb,sma){
  var items=[['Close',C.close]]; if(sma){items.push(['SMA20',C.sma20],['SMA50',C.sma50]);} if(bb){items.push(['Bollinger',C.bb]);}
  var x=ML+4; items.forEach(function(it){ svg.appendChild(el('line',{x1:x,y1:MT+6,x2:x+14,y2:MT+6,stroke:it[1],'stroke-width':2}));
    var t=el('text',{x:x+18,y:MT+9}); t.textContent=it[0]; svg.appendChild(t); x+=18+it[0].length*6.2+14; });
}
function drawRSI(){
  var svg=document.getElementById('p-rsi'); svg.innerHTML='';
  if(!document.getElementById('c-rsi').checked){ svg.style.display='none'; return; } svg.style.display='';
  var d=DATA, n=d.close.length, y0=RH-MB, y1=MT, Y=function(v){ return y0-(v/100)*(y0-y1); };
  [30,50,70].forEach(function(g){ var yy=Y(g); var dash=g===50?'2 4':'4 4';
    svg.appendChild(el('line',{x1:ML,y1:yy,x2:W-MR,y2:yy,stroke:'var(--border)','stroke-width':0.7,'stroke-dasharray':dash}));
    var t=el('text',{x:ML-5,y:yy+3,'text-anchor':'end'}); t.textContent=g; svg.appendChild(t); });
  svg.appendChild(el('rect',{x:ML,y:Y(70),width:W-ML-MR,height:Y(30)-Y(70),fill:C.rsi,opacity:0.05}));
  var p=[]; for(var i=0;i<n;i++){ if(d.rsi[i]!=null)p.push([xAt(i,n),Y(d.rsi[i])]); }
  svg.appendChild(el('polyline',{points:L(p),fill:'none',stroke:C.rsi,'stroke-width':1.4}));
  var lt=el('text',{x:ML+4,y:MT+10}); lt.textContent='RSI(14)'; svg.appendChild(lt);
  crosshair(svg,'cx-rsi',y1,y0);
}
function drawMACD(){
  var svg=document.getElementById('p-macd'); svg.innerHTML='';
  if(!document.getElementById('c-macd').checked){ svg.style.display='none'; return; } svg.style.display='';
  var d=DATA, n=d.close.length, y0=MH-MB, y1=MT;
  var mm=minmax([d.macd,d.signal,d.hist]), lo=mm[0], hi=mm[1]; var Y=function(v){ return y0-(v-lo)/(hi-lo)*(y0-y1); };
  var yz=Y(0); svg.appendChild(el('line',{x1:ML,y1:yz,x2:W-MR,y2:yz,stroke:'var(--border)','stroke-width':0.7}));
  var bw=Math.max(1,(W-ML-MR)/n*0.7);
  for(var i=0;i<n;i++){ if(d.hist[i]==null)continue; var x=xAt(i,n), yv=Y(d.hist[i]);
    svg.appendChild(el('rect',{x:x-bw/2,y:Math.min(yz,yv),width:bw,height:Math.abs(yv-yz),
      fill:d.hist[i]>=0?C.up:C.down,opacity:0.5})); }
  [['macd',C.macd],['signal',C.sig]].forEach(function(k){ var p=[]; for(var i=0;i<n;i++){ if(d[k[0]][i]!=null)p.push([xAt(i,n),Y(d[k[0]][i])]); }
    svg.appendChild(el('polyline',{points:L(p),fill:'none',stroke:k[1],'stroke-width':1.3})); });
  var lt=el('text',{x:ML+4,y:MT+10}); lt.textContent='MACD(12,26,9)'; svg.appendChild(lt);
  // x date labels on the bottom panel
  [0,Math.floor((n-1)/2),n-1].forEach(function(idx,ki){ var anc=ki===0?'start':(ki===2?'end':'middle');
    var t=el('text',{x:xAt(idx,n),y:MH-5,'text-anchor':anc}); t.textContent=_date(d.dates[idx]); svg.appendChild(t); });
  crosshair(svg,'cx-macd',y1,y0);
}
function crosshair(svg,id,y1,y0){ svg.appendChild(el('line',{id:id,x1:0,y1:y1,x2:0,y2:y0,
  stroke:'var(--muted)','stroke-width':1,opacity:0.6,style:'display:none'})); }

function niceStep(range,target){ var raw=(range||1)/Math.max(1,target); var p=Math.pow(10,Math.floor(Math.log10(raw)));
  var n=raw/p; var s=n<1.5?1:(n<3?2:(n<7?5:10)); return s*p; }

function redraw(){ if(!DATA)return; drawPrice(); drawRSI(); drawMACD(); }

function hover(ev){ if(!DATA)return; var svg=document.getElementById('p-price'); var r=svg.getBoundingClientRect();
  var sx=r.width/W; var vx=(ev.clientX-r.left)/sx; var n=DATA.close.length;
  var frac=(vx-ML)/(W-ML-MR); var i=Math.round(frac*(n-1)); if(i<0)i=0; if(i>n-1)i=n-1;
  var x=xAt(i,n);
  ['cx-price','cx-rsi','cx-macd'].forEach(function(id){ var c=document.getElementById(id); if(c){ c.setAttribute('x1',x); c.setAttribute('x2',x); c.style.display=''; } });
  var d=DATA; var ro=document.getElementById('readout');
  ro.innerHTML='<span class="k">'+_date(d.dates[i])+'</span> &nbsp; <b>'+_fmt(d.close[i])+'</b>'
    +' &nbsp; <span class="k">RSI</span> '+(d.rsi[i]==null?'—':d.rsi[i].toFixed(0))
    +' &nbsp; <span class="k">MACD</span> '+(d.macd[i]==null?'—':d.macd[i].toFixed(2))
    +' / '+(d.signal[i]==null?'—':d.signal[i].toFixed(2));
}
function hoverOff(){ ['cx-price','cx-rsi','cx-macd'].forEach(function(id){ var c=document.getElementById(id); if(c)c.style.display='none'; });
  if(DATA){ var i=DATA.close.length-1; var ro=document.getElementById('readout');
    ro.innerHTML='<span class="k">latest '+_date(DATA.dates[i])+'</span> &nbsp; <b>'+_fmt(DATA.close[i])+'</b>'; } }

function loadInd(){ var t=(document.getElementById('itk').value||'').trim().toUpperCase(); if(!t)return;
  document.getElementById('ind-msg').textContent='Loading '+t+'…';
  document.getElementById('isug').style.display='none';
  fetch('/api/indicators/'+encodeURIComponent(t)+'?period='+PERIOD).then(function(r){return r.json();}).then(function(d){
    if(d.error){ document.getElementById('ind-msg').textContent=d.error; DATA=null; return; }
    DATA=d; document.getElementById('ind-msg').textContent=''; redraw(); hoverOff();
  }).catch(function(){ document.getElementById('ind-msg').textContent='Failed to load.'; });
}

// period segment
document.getElementById('perseg').addEventListener('click', function(e){ var b=e.target.closest('button'); if(!b)return;
  [].forEach.call(this.querySelectorAll('button'),function(x){x.classList.toggle('on',x===b);}); PERIOD=b.dataset.p; loadInd(); });

// ticker autocomplete (reuse /api/search)
var _res=[], _tmr=null;
function isearch(){ clearTimeout(_tmr); var q=document.getElementById('itk').value.trim(); var s=document.getElementById('isug');
  if(!q){ s.style.display='none'; return; }
  _tmr=setTimeout(function(){ fetch('/api/search?q='+encodeURIComponent(q)).then(function(r){return r.json();}).then(function(d){
    _res=(d.results||[]).slice(0,8); if(!_res.length){ s.style.display='none'; return; }
    s.innerHTML=_res.map(function(x,i){ return '<div class="sug" onclick="pick('+i+')"><b>'+x.symbol+'</b> <span>'+(x.name||'').replace(/</g,'&lt;')+'</span></div>'; }).join('');
    s.style.display='block'; }).catch(function(){ s.style.display='none'; }); },180); }
function pick(i){ var x=_res[i]; if(x){ document.getElementById('itk').value=x.symbol; document.getElementById('isug').style.display='none'; loadInd(); } }
function ikey(e){ if(e.key==='Enter'){ e.preventDefault(); loadInd(); } if(e.key==='Escape') document.getElementById('isug').style.display='none'; }
document.addEventListener('click', function(e){ if(!e.target.closest('.addwrap')) document.getElementById('isug').style.display='none'; });

document.getElementById('panels').addEventListener('mousemove', hover);
document.getElementById('panels').addEventListener('mouseleave', hoverOff);
(function(){ var t=localStorage.getItem('wl_theme'); if(t) document.documentElement.setAttribute('data-theme',t);
  if(INIT){ document.getElementById('itk').value=INIT; loadInd(); } })();
"""
