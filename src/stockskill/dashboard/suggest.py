"""Search as you type, shared by every search box: suggestions appear under
the input while typing (stocks, politicians and funds from /api/find, which
forgives typos). ``attachSuggest(input, {kinds, onPick})``; ``fzScore(q, name)``
is the same forgiving match in the browser, for filtering lists already loaded."""

SUGGEST_CSS = """
.sg-box{position:absolute;left:0;right:0;top:calc(100% + 4px);z-index:60;background:var(--bg);border:1px solid var(--border);
  border-radius:12px;box-shadow:0 16px 36px -14px rgba(0,0,0,.35);padding:6px;max-height:min(70vh,460px);overflow:auto;display:none;min-width:260px}
.sg-box.show{display:block}
.sg-h{font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted);padding:6px 8px 2px}
.sg-i{display:flex;align-items:center;gap:10px;padding:7px 8px;border-radius:8px;cursor:pointer;font-size:14px;color:var(--ink)}
.sg-i:hover,.sg-i.on{background:var(--surface-2)}
.sg-i b{font-weight:500;min-width:52px} .sg-i span{color:var(--muted);font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sg-i img,.sg-i .sg-mono{width:26px;height:30px;border-radius:6px;object-fit:cover;flex:none;background:var(--surface-2);
  display:inline-flex;align-items:center;justify-content:center;font-size:11px;color:var(--muted)}
.sg-none{padding:8px;color:var(--muted);font-size:13px}
"""

SUGGEST_JS = r"""
function _sgEsc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
function fzScore(q, name){                       // 0..1, forgiving: "palosi" ~ "pelosi"
  function norm(s){ return String(s||'').normalize('NFKD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[^a-z0-9 ]+/g,' ').trim(); }
  function lev(a,b){ var m=a.length,n=b.length,d=[],i,j; for(i=0;i<=m;i++){ d[i]=[i]; } for(j=0;j<=n;j++) d[0][j]=j;
    for(i=1;i<=m;i++) for(j=1;j<=n;j++) d[i][j]=Math.min(d[i-1][j]+1,d[i][j-1]+1,d[i-1][j-1]+(a[i-1]===b[j-1]?0:1)); return d[m][n]; }
  q=norm(q); var n=norm(name); if(!q||!n) return 0;
  if((' '+n).indexOf(' '+q)>=0) return 1; if(n.indexOf(q)>=0) return 0.9;
  var words=n.split(' '), qw=q.split(' ');
  if(qw.every(function(x){ return words.some(function(w){ return w.indexOf(x)===0; }); })) return 0.85;
  var best=0; qw.forEach(function(x){ if(x.length<3) return; words.forEach(function(w){
    var r=1-lev(x,w)/Math.max(x.length,w.length); if(r>best) best=r; }); });
  return best*0.8; }
function attachSuggest(input, opts){
  if(!input || input._sg) return; input._sg=true; opts=opts||{};
  var host=input.parentNode; if(getComputedStyle(host).position==='static') host.style.position='relative';
  var box=document.createElement('div'); box.className='sg-box'; host.appendChild(box);
  var items=[], on=-1, timer=null, seq=0;
  function hide(){ box.classList.remove('show'); on=-1; }
  function pick(i){ var it=items[i]; if(!it) return; hide(); opts.onPick && opts.onPick(it, input); }
  function draw(d){ items=[]; var h='';
    function sec(title, list, row){ if(!list||!list.length) return; h+='<div class="sg-h">'+title+'</div>';
      list.forEach(function(x){ var i=items.length; items.push(x); h+='<div class="sg-i" data-i="'+i+'">'+row(x)+'</div>'; }); }
    sec('Stocks', (d.stocks||[]).map(function(x){ return {kind:'stock', symbol:x.symbol, name:x.name}; }),
        function(x){ return '<b>'+_sgEsc(x.symbol)+'</b><span>'+_sgEsc(x.name||'')+'</span>'; });
    sec('Politicians', (d.politicians||[]).map(function(x){ x.kind='politician'; return x; }), function(x){
      var ini=(x.name||'?').split(' ').map(function(w){ return w[0]; }).slice(0,2).join('');
      return (x.photo?'<img src="'+_sgEsc(x.photo)+'" alt="" loading="lazy">':'<span class="sg-mono">'+_sgEsc(ini)+'</span>')+
        '<b style="min-width:0">'+_sgEsc(x.name)+'</b><span>'+_sgEsc([x.party?x.party[0]:'', x.chamber==='President'?'President':x.chamber, x.state].filter(Boolean).join(' · '))+'</span>'; });
    sec('Funds', (d.funds||[]).map(function(x){ x.kind='fund'; return x; }),
        function(x){ return '<b style="min-width:0">'+_sgEsc(x.fund)+'</b><span>'+_sgEsc(x.manager)+'</span>'; });
    box.innerHTML=h||'<div class="sg-none">No matches yet. Keep typing, or press Enter.</div>';
    box.classList.add('show'); on=-1; }
  input.addEventListener('input', function(){ clearTimeout(timer); var q=input.value.trim();
    if(opts.lastToken) q=q.split(/[\s,;]+/).pop();
    if(q.length<(opts.minLen||1)){ hide(); return; }
    var my=++seq; timer=setTimeout(function(){
      fetch('/api/find?kinds='+encodeURIComponent(opts.kinds||'stocks')+'&q='+encodeURIComponent(q)).then(function(r){ return r.json(); })
        .then(function(d){ if(my===seq && document.activeElement===input) draw(d); }).catch(function(){}); }, 150); });
  input.addEventListener('keydown', function(e){ if(!box.classList.contains('show')||!items.length) return;
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){ e.preventDefault(); on=(on+(e.key==='ArrowDown'?1:-1)+items.length)%items.length;
      box.querySelectorAll('.sg-i').forEach(function(el,i){ el.classList.toggle('on',i===on); }); }
    else if(e.key==='Enter' && on>=0){ e.preventDefault(); e.stopImmediatePropagation(); pick(on); }
    else if(e.key==='Escape') hide(); }, true);
  box.addEventListener('mousedown', function(e){ var el=e.target.closest('.sg-i'); if(el){ e.preventDefault(); pick(+el.dataset.i); } });
  input.addEventListener('blur', function(){ setTimeout(hide, 150); });
}
// a stock picked for a box that already runs on Enter: fill it in and run it
function sgRunTicker(it, input){ if(it.kind!=='stock') return; input.value=it.symbol;
  input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); }
"""
