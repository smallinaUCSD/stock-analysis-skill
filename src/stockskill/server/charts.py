"""A small donut (pie) chart for the profile pages: shares of a whole, with a
legend of names and percentages. ``donut(el, items, opts)`` where items are
[{name, value}] and opts may give ``title`` and ``fmt`` (for the values)."""

DONUT_CSS = """
.dn-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(360px,100%),1fr));gap:14px}
.dn{display:flex;gap:18px;align-items:center;border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:14px 16px}
.dn h3{font-size:12px;letter-spacing:1.3px;text-transform:uppercase;color:var(--muted);font-weight:500;margin:0 0 8px}
.dn svg{flex:none;width:150px;height:150px}
.dn svg circle.seg{transition:stroke-width .12s}
.dn svg circle.seg:hover{stroke-width:30}
.dn-leg{flex:1;min-width:0;font-size:13px}
.dn-leg div{display:grid;grid-template-columns:10px 1fr auto;gap:8px;align-items:center;padding:2px 0}
.dn-leg i{width:10px;height:10px;border-radius:3px}
.dn-leg span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dn-leg b{font-weight:500;font-variant-numeric:tabular-nums}
.dn-mid{font:500 15px var(--font);fill:var(--ink)} .dn-sub{font-size:11px;fill:var(--muted)}
@media (max-width:520px){.dn{flex-direction:column;align-items:stretch}.dn svg{align-self:center}}
"""

DONUT_JS = r"""
var DN_COLORS=['var(--accent)','#5db8a6','#e8a55a','#8b7fc7','#4f86d9','#d96c8f','#9bbf4a','#c99a2e','#6fb1d8','#b07256'];
function donut(el, items, opts){ opts=opts||{}; items=(items||[]).filter(function(x){ return x.value>0; });
  var total=items.reduce(function(a,x){ return a+x.value; },0);
  if(!el) return; if(!total){ el.innerHTML=''; el.style.display='none'; return; }
  var R=58, C=2*Math.PI*R, off=0, segs='';
  items.forEach(function(x,i){ var len=x.value/total*C;
    segs+='<circle class="seg" cx="75" cy="75" r="'+R+'" fill="none" stroke="'+DN_COLORS[i%DN_COLORS.length]+'" stroke-width="24" '+
      'stroke-dasharray="'+Math.max(0,len-1.5).toFixed(2)+' '+(C-Math.max(0,len-1.5)).toFixed(2)+'" stroke-dashoffset="'+(-off).toFixed(2)+'" '+
      'transform="rotate(-90 75 75)"><title>'+esc(x.name)+': '+(x.value/total*100).toFixed(1)+'%</title></circle>'; off+=len; });
  var mid=opts.center!=null?opts.center:items.length;
  el.style.display='';
  el.innerHTML='<svg viewBox="0 0 150 150" role="img" aria-label="'+esc(opts.title||'')+'">'+segs+
    '<text x="75" y="74" text-anchor="middle" class="dn-mid">'+esc(mid)+'</text>'+
    '<text x="75" y="92" text-anchor="middle" class="dn-sub">'+esc(opts.sub||'')+'</text></svg>'+
    '<div class="dn-leg">'+(opts.title?'<h3>'+esc(opts.title)+'</h3>':'')+items.map(function(x,i){
      return '<div><i style="background:'+DN_COLORS[i%DN_COLORS.length]+'"></i><span title="'+esc(x.name)+'">'+esc(x.name)+'</span><b>'+
        (x.value/total*100).toFixed(x.value/total<0.1?1:0)+'%'+(opts.fmt?' <span class="muted">'+opts.fmt(x.value)+'</span>':'')+'</b></div>'; }).join('')+'</div>'; }
"""
