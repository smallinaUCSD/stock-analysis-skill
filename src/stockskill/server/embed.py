"""Lets a research page run inside the stock page's tabs (?embed=1): hides its
own header and search bar and tells the parent page how tall it is."""

EMBED_CSS = """
html.embed header,html.embed .page-x,html.embed .fa-bar,html.embed .er-bar,html.embed .kg-bar,html.embed .fa-title,
html.embed .er-title,html.embed .kg-title{display:none!important}
html.embed .wrap{padding-top:4px}
html.embed body{background:transparent}
"""

EMBED_JS = r"""
(function(){ if(!/[?&]embed=1\b/.test(location.search)) return;
  document.documentElement.classList.add('embed');
  function tell(){ try{ parent.postMessage({embedHeight:document.documentElement.scrollHeight}, location.origin); }catch(_){} }
  if(window.ResizeObserver) new ResizeObserver(tell).observe(document.documentElement);
  window.addEventListener('load', tell); setTimeout(tell, 300); setTimeout(tell, 1500);
})();
"""
