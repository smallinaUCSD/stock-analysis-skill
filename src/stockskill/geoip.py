"""Approximate location (city, region, country) for an IP address, looked up
on this server in DB-IP's free "IP to City Lite" database, so addresses are
never sent to a third party.

The database (~125 MB, CC BY 4.0: "IP Geolocation by DB-IP") is downloaded
in the background when STOCKSKILL_GEOIP=1 and refreshed monthly. Without it,
lookups return {} and pages show "Unknown".
"""

from __future__ import annotations

import gzip
import ipaddress
import os
import shutil
import threading
import time
from datetime import date
from functools import lru_cache

ATTRIBUTION = '<a href="https://db-ip.com" target="_blank" rel="noopener">IP Geolocation by DB-IP</a>'
_URL = "https://download.db-ip.com/free/dbip-city-lite-{ym}.mmdb.gz"
_READER: dict = {"r": None, "mtime": 0.0}
_LOCK = threading.Lock()


def db_path() -> str:
    return os.environ.get("STOCKSKILL_GEOIP_DB") or "data/geo/dbip-city-lite.mmdb"


def _months() -> list[str]:
    d = date.today()
    prev = date(d.year - 1, 12, 1) if d.month == 1 else date(d.year, d.month - 1, 1)
    return [d.strftime("%Y-%m"), prev.strftime("%Y-%m")]


def ensure_db(max_age_days: float = 35.0) -> bool:
    """Download the database if it's missing or over a month old. True if one is ready."""
    p = db_path()
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < max_age_days * 86400:
        return True
    import requests
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    tmp = p + ".download"
    for ym in _months():                        # this month's file appears on the 1st
        try:
            with requests.get(_URL.format(ym=ym), stream=True, timeout=60) as r:
                if r.status_code != 200:
                    continue
                with open(tmp + ".gz", "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            with gzip.open(tmp + ".gz", "rb") as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            import maxminddb
            maxminddb.open_database(tmp).close()    # refuse a broken file
            os.replace(tmp, p)
            lookup.cache_clear()
            return True
        except Exception:  # noqa: BLE001
            continue
        finally:
            for f in (tmp + ".gz", tmp):
                if os.path.exists(f):
                    os.remove(f)
    return os.path.exists(p)


def keep_current() -> None:
    """Background: fetch now if needed, then check daily."""
    def loop():
        while True:
            try:
                ensure_db()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(86400)
    threading.Thread(target=loop, daemon=True).start()


def _reader():
    p = db_path()
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return None
    with _LOCK:
        if _READER["r"] is None or _READER["mtime"] != mt:
            import maxminddb
            try:
                _READER["r"] = maxminddb.open_database(p)
                _READER["mtime"] = mt
            except Exception:  # noqa: BLE001
                _READER["r"] = None
        return _READER["r"]


def is_public(ip: str) -> bool:
    try:
        a = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return False
    return a.is_global


@lru_cache(maxsize=4096)
def lookup(ip: str) -> dict:
    """{"city", "region", "country", "cc"} (any may be missing), or {}."""
    if not is_public(ip):
        return {}
    r = _reader()
    if r is None:
        return {}
    try:
        rec = r.get(ip.strip()) or {}
    except Exception:  # noqa: BLE001
        return {}

    def name(x):
        return ((x or {}).get("names") or {}).get("en")
    out = {"city": name(rec.get("city")), "region": name((rec.get("subdivisions") or [{}])[0]),
           "country": name(rec.get("country")), "cc": (rec.get("country") or {}).get("iso_code")}
    return {k: v for k, v in out.items() if v}


def label(g: dict | None) -> str:
    """'Austin, Texas, United States' (or as much as is known)."""
    g = g or {}
    parts = [g.get("city"), g.get("region"), g.get("country")]
    seen, out = set(), []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return ", ".join(out)
