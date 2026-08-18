"""Technical-indicators page: price + Bollinger/SMAs/Ichimoku, and RSI, Stochastic,
MACD, ADX, ATR and OBV subpanels.

Self-contained. Data comes from GET /api/indicators/<ticker>; the client draws
stacked SVG panels with a shared x-axis and a hover readout.
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
            "<span class=\"sub\" style=\"margin:0\">Bollinger · Ichimoku · RSI · Stochastic · MACD · ADX · ATR · OBV</span>"
            "<button class=\"h-close\" onclick=\"window.close()\" title=\"Close tab\" "
            "style=\"margin-left:auto\">✕</button></header>"
            "<p style=\"font-size:12px;margin:-6px 0 12px\">"
            "<a class=\"h-back\" href=\"/\" onclick=\"return goBack(event)\">← back to watchlist</a></p>"
            + _CONTROLS +
            "<div id=\"ind-msg\" class=\"muted\" style=\"font-size:13px;margin:8px 0\"></div>"
            "<div id=\"readout\" class=\"ind-readout\"></div>"
            "<div id=\"panels\">"
            "<svg id=\"p-price\" class=\"ind-svg\" viewBox=\"0 0 900 330\" preserveAspectRatio=\"xMidYMid meet\"></svg>"
            "<svg id=\"p-rsi\" class=\"ind-svg\" viewBox=\"0 0 900 120\" preserveAspectRatio=\"xMidYMid meet\"></svg>"
            "<svg id=\"p-stoch\" class=\"ind-svg\" viewBox=\"0 0 900 120\" preserveAspectRatio=\"xMidYMid meet\"></svg>"
            "<svg id=\"p-macd\" class=\"ind-svg\" viewBox=\"0 0 900 150\" preserveAspectRatio=\"xMidYMid meet\"></svg>"
            "<svg id=\"p-adx\" class=\"ind-svg\" viewBox=\"0 0 900 120\" preserveAspectRatio=\"xMidYMid meet\"></svg>"
            "<svg id=\"p-atr\" class=\"ind-svg\" viewBox=\"0 0 900 110\" preserveAspectRatio=\"xMidYMid meet\"></svg>"
            "<svg id=\"p-obv\" class=\"ind-svg\" viewBox=\"0 0 900 120\" preserveAspectRatio=\"xMidYMid meet\"></svg>"
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
  <button class="tbtn" onclick="loadInd()">Plot</button>
  <span class="seg" id="perseg">
    <button data-p="3mo">3M</button><button data-p="6mo">6M</button>
    <button data-p="1y" class="on">1Y</button><button data-p="2y">2Y</button>
    <button data-p="5y">5Y</button>
  </span>
</div>
<div class="ind-bar" style="gap:6px 14px">
  <span class="ind-grp">Overlays:</span>
  <label class="ind-chk"><input type="checkbox" id="c-bb" checked onchange="redraw()"> Bollinger</label>
  <label class="ind-chk"><input type="checkbox" id="c-sma" checked onchange="redraw()"> SMA 20/50</label>
  <label class="ind-chk"><input type="checkbox" id="c-ich" onchange="redraw()"> Ichimoku</label>
  <span class="ind-grp">Panels:</span>
  <label class="ind-chk"><input type="checkbox" id="c-rsi" checked onchange="redraw()"> RSI</label>
  <label class="ind-chk"><input type="checkbox" id="c-stoch" onchange="redraw()"> Stochastic</label>
  <label class="ind-chk"><input type="checkbox" id="c-macd" checked onchange="redraw()"> MACD</label>
  <label class="ind-chk"><input type="checkbox" id="c-adx" onchange="redraw()"> ADX</label>
  <label class="ind-chk"><input type="checkbox" id="c-atr" onchange="redraw()"> ATR</label>
  <label class="ind-chk"><input type="checkbox" id="c-obv" onchange="redraw()"> OBV</label>
</div>
"""

_EXTRA_CSS = """
.ind-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px}
.ind-bar #itk{width:100%;padding:8px 11px;border-radius:9px;border:1px solid var(--border);
  background:var(--surface);color:var(--ink);font-size:13px}
.ind-bar .seg{display:inline-flex;border:1px solid var(--border);border-radius:9px;overflow:hidden}
.ind-bar .seg button{font:600 12px inherit;padding:7px 12px;border:none;background:var(--surface);
  color:var(--muted);cursor:pointer}
.ind-bar .seg button:hover{color:var(--ink)}
.ind-bar .seg button.on{background:var(--accent);color:#fff}
.ind-bar .tbtn{font:650 12.5px inherit;line-height:1;padding:8px 15px;border-radius:9px;cursor:pointer;
  background:var(--accent);color:#fff;border:1px solid transparent}
.ind-bar .tbtn:hover{filter:brightness(1.08)}
.ind-grp{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
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

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){ try{window.opener.focus();}catch(_){}; window.close(); }
  else location.href='/'; return false; }
var W=900, ML=52, MR=12, MT=10, PH=330, MB=18;
var DATA=null, PERIOD='1y';
var C={close:'var(--ink)', sma20:'#e0a800', sma50:'#8a63d2', bb:'var(--muted)',
       tenkan:'#3b82f6', kijun:'#d9534f', up:'var(--up)', down:'var(--down)',
       rsi:'#3b82f6', k:'#3b82f6', d:'#e0a800', macd:'#3b82f6', sig:'#e0a800',
       adx:'#8a63d2', pdi:'var(--up)', mdi:'var(--down)', atr:'#14b8a6', obv:'#3b82f6'};

function on(k){ var e=document.getElementById('c-'+k); return !!(e && e.checked); }
function _fmt(v,d){ return v==null?'-':'$'+Number(v).toLocaleString(undefined,{minimumFractionDigits:d||2,maximumFractionDigits:d||2}); }
function _big(v){ if(v==null)return '-'; var a=Math.abs(v); var s=v<0?'-':'';
  if(a>=1e9)return s+(a/1e9).toFixed(1)+'B'; if(a>=1e6)return s+(a/1e6).toFixed(1)+'M'; if(a>=1e3)return s+(a/1e3).toFixed(1)+'k'; return ''+Math.round(v); }
function num(v,dp){ return v==null?'-':Number(v).toFixed(dp); }
function _date(iso){ var d=new Date(iso); return (d.getMonth()+1)+'/'+d.getDate()+'/'+String(d.getFullYear()).slice(2); }
function L(pts){ return pts.filter(function(p){return p;}).map(function(p){return p[0].toFixed(1)+','+p[1].toFixed(1);}).join(' '); }
function el(tag,attr){ var e=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for(var k in attr) e.setAttribute(k,attr[k]); return e; }
function minmax(arrs){ var lo=Infinity,hi=-Infinity;
  arrs.forEach(function(a){ (a||[]).forEach(function(v){ if(v==null||isNaN(v))return; if(v<lo)lo=v; if(v>hi)hi=v; }); });
  if(lo===Infinity){lo=0;hi=1;} if(lo===hi){lo-=1;hi+=1;} return [lo,hi]; }
function xAt(i,n){ return ML + (n<2?0:i/(n-1)*(W-ML-MR)); }
function crosshair(svg,id,y1,y0){ svg.appendChild(el('line',{id:id,x1:0,y1:y1,x2:0,y2:y0,
  stroke:'var(--muted)','stroke-width':1,opacity:0.6,style:'display:none'})); }
function niceStep(range,target){ var raw=(range||1)/Math.max(1,target); var p=Math.pow(10,Math.floor(Math.log10(raw)));
  var n=raw/p; var s=n<1.5?1:(n<3?2:(n<7?5:10)); return s*p; }
function polyline(svg,data,n,Y,color,width,dash){ var p=[]; for(var i=0;i<n;i++){ if(data[i]!=null)p.push([xAt(i,n),Y(data[i])]); }
  svg.appendChild(el('polyline',{points:L(p),fill:'none',stroke:color,'stroke-width':width||1.4,'stroke-dasharray':dash||''})); }
function panelLabel(svg,txt){ var t=el('text',{x:ML+4,y:MT+10}); t.textContent=txt; svg.appendChild(t); }

function drawPrice(){
  var svg=document.getElementById('p-price'); svg.innerHTML=''; svg.style.display='';
  var d=DATA, n=d.close.length, y0=PH-MB, y1=MT;
  var arrs=[d.close]; if(on('bb')){arrs.push(d.bb_upper,d.bb_lower);} if(on('sma')){arrs.push(d.sma20,d.sma50);}
  if(on('ich')){arrs.push(d.ichimoku.tenkan,d.ichimoku.kijun,d.ichimoku.span_a,d.ichimoku.span_b);}
  var mm=minmax(arrs), lo=mm[0], hi=mm[1], pad=(hi-lo)*0.05; lo-=pad; hi+=pad;
  var Y=function(v){ return y0-(v-lo)/(hi-lo)*(y0-y1); };
  var step=niceStep(hi-lo,5);
  for(var g=Math.ceil(lo/step)*step; g<=hi; g+=step){ var yy=Y(g);
    svg.appendChild(el('line',{x1:ML,y1:yy,x2:W-MR,y2:yy,stroke:'var(--border)','stroke-width':0.5,opacity:0.5}));
    var t=el('text',{x:ML-5,y:yy+3,'text-anchor':'end'}); t.textContent='$'+(g>=1000?(g/1000).toFixed(1)+'k':g.toFixed(0)); svg.appendChild(t); }
  // Ichimoku cloud (behind everything)
  if(on('ich')){ var A=d.ichimoku.span_a, B=d.ichimoku.span_b;
    for(var i=1;i<n;i++){ if(A[i]==null||B[i]==null||A[i-1]==null||B[i-1]==null)continue;
      var pts=[[xAt(i-1,n),Y(A[i-1])],[xAt(i,n),Y(A[i])],[xAt(i,n),Y(B[i])],[xAt(i-1,n),Y(B[i-1])]];
      svg.appendChild(el('polygon',{points:L(pts),fill:(A[i]>=B[i]?C.up:C.down),opacity:0.10,stroke:'none'})); }
    polyline(svg,A,n,Y,C.up,0.8,'3 3'); polyline(svg,B,n,Y,C.down,0.8,'3 3');
    polyline(svg,d.ichimoku.tenkan,n,Y,C.tenkan,1); polyline(svg,d.ichimoku.kijun,n,Y,C.kijun,1);
  }
  if(on('bb')){ var top=[],bot=[]; for(var i=0;i<n;i++){ if(d.bb_upper[i]!=null)top.push(xAt(i,n).toFixed(1)+','+Y(d.bb_upper[i]).toFixed(1)); }
    for(var j=n-1;j>=0;j--){ if(d.bb_lower[j]!=null)bot.push(xAt(j,n).toFixed(1)+','+Y(d.bb_lower[j]).toFixed(1)); }
    if(top.length) svg.appendChild(el('polygon',{points:top.concat(bot).join(' '),fill:C.bb,opacity:0.07}));
    polyline(svg,d.bb_upper,n,Y,C.bb,1,'3 3'); polyline(svg,d.bb_lower,n,Y,C.bb,1,'3 3'); }
  if(on('sma')){ polyline(svg,d.sma20,n,Y,C.sma20,1.3); polyline(svg,d.sma50,n,Y,C.sma50,1.3); }
  polyline(svg,d.close,n,Y,C.close,1.6);
  crosshair(svg,'cx-price',y1,y0);
  // legend + x dates
  var leg=[['Close',C.close]]; if(on('sma')){leg.push(['SMA20',C.sma20],['SMA50',C.sma50]);}
  if(on('bb'))leg.push(['Bollinger',C.bb]); if(on('ich'))leg.push(['Tenkan',C.tenkan],['Kijun',C.kijun]);
  var lx=ML+4; leg.forEach(function(it){ svg.appendChild(el('line',{x1:lx,y1:MT+6,x2:lx+14,y2:MT+6,stroke:it[1],'stroke-width':2}));
    var t=el('text',{x:lx+18,y:MT+9}); t.textContent=it[0]; svg.appendChild(t); lx+=18+it[0].length*6.1+14; });
  [0,Math.floor((n-1)/2),n-1].forEach(function(idx,ki){ var anc=ki===0?'start':(ki===2?'end':'middle');
    var t=el('text',{x:xAt(idx,n),y:PH-5,'text-anchor':anc}); t.textContent=_date(d.dates[idx]); svg.appendChild(t); });
}

// generic subpanel: lines[{data,color,width,dash}], guides[{v,dash,label}], fixed=[lo,hi] or null
function subPanel(id,cxId,H,visible,lines,guides,label,fixed,band){
  var svg=document.getElementById(id);
  if(!visible){ svg.style.display='none'; svg.innerHTML=''; return; }
  svg.style.display=''; svg.innerHTML='';
  var d=DATA, n=d.close.length, y0=H-MB, y1=MT;
  var lo,hi;
  if(fixed){ lo=fixed[0]; hi=fixed[1]; }
  else { var arrs=lines.map(function(x){return x.data;}); if(guides)guides.forEach(function(g){arrs.push([g.v]);}); var mm=minmax(arrs); lo=mm[0]; hi=mm[1]; var pad=(hi-lo)*0.06; lo-=pad; hi+=pad; }
  var Y=function(v){ return y0-(v-lo)/(hi-lo)*(y0-y1); };
  if(band){ svg.appendChild(el('rect',{x:ML,y:Y(band[1]),width:W-ML-MR,height:Y(band[0])-Y(band[1]),fill:band[2],opacity:0.05})); }
  (guides||[]).forEach(function(gg){ var yy=Y(gg.v);
    svg.appendChild(el('line',{x1:ML,y1:yy,x2:W-MR,y2:yy,stroke:'var(--border)','stroke-width':0.7,'stroke-dasharray':gg.dash||'4 4'}));
    var t=el('text',{x:ML-5,y:yy+3,'text-anchor':'end'}); t.textContent=gg.label!=null?gg.label:gg.v; svg.appendChild(t); });
  lines.forEach(function(ln){ polyline(svg,ln.data,n,Y,ln.color,ln.width,ln.dash); });
  panelLabel(svg,label);
  crosshair(svg,cxId,y1,y0);
}

function drawMACD(){
  var id='p-macd'; var svg=document.getElementById(id);
  if(!on('macd')){ svg.style.display='none'; svg.innerHTML=''; return; }
  svg.style.display=''; svg.innerHTML='';
  var d=DATA, n=d.close.length, H=150, y0=H-MB, y1=MT;
  var mm=minmax([d.macd,d.signal,d.hist]), lo=mm[0], hi=mm[1]; var Y=function(v){ return y0-(v-lo)/(hi-lo)*(y0-y1); };
  var yz=Y(0); svg.appendChild(el('line',{x1:ML,y1:yz,x2:W-MR,y2:yz,stroke:'var(--border)','stroke-width':0.7}));
  var bw=Math.max(1,(W-ML-MR)/n*0.7);
  for(var i=0;i<n;i++){ if(d.hist[i]==null)continue; var x=xAt(i,n), yv=Y(d.hist[i]);
    svg.appendChild(el('rect',{x:x-bw/2,y:Math.min(yz,yv),width:bw,height:Math.abs(yv-yz),fill:d.hist[i]>=0?C.up:C.down,opacity:0.5})); }
  polyline(svg,d.macd,n,Y,C.macd,1.3); polyline(svg,d.signal,n,Y,C.sig,1.3);
  panelLabel(svg,'MACD(12,26,9)'); crosshair(svg,'cx-macd',y1,y0);
}

function redraw(){ if(!DATA)return; var d=DATA;
  drawPrice();
  subPanel('p-rsi','cx-rsi',120,on('rsi'),[{data:d.rsi,color:C.rsi}],
    [{v:30},{v:50,dash:'2 6'},{v:70}],'RSI(14)',[0,100],[30,70,C.rsi]);
  subPanel('p-stoch','cx-stoch',120,on('stoch'),
    [{data:d.stoch_k,color:C.k,width:1.3},{data:d.stoch_d,color:C.d,width:1.2}],
    [{v:20},{v:80}],'Stochastic %K/%D',[0,100],[20,80,C.k]);
  drawMACD();
  subPanel('p-adx','cx-adx',120,on('adx'),
    [{data:d.adx,color:C.adx,width:1.5},{data:d.plus_di,color:C.pdi,width:1,dash:'3 3'},{data:d.minus_di,color:C.mdi,width:1,dash:'3 3'}],
    [{v:25,label:25}],'ADX(14) +DI/-DI',null);
  subPanel('p-atr','cx-atr',110,on('atr'),[{data:d.atr,color:C.atr,width:1.4}],null,'ATR(14)',null);
  subPanel('p-obv','cx-obv',120,on('obv'),[{data:d.obv,color:C.obv,width:1.4}],null,'OBV',null);
}

function hover(ev){ if(!DATA)return; var svg=document.getElementById('p-price'); var r=svg.getBoundingClientRect();
  var sx=r.width/W; var vx=(ev.clientX-r.left)/sx; var n=DATA.close.length;
  var i=Math.round((vx-ML)/(W-ML-MR)*(n-1)); if(i<0)i=0; if(i>n-1)i=n-1; var x=xAt(i,n);
  var lines=document.querySelectorAll('#panels line[id^="cx-"]');
  [].forEach.call(lines,function(c){ c.setAttribute('x1',x); c.setAttribute('x2',x); c.style.display=''; });
  document.getElementById('readout').innerHTML=readoutAt(i);
}
function readoutAt(i){ var d=DATA;
  var p=['<span class="k">'+_date(d.dates[i])+'</span> &nbsp; <b>'+_fmt(d.close[i])+'</b>'];
  if(on('rsi')) p.push('<span class="k">RSI</span> '+num(d.rsi[i],0));
  if(on('stoch')) p.push('<span class="k">Stoch</span> '+num(d.stoch_k[i],0)+'/'+num(d.stoch_d[i],0));
  if(on('macd')) p.push('<span class="k">MACD</span> '+num(d.macd[i],2)+'/'+num(d.signal[i],2));
  if(on('adx')) p.push('<span class="k">ADX</span> '+num(d.adx[i],0));
  if(on('atr')) p.push('<span class="k">ATR</span> '+num(d.atr[i],2));
  if(on('obv')) p.push('<span class="k">OBV</span> '+_big(d.obv[i]));
  return p.join(' &nbsp; ');
}
function hoverOff(){ [].forEach.call(document.querySelectorAll('#panels line[id^="cx-"]'),function(c){c.style.display='none';});
  if(DATA){ var i=DATA.close.length-1; document.getElementById('readout').innerHTML='<span class="k">latest '+_date(DATA.dates[i])+'</span> &nbsp; <b>'+_fmt(DATA.close[i])+'</b>'; } }

function loadInd(){ var t=(document.getElementById('itk').value||'').trim().toUpperCase(); if(!t)return;
  document.getElementById('ind-msg').textContent='Loading '+t+'…'; document.getElementById('isug').style.display='none';
  fetch('/api/indicators/'+encodeURIComponent(t)+'?period='+PERIOD).then(function(r){return r.json();}).then(function(d){
    if(d.error){ document.getElementById('ind-msg').textContent=d.error; DATA=null; return; }
    DATA=d; document.getElementById('ind-msg').textContent=''; redraw(); hoverOff();
  }).catch(function(){ document.getElementById('ind-msg').textContent='Failed to load.'; });
}
document.getElementById('perseg').addEventListener('click', function(e){ var b=e.target.closest('button'); if(!b)return;
  [].forEach.call(this.querySelectorAll('button'),function(x){x.classList.toggle('on',x===b);}); PERIOD=b.dataset.p; loadInd(); });

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
