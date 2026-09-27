"""Photos of the people who run the tracked funds (people recognize faces
faster than firm names), from Wikipedia.

Only freely licensed photos on Wikimedia Commons are used, each with its
author and license credited and linked, as those licenses require; a
manager without one keeps the initials. Looked up in the background and
saved for 30 days (<cache>/_13f/photos.json); pages only read the file.
"""

from __future__ import annotations

import html
import json
import os
import re
import time
from urllib.parse import quote, unquote

# the manager's Wikipedia article, where it isn't just their name
TITLES = {"Jim Simons' firm": "Jim Simons (mathematician)", "Chase Coleman": "Chase Coleman III",
          "Dan Loeb": "Daniel S. Loeb", "Steve Cohen": "Steven A. Cohen", "Paul Singer": "Paul Singer (businessman)",
          "Gates Foundation": "Bill Gates", "Stephen Mandel": "Stephen Mandel", "Ken Griffin": "Kenneth C. Griffin"}
MAX_AGE = 30 * 86400
RETRY_AGE = 6 * 3600                                 # a lookup cut short by rate limits is retried sooner


class RateLimited(Exception):
    pass


def _path(cache_dir) -> str:
    from .funds13f import _dir
    return os.path.join(_dir(cache_dir), "photos.json")


def load(cache_dir=None) -> dict:
    """{manager: {img, page, credit, license, file_page}} (only those with a free photo)."""
    try:
        return json.load(open(_path(cache_dir))).get("photos") or {}
    except (OSError, ValueError):
        return {}


def _ua() -> str:
    who = os.environ.get("STOCKSKILL_CONTACT_EMAIL") or os.environ.get("STOCKSKILL_PUBLIC_URL") or "self-hosted"
    return f"SMInvestments/1.0 (stock research site; {who})"


def _plain(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def lookup(name: str, get=None) -> dict | None:
    """One manager's free photo with credit, or None."""
    import requests
    get = get or (lambda url, **kw: requests.get(url, headers={"User-Agent": _ua()}, timeout=15, **kw))
    title = TITLES.get(name, name)
    r = get("https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(title.replace(" ", "_")))
    if getattr(r, "status_code", 0) == 429:
        raise RateLimited()
    if getattr(r, "status_code", 0) != 200:
        return None
    s = r.json()
    thumb = (s.get("thumbnail") or {}).get("source") or ""
    if s.get("type") != "standard" or "/wikipedia/commons/" not in thumb:
        return None                                   # no photo, or a local (usually non-free) one
    m = re.search(r"/commons/thumb/[0-9a-f]/[0-9a-f]{2}/([^/]+)/", thumb) or re.search(r"/commons/[0-9a-f]/[0-9a-f]{2}/([^/?]+)", thumb)
    if not m:
        return None
    fname = unquote(m.group(1))
    q = get("https://commons.wikimedia.org/w/api.php", params={
        "action": "query", "titles": "File:" + fname, "prop": "imageinfo", "iiprop": "extmetadata", "format": "json"})
    if getattr(q, "status_code", 0) == 429:
        raise RateLimited()
    if getattr(q, "status_code", 0) != 200:
        return None
    pages = (q.json().get("query") or {}).get("pages") or {}
    meta = next(iter(pages.values()), {}).get("imageinfo", [{}])[0].get("extmetadata", {})
    lic = _plain((meta.get("LicenseShortName") or {}).get("value"))
    if not lic or re.search(r"fair use|non-?free", lic, re.I):
        return None
    return {"img": thumb.split("?")[0], "page": ((s.get("content_urls") or {}).get("desktop") or {}).get("page"),
            "credit": _plain((meta.get("Artist") or {}).get("value"))[:80] or "Wikimedia Commons",
            "license": lic, "file_page": "https://commons.wikimedia.org/wiki/File:" + quote(fname.replace(" ", "_"))}


def refresh(managers: list[str], cache_dir=None, get=None, force: bool = False) -> dict:
    """Look up any missing or month-old photos and save them."""
    p = _path(cache_dir)
    try:
        saved = json.load(open(p))
        age = time.time() - saved.get("fetched", 0)
        if not force and age < (RETRY_AGE if saved.get("incomplete") else MAX_AGE):
            return saved.get("photos") or {}
    except (OSError, ValueError):
        saved = {}
    out, incomplete = dict(saved.get("photos") or {}), False
    for name in managers:
        ph = None
        for attempt in range(3):
            try:
                ph = lookup(name, get)
                break
            except RateLimited:
                time.sleep(15 * (attempt + 1))        # Wikipedia asked us to slow down
            except Exception:  # noqa: BLE001
                break
        else:
            incomplete = True                         # still refused: keep what we had, try again later
            break
        if ph:
            out[name] = ph
        time.sleep(1.5)                               # be gentle with Wikipedia
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"fetched": time.time(), "incomplete": incomplete, "photos": out}, f)
    os.replace(tmp, p)
    return out
