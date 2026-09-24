"""Breakouts page: today's breakout candidates on the watchlist, graded by how
many confirmations they have, next to how breakouts have actually done here.
Data from GET /api/breakouts."""

from __future__ import annotations

from ..dashboard.render import _CSS, _THEME_BOOT, icon


def breakouts_html() -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Breakouts</title>" + _THEME_BOOT + "<style>" + _CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Breakouts</h1>"
            "<span class=\"sub\" style=\"margin:0\">Stocks closing above their 20-day high, graded</span>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" "
            "aria-label=\"Close\">" + icon("x", 17) + "</button></header>"
            "<p id=\"meta\" class=\"muted bo-meta\"></p>"
            "<div id=\"list\" class=\"bo-tw muted\">Scanning…</div>"
            "<section class=\"bo-sec\"><h2>How breakouts have done here</h2><div id=\"track\" class=\"bo-tw muted\">Loading…</div>"
            "<p class=\"bo-note\" id=\"verdict\"></p></section>"
            "<section class=\"bo-sec\"><h2>What the grade means</h2><p class=\"bo-note\" style=\"font-size:14px\">"
            "A breakout is a close above the prior 20-day high. Each gets a point for: being within 2% of its "
            "52-week high (stocks near their highs have tended to keep outperforming, George &amp; Hwang, 2004); "
            "volume at least 1.5x its 50-day average; the trend in order (price above the 50-day average, above the "
            "200-day); beating the S&amp;P 500 over 3 months; and a squeeze first (a quiet, narrow range just before). "
            "Grade A has 4 or 5, B has 3, C fewer. During market hours today's volume is only partway through the day.</p></section>"
            "<p class=\"muted\" style=\"font-size:13px;margin-top:18px\">A scan of the watchlist from daily closes. "
            "Analysis, not advice.</p>"
            "</div><script>" + _JS + "</script></body></html>")


_EXTRA_CSS = """
.bo-meta{font-size:14px;margin:0 0 10px}
.bo-sec{margin-top:22px}
.bo-sec h2{font-family:var(--font-display);font-weight:500;font-size:28px;margin:0 0 8px}
.bo-tw{overflow-x:auto;border:1px solid var(--border);border-radius:10px;background:var(--surface)}
.bo-tw.muted{padding:14px;font-size:14px}
.bo-t{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
.bo-t th,.bo-t td{padding:9px 12px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap}
.bo-t th{font-size:12px;font-weight:500;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px}
.bo-t tr:last-child td{border-bottom:none}
.bo-t td:first-child,.bo-t th:first-child,.bo-t td:nth-child(2),.bo-t th:nth-child(2){text-align:left}
.bo-t .up{color:var(--up)} .bo-t .down{color:var(--down)} .bo-t .mu{color:var(--muted)}
.bo-t a{color:var(--link);text-decoration:none;font-weight:500} .bo-t a:hover{text-decoration:underline}
.grade{display:inline-block;min-width:22px;text-align:center;border-radius:5px;padding:0 6px;font-weight:500}
.grade.A{background:color-mix(in srgb,var(--up) 16%,transparent);color:var(--up)}
.grade.B{background:var(--surface-3)} .grade.C{color:var(--muted);border:1px solid var(--border)}
.ck{display:inline-flex;gap:4px;flex-wrap:nowrap}
.ck span{font-size:12px;border:1px solid var(--border);border-radius:5px;padding:0 5px;color:var(--muted)}
.ck span.on{color:var(--ink);border-color:var(--ink-2)}
.bo-note{font-size:13px;color:var(--muted);line-height:1.55;margin:8px 0 0}
"""

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){ try{window.opener.focus();}catch(_){}; window.close(); }
  else location.href='/'; return false; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
function pct(v,dp){ if(v==null) return '<span class="mu">-</span>'; return '<span class="'+(v>=0?'up':'down')+'">'+(v>=0?'+':'')+(v*100).toFixed(dp==null?1:dp)+'%</span>'; }
var LABELS={near_52w_high:'52w high',volume:'volume',trend:'trend',relative_strength:'beats S&P',squeeze:'squeeze'};
fetch('/api/breakouts').then(function(r){return r.json();}).then(function(d){
  if(!d.ok){ document.getElementById('list').textContent=d.error||'Unavailable.'; return; }
  document.getElementById('meta').textContent=d.candidates.length+' breakouts among '+d.universe+' stocks, as of the '+d.as_of+' close.';
  var L=document.getElementById('list');
  if(!d.candidates.length){ L.textContent='No breakouts today.'; }
  else { L.className='bo-tw'; L.innerHTML='<table class="bo-t"><thead><tr><th>Ticker</th><th>Confirmations</th><th>Grade</th><th>Close</th><th>Day</th><th>Above 20-day high</th><th>Volume vs avg</th><th>From 52w high</th><th>vs S&amp;P, 3 mo</th></tr></thead><tbody>'+
    d.candidates.map(function(r){ return '<tr><td><a href="/analysis/'+encodeURIComponent(r.ticker)+'" target="_blank" rel="noopener">'+esc(r.ticker)+'</a></td><td><span class="ck">'+
      Object.keys(LABELS).map(function(k){ return '<span class="'+(r.checks[k]?'on':'')+'">'+LABELS[k]+'</span>'; }).join('')+'</span></td><td><span class="grade '+r.grade+'">'+r.grade+'</span></td>'+
      '<td>$'+r.close.toFixed(2)+'</td><td>'+pct(r.change)+'</td><td>'+pct(r.above)+'</td><td>'+(r.rvol==null?'<span class="mu">-</span>':r.rvol.toFixed(1)+'x')+'</td><td>'+pct(r.from_52w_high)+'</td><td>'+pct(r.rs_3m,0)+'</td></tr>'; }).join('')+'</tbody></table>'; }
  var bt=d.backtest, T=document.getElementById('track');
  if(bt){ T.className='bo-tw';
    var row=function(label,x){ return '<tr><td>'+label+'</td><td>'+(x.n!=null?x.n.toLocaleString():'-')+'</td>'+['5','20','60'].map(function(h){
      var s=x[h]||{}; return '<td>'+pct(s.mean)+(s.excess!=null?' <span class="mu">('+(s.excess>=0?'+':'')+(s.excess*100).toFixed(1)+' vs normal)</span>':'')+'</td><td>'+(s.hit!=null?Math.round(s.hit*100)+'%':'-')+'</td>'; }).join('')+'</tr>'; };
    T.innerHTML='<table class="bo-t"><thead><tr><th>Signal</th><th>Count</th><th>After 5 days</th><th>Up</th><th>After 20 days</th><th>Up</th><th>After 60 days</th><th>Up</th></tr></thead><tbody>'+
      row('Grade A',bt.A)+row('Grade B',bt.B)+row('Grade C',bt.C)+row('Any day (normal)',Object.assign({n:null},bt.base))+'</tbody></table>';
    var a=(bt.A||{})['20']||{}, edge=a.excess!=null && a.excess>0.01;
    document.getElementById('verdict').textContent='Replaying every breakout on these stocks over the past '+bt.years+' years (one per stock per 10 days). '+
      (edge?'Grade A breakouts beat ordinary days by '+(a.excess*100).toFixed(1)+' pts over 20 days: a modest edge, before trading costs.':
      'So far breakouts here have done about the same as ordinary days, so treat the list as "what is breaking out", not as a buy signal.'); }
}).catch(function(){ document.getElementById('list').textContent='Breakout scan unavailable right now.'; });
"""
