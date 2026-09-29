"""Load test with a realistic request mix: how many requests a second the server
handles, and its median / p95 / p99 latency, as simultaneous clients grow.

    uv run python scripts/loadtest.py http://127.0.0.1:8787 cookies.txt [1,4,8,16,32,64]

cookies.txt is a signed-in session (Netscape format), e.g. for a TEST account:
    curl -c cookies.txt -H 'Content-Type: application/json' \
         -d '{"email":"...","password":"..."}' http://127.0.0.1:8787/auth/login
Each step runs 20 seconds at full speed, so run it when nobody is using the
site. NOWARM=1 skips warming the caches first."""
import http.cookiejar
import random
import statistics
import sys
import threading
import time

import requests

BASE = sys.argv[1]
jar = http.cookiejar.MozillaCookieJar(sys.argv[2])
jar.load(ignore_discard=True, ignore_expires=True)

TICKERS = "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,AVGO,AMD,QCOM,INTC,MRVL,AMAT,MU"
MIX = [  # (weight, name, path, signed_in)
    (35, "board-meta poll", "/api/board/meta", True),
    (20, "live quotes", "/api/quotes", True),
    (10, "after-hours poll", f"/api/ext?t={TICKERS}", True),
    (10, "board page", "/", True),
    (8, "search", "/api/find?q=nvid", True),
    (5, "stock page", "/analysis/{t}", True),
    (5, "calendar data", "/api/calendar", True),
    (4, "calendar page", "/calendar", True),
    (3, "landing (signed out)", "/", False),
]
STOCKS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD"]
W = [m[0] for m in MIX]


def worker(stop, out, errs):
    s_in, s_out = requests.Session(), requests.Session()
    s_in.cookies = jar
    while not stop.is_set():
        _, name, path, signed = random.choices(MIX, W)[0]
        path = path.replace("{t}", random.choice(STOCKS))
        t0 = time.perf_counter()
        try:
            r = (s_in if signed else s_out).get(BASE + path, timeout=60)
            ok = r.status_code < 500
        except Exception:  # noqa: BLE001
            ok = False
        dt = time.perf_counter() - t0
        (out if ok else errs).append((name, dt))


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))] if xs else float("nan")


def run(conc, secs):
    stop, out, errs = threading.Event(), [], []
    th = [threading.Thread(target=worker, args=(stop, out, errs), daemon=True) for _ in range(conc)]
    for t in th:
        t.start()
    time.sleep(secs)
    stop.set()
    for t in th:
        t.join(70)
    lat = [d for _, d in out]
    return out, errs, {"conc": conc, "rps": len(out) / secs, "p50": statistics.median(lat) if lat else 0,
                       "p95": pct(lat, 95), "p99": pct(lat, 99), "err": len(errs)}


if __name__ == "__main__":
    import os
    if not os.environ.get("NOWARM"):
        for p in ["/", "/api/calendar", "/calendar"] + [f"/analysis/{t}" for t in STOCKS]:   # warm caches
            requests.get(BASE + p, cookies=jar, timeout=120)
    print(f"{'clients':>7} {'req/s':>7} {'p50 ms':>8} {'p95 ms':>8} {'p99 ms':>8} {'errors':>6}")
    per = {}
    for conc in [int(c) for c in (sys.argv[3] if len(sys.argv) > 3 else "1,4,8,16,32,64").split(",")]:
        out, errs, r = run(conc, 20)
        print(f"{r['conc']:>7} {r['rps']:>7.1f} {r['p50']*1000:>8.0f} {r['p95']*1000:>8.0f} {r['p99']*1000:>8.0f} {r['err']:>6}", flush=True)
        if conc == 16:
            for name, d in out:
                per.setdefault(name, []).append(d)
    if per:
        print("\nper endpoint at 16 clients:")
        for name, ds in sorted(per.items(), key=lambda x: -pct(x[1], 95)):
            print(f"  {name:<22} n={len(ds):>5}  p50 {statistics.median(ds)*1000:>6.0f} ms  p95 {pct(ds, 95)*1000:>6.0f} ms  p99 {pct(ds, 99)*1000:>6.0f} ms")
