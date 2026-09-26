"""Alerts page (private mode only): set up phone notifications through ntfy
and manage the rules. Data from /api/alerts."""

from __future__ import annotations

from ..dashboard.render import _CSS, _THEME_BOOT, icon


def alerts_html() -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Alerts</title>" + _THEME_BOOT + "<style>" + _CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Alerts</h1>"
            "<span class=\"sub\" style=\"margin:0\">Notifications on your phone</span>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" aria-label=\"Close\">"
            + icon("x", 17) + "</button></header>"
            "<div id=\"al-setup\"></div>"
            "<div class=\"al-card\"><h3>New alert</h3><div class=\"al-form\">"
            "<select id=\"al-type\" class=\"al-in\"></select>"
            "<input id=\"al-tk\" class=\"al-in\" placeholder=\"Ticker\" autocomplete=\"off\">"
            "<span id=\"al-vwrap\"><input id=\"al-val\" class=\"al-in\" inputmode=\"decimal\"><span id=\"al-unit\" class=\"al-u\"></span></span>"
            "<button class=\"al-go\" onclick=\"addRule()\">Add alert</button><span id=\"al-msg\" class=\"al-msg\"></span></div>"
            "<p id=\"al-help\" class=\"al-help\"></p></div>"
            "<div class=\"al-card\"><h3>Your alerts</h3><div id=\"al-rules\" class=\"muted\">Loading…</div></div>"
            "<div class=\"al-card\"><h3>Recently sent</h3><div id=\"al-log\" class=\"muted\"></div></div>"
            "<p class=\"al-note\">Price alerts are checked every 5 minutes while the market is open (the whole watchlist's "
            "daily moves every 15). Breakouts are checked after the close, insider purchases (SEC Form 4, via Finnhub) in "
            "the evening, and earnings each morning for the next trading day. Alerts only run while this app is running. "
            "Each alert fires once: a price alert re-arms after the price moves 1% back the other way.</p>"
            "</div><script>" + _JS + "</script></body></html>")


_EXTRA_CSS = """
.al-card{border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:12px 16px;margin-bottom:12px}
.al-card h3{font-size:12px;font-weight:500;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);margin:0 0 10px}
.al-card.warn{border-color:var(--accent)}
.al-card ol{margin:6px 0 0 18px;padding:0;font-size:14px;line-height:1.7}
.al-card code{font-family:var(--font-mono);font-size:13px;background:var(--bg);padding:2px 6px;border-radius:4px;user-select:all}
.al-form{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.al-in{height:38px;padding:0 10px;border-radius:var(--r);border:1px solid var(--border);background:var(--bg);color:var(--ink);font:14px var(--font)}
#al-tk{width:110px;text-transform:uppercase} #al-val{width:110px}
.al-u{margin-left:6px;color:var(--muted);font-size:13px}
.al-go,.al-b{height:38px;padding:0 16px;border-radius:var(--r);border:none;background:var(--accent);color:var(--accent-ink);font:500 14px var(--font);cursor:pointer}
.al-b.sec{background:var(--bg);color:var(--ink);border:1px solid var(--border)}
.al-msg{font-size:13px;color:var(--muted)}
.al-help{font-size:13px;color:var(--muted);margin:8px 0 0}
.al-row{display:flex;align-items:center;gap:12px;padding:9px 0;border-top:1px solid var(--border);font-size:14px}
.al-row:first-child{border-top:none}
.al-row .d{flex:1} .al-row .d small{display:block;color:var(--muted);font-size:12px}
.al-row.off .d{color:var(--muted)}
.al-row button{border:1px solid var(--border);background:var(--bg);color:var(--ink);border-radius:var(--r);height:30px;padding:0 10px;font:13px var(--font);cursor:pointer}
.al-row button:hover{border-color:var(--border-strong)}
.al-log{display:flex;gap:12px;padding:7px 0;border-top:1px solid var(--border);font-size:13px}
.al-log:first-child{border-top:none}
.al-log .t{color:var(--muted);white-space:nowrap;min-width:120px}
.al-log .x{color:var(--down)}
.al-note{font-size:13px;color:var(--muted);line-height:1.55;margin:12px 0 0}
.muted{color:var(--muted);font-size:14px}
@media (max-width:640px){.al-log{flex-direction:column;gap:2px}}
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
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
var HELP={price_above:['ticker','$','Buzz when the price reaches this level or higher.'],
  price_below:['ticker','$','Buzz when the price falls to this level or lower.'],
  move:['ticker-optional','%','Buzz when a stock moves this much in a day, up or down. Leave the ticker empty for your whole watchlist.'],
  breakout:['','','After the close, every watchlist stock that closed at a 20-day high (see Breakouts).'],
  insider_buy:['','$','Evening check: an executive or director bought their own company\'s stock on the open market, worth at least this much (default $100,000).'],
  earnings:['','','Each morning, which watchlist companies report before the next trading day\'s open or after today\'s close.']};
var D=null;
function describe(r){ var t=TN[r.type];
  if(r.type==='price_above'||r.type==='price_below') return '<b>'+esc(r.ticker)+'</b> · '+t+' $'+(+r.value).toLocaleString('en-US',{maximumFractionDigits:2});
  if(r.type==='move') return '<b>'+(r.ticker==='*'?'Any watchlist stock':esc(r.ticker))+'</b> · '+t+' '+r.value+'% or more';
  if(r.type==='insider_buy') return t+' (at least $'+(+r.value).toLocaleString('en-US')+')';
  return t; }
function setType(){ var k=document.getElementById('al-type').value, h=HELP[k];
  var tk=document.getElementById('al-tk'); tk.style.display=h[0]?'':'none'; tk.placeholder=h[0]==='ticker-optional'?'Ticker (optional)':'Ticker';
  document.getElementById('al-vwrap').style.display=h[1]?'':'none';
  document.getElementById('al-val').placeholder=h[1]==='%'?'e.g. 5':k==='insider_buy'?'100000':'e.g. 150';
  document.getElementById('al-unit').textContent=h[1]==='%'?'%':h[1]==='$'?'USD':'';
  document.getElementById('al-help').textContent=h[2]; }
function setup(d){ var el=document.getElementById('al-setup');
  if(d.topic){ el.innerHTML='<div class="al-card"><h3>Phone</h3><div class="al-form"><span style="flex:1;font-size:14px">Sending to ntfy topic <code>'+esc(d.topic)+'</code>'+
    (d.running?'':' <span class="muted">(restart the app to start the checker)</span>')+'</span>'+
    '<button class="al-b sec" onclick="test(this)">Send a test</button><button class="al-b sec" onclick="checkNow(this)">Check now</button></div></div>'; return; }
  el.innerHTML='<div class="al-card warn"><h3>Set up your phone (2 minutes)</h3><ol>'+
    '<li>Install the free <b>ntfy</b> app (App Store or Google Play).</li>'+
    '<li>In the app, tap <b>+</b> and subscribe to this topic: <code>'+esc(d.suggested)+'</code> (a random name, since anyone who knows it can read it).</li>'+
    '<li>Add this line to your <code>.env</code> file: <code>NTFY_TOPIC='+esc(d.suggested)+'</code></li>'+
    '<li>Restart the app, then come back here and press <b>Send a test</b>.</li></ol></div>'; }
function render(){
  setup(D);
  var cur=document.getElementById('al-type').value;
  document.getElementById('al-type').innerHTML=D.types.map(function(t){ return '<option value="'+t[0]+'">'+esc(t[1])+'</option>'; }).join('');
  if(cur) document.getElementById('al-type').value=cur;
  setType();
  var el=document.getElementById('al-rules');
  el.className=D.rules.length?'':'muted';
  el.innerHTML=D.rules.length?D.rules.map(function(r){ return '<div class="al-row'+(r.on?'':' off')+'"><span class="d">'+describe(r)+'<small>Added '+esc(r.created)+(r.on?'':' · paused')+'</small></span>'+
      '<button onclick="toggle(\''+r.id+'\')">'+(r.on?'Pause':'Resume')+'</button><button onclick="del(\''+r.id+'\')">Delete</button></div>'; }).join(''):'No alerts yet. Add one above.';
  var lg=document.getElementById('al-log');
  lg.className=D.log.length?'':'muted';
  lg.innerHTML=D.log.length?D.log.map(function(x){ return '<div class="al-log"><span class="t">'+esc((x.at||'').replace('T',' ').slice(0,16))+'</span><span><b>'+esc(x.title)+'</b> '+esc(x.body||'')+
      (x.sent?'':' <span class="x">(not delivered)</span>')+'</span></div>'; }).join(''):'Nothing sent yet.';
}
var TN={};
function load(){ fetch('/api/alerts').then(function(r){return r.json();}).then(function(d){ D=d; TN={}; d.types.forEach(function(t){ TN[t[0]]=t[1]; }); render(); }); }
function msg(t){ document.getElementById('al-msg').textContent=t; }
function addRule(){ var k=document.getElementById('al-type').value, h=HELP[k];
  var body={type:k, ticker:h[0]?document.getElementById('al-tk').value.trim():'', value:h[1]?document.getElementById('al-val').value.trim():''};
  fetch('/api/alerts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(r){return r.json();}).then(function(d){
    if(!d.ok){ msg(d.error||'Could not add.'); return; } msg('Added.'); document.getElementById('al-tk').value=''; document.getElementById('al-val').value=''; load(); }); }
function toggle(id){ fetch('/api/alerts/'+id+'/toggle',{method:'POST'}).then(load); }
function del(id){ if(!confirm('Delete this alert?')) return; fetch('/api/alerts/'+id,{method:'DELETE'}).then(load); }
function test(b){ b.disabled=true; fetch('/api/alerts/test',{method:'POST'}).then(function(r){return r.json();}).then(function(d){
  b.textContent=d.ok?'Sent. Check your phone':(d.error||'Failed'); setTimeout(function(){ b.disabled=false; b.textContent='Send a test'; },4000); }); }
function checkNow(b){ b.disabled=true; fetch('/api/alerts/check',{method:'POST'}).then(function(){
  b.textContent='Checking…'; setTimeout(function(){ b.disabled=false; b.textContent='Check now'; load(); },8000); }); }
document.getElementById('al-type').addEventListener('change',setType);
load();
"""
