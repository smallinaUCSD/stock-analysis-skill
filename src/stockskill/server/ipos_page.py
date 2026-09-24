"""IPO calendar page: upcoming listings and how recent ones have traded since
pricing. Data from GET /api/ipos (Finnhub's free IPO calendar)."""

from __future__ import annotations

from ..dashboard.render import _CSS, _THEME_BOOT, icon


def ipos_html() -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>IPO calendar</title>" + _THEME_BOOT + "<style>" + _CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>IPOs</h1>"
            "<span class=\"sub\" style=\"margin:0\">Upcoming listings and how recent ones have traded</span>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" "
            "aria-label=\"Close\">" + icon("x", 17) + "</button></header>"
            "<label class=\"ipo-chk\"><input type=\"checkbox\" id=\"spac\" onchange=\"render()\"> "
            "Show SPACs (blank-check shells that list at $10)</label>"
            "<section class=\"ipo-sec\"><h2>Coming up</h2><div id=\"up\" class=\"ipo-tw muted\">Loading…</div></section>"
            "<section class=\"ipo-sec\"><h2>Priced in the last 30 days</h2><div id=\"rec\" class=\"ipo-tw muted\">Loading…</div>"
            "<p class=\"ipo-note\">&ldquo;Since IPO&rdquo; compares today's price with the offer price. On average, IPOs "
            "have lagged comparable companies over the following years (Ritter, 1991), even when the first day pops.</p></section>"
            "<p class=\"muted\" style=\"font-size:13px;margin-top:18px\">Dates and price ranges change until a deal prices. "
            "Data from Finnhub's IPO calendar. Analysis, not advice.</p>"
            "</div><script>" + _JS + "</script></body></html>")


_EXTRA_CSS = """
.ipo-chk{font-size:14px;color:var(--muted);display:flex;align-items:center;gap:6px;margin:4px 0 10px}
.ipo-sec{margin-top:18px}
.ipo-sec h2{font-family:var(--font-display);font-weight:500;font-size:28px;margin:0 0 8px}
.ipo-tw{overflow-x:auto;border:1px solid var(--border);border-radius:10px;background:var(--surface)}
.ipo-tw.muted{padding:14px;font-size:14px}
.ipo-t{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
.ipo-t th,.ipo-t td{padding:9px 12px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap}
.ipo-t th{font-size:12px;font-weight:500;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px}
.ipo-t tr:last-child td{border-bottom:none}
.ipo-t td:nth-child(-n+3),.ipo-t th:nth-child(-n+3){text-align:left}
.ipo-t .nm{white-space:normal;min-width:180px}
.ipo-t .tk{font-weight:500}
.ipo-t .up{color:var(--up)} .ipo-t .down{color:var(--down)} .ipo-t .mu{color:var(--muted)}
.ipo-tag{font-size:12px;color:var(--muted);border:1px solid var(--border);border-radius:5px;padding:0 5px;margin-left:6px}
.ipo-note{font-size:13px;color:var(--muted);margin:6px 0 0;line-height:1.5}
"""

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){ try{window.opener.focus();}catch(_){}; window.close(); }
  else location.href='/'; return false; }
var D=null;
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
function fdate(iso){ if(!iso) return '-'; var p=iso.split('-'); return ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+p[1]-1]+' '+(+p[2]); }
function big(v){ if(v==null) return '<span class="mu">-</span>'; var a=Math.abs(v);
  return a>=1e9?'$'+(v/1e9).toFixed(2)+'B':(a>=1e6?'$'+(v/1e6).toFixed(0)+'M':'$'+Math.round(v).toLocaleString()); }
function rng(r){ if(r.low==null) return '<span class="mu">TBD</span>'; return r.low===r.high?'$'+r.low.toFixed(2):'$'+r.low.toFixed(2)+' - '+r.high.toFixed(2); }
function shares(v){ return v==null?'<span class="mu">-</span>':(v>=1e6?(v/1e6).toFixed(1)+'M':Math.round(v).toLocaleString()); }
function table(head, rows){ return '<table class="ipo-t"><thead><tr>'+head.map(function(h){return '<th>'+h+'</th>';}).join('')+
  '</tr></thead><tbody>'+rows.join('')+'</tbody></table>'; }
function render(){ if(!D) return; var show=document.getElementById('spac').checked;
  var keep=function(r){ return show||!r.spac; };
  var tag=function(r){ return r.spac?'<span class="ipo-tag">SPAC</span>':''; };
  var up=D.upcoming.filter(keep), rec=D.recent.filter(keep);
  var u=document.getElementById('up'), c=document.getElementById('rec');
  if(up.length){ u.className='ipo-tw'; u.innerHTML=table(['Date','Company','Ticker','Exchange','Price range','Shares','Deal size'],
    up.map(function(r){ return '<tr><td>'+fdate(r.date)+'</td><td class="nm">'+esc(r.name)+tag(r)+'</td><td class="tk">'+esc(r.symbol||'-')+
      '</td><td>'+esc(r.exchange||'-')+'</td><td>'+rng(r)+'</td><td>'+shares(r.shares)+'</td><td>'+big(r.value)+'</td></tr>'; })); }
  else { u.className='ipo-tw muted'; u.textContent='No IPOs scheduled in the next few weeks.'; }
  if(rec.length){ c.className='ipo-tw'; c.innerHTML=table(['Priced','Company','Ticker','Offer price','Now','Since IPO'],
    rec.map(function(r){ var s=r.since_ipo, cls=s==null?'mu':(s>=0?'up':'down');
      return '<tr><td>'+fdate(r.date)+'</td><td class="nm">'+esc(r.name)+tag(r)+'</td><td class="tk">'+esc(r.symbol||'-')+'</td><td>'+
        (r.high!=null?'$'+r.high.toFixed(2):'<span class="mu">-</span>')+'</td><td>'+(r.last!=null?'$'+r.last.toFixed(2):'<span class="mu">-</span>')+
        '</td><td class="'+cls+'">'+(s==null?'-':(s>=0?'+':'')+(s*100).toFixed(1)+'%')+'</td></tr>'; })); }
  else { c.className='ipo-tw muted'; c.textContent='No recent IPOs to show.'; }
}
fetch('/api/ipos').then(function(r){return r.json();}).then(function(d){
  if(!d.ok){ ['up','rec'].forEach(function(id){ document.getElementById(id).textContent=d.error||'IPO calendar unavailable.'; }); return; }
  D=d; render(); }).catch(function(){ document.getElementById('up').textContent='IPO calendar unavailable right now.'; });
"""
