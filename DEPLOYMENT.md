# Deployment & the road to a SaaS

The goal: go from a personal, local tool to a multi-user app where people sign in
and pay. This doc captures the plan and how to run the **first step** — a safe,
public, read-only launch.

## Why not Vercel for the live app

Vercel is serverless: stateless, ephemeral filesystem, short (~10s) function
timeouts. This app is the opposite — a long-lived Flask process with in-memory +
on-disk caches that fetches 100+ tickers per rebuild (30–60s). On Vercel the cache
wouldn't persist, board builds would time out, and — the real blocker — **Yahoo
blocks datacenter IPs**, so yfinance mostly returns "no data" from cloud hosts.

Use an **always-on container host** (Render / Railway / Fly.io — all have free
tiers) for the live app, and a **licensed data API** instead of scraping Yahoo
once you have real users (see Phase 1).

## Phases

| Phase | What | You set up |
|---|---|---|
| **0. Safe public launch** *(now)* | Public mode (no holdings, no add-ticker) + Buy-me-a-coffee, on a container host | Host account |
| **1. Real data** | Data-provider seam → licensed API (Finnhub/Tiingo/Polygon free tier) | API key |
| **2. Auth** | Managed sign-in (Clerk / Supabase Auth / Auth0) | Auth account |
| **3. Database** | Per-user watchlists/holdings/settings in Postgres (holdings now safe) | Supabase / Neon |
| **4. Payments** | Stripe subscriptions (Checkout + Portal + webhooks), gate premium | Stripe account |

## Phase 0 — public mode (built in)

**Public mode** makes a shared deployment safe: it does NOT register the holdings
routes or the watchlist-mutation routes, and the board renders with **no Holdings
button and no add-ticker box**. Personal data can never be seen or changed. The
read-only analysis tools (Evaluate, Look-through, Monte Carlo, Indicators) stay.

Run it locally:

```bash
uv run stockskill serve --public            # or STOCKSKILL_PUBLIC=1
STOCKSKILL_BMC_URL=https://buymeacoffee.com/YOURNAME uv run stockskill serve --public
```

- `--public` / `STOCKSKILL_PUBLIC=1` — safe shared mode.
- `STOCKSKILL_BMC_URL` — shows a "☕ Buy me a coffee" button (get the link from
  buymeacoffee.com; the app only links out, it never handles payments).
- `holdings.csv` is never deployed and stays gitignored; the holdings routes
  simply don't exist in public mode.

### Deploy to Render (free, ~5 minutes)

The repo already ships everything: a `Dockerfile` (gunicorn + the public app), a
`.dockerignore` (never ships `holdings.csv`), and a `render.yaml` blueprint.

1. Push to GitHub (already done).
2. Go to **render.com** → sign in with GitHub → **New +** → **Blueprint**.
3. Pick this repo. Render reads `render.yaml` and creates a free web service that
   builds the `Dockerfile` and runs it with `STOCKSKILL_PUBLIC=1`.
4. (Optional) In the service's **Environment**, set `STOCKSKILL_BMC_URL` to your
   Buy-me-a-coffee link so the button appears.
5. Deploy. Render gives you `https://stockskill.onrender.com` (HTTPS included).
   Health check: `/healthz` returns `{"ok": true, "public": true}`.

Locally you can run the exact same server:

```bash
STOCKSKILL_PUBLIC=1 uv run gunicorn -w 1 -k gthread --threads 8 -t 120 \
  -b 0.0.0.0:8000 'stockskill.server:create_app()'
```

### Data snapshot (so the hosted site shows real data despite Yahoo IP-blocking)

Yahoo rate-limits datacenter IPs, so live fetches from Render often return "n/a".
The fix: build the data **locally** (your IP works) and ship it. The deploy is
configured to serve `data/cache/` (a committed snapshot) with a 7-day TTL, so it
never refetches from the blocked host.

**Refresh the snapshot before each deploy:**

```bash
# fetch the public tickers locally and write the cache the deploy serves
uv run stockskill watchlist --tickers data/public_tickers.csv \
  --cache-dir data/cache --period 1y --out /tmp/snapshot.html
git add data/cache && git commit -m "refresh data snapshot" && git push
```

Render redeploys on push, and the site shows your freshly-fetched data. (The data
is a snapshot — as fresh as your last local build. Live per-request data across
many users is Phase 1: a licensed API.)

**Free-tier caveats**
- The service **sleeps after ~15 min idle**; the first hit after that spins it up
  and builds the board (~1 min). Fine for a hobby launch.
- ~512 MB RAM → one gunicorn worker (the Dockerfile default). Bump workers only on
  a paid plan.
- **Yahoo may rate-limit the cloud IP.** The stale-while-error cache degrades
  gracefully (keeps last-good values), but for reliable traffic, do Phase 1
  (a licensed data API) before you rely on it.
- Railway / Fly.io work the same way from the `Dockerfile` if you prefer them.

### Alternative: static view-only board (GitHub Pages, already wired)
`.github/workflows/dashboard.yml` renders the board to static HTML and publishes
it to Pages during market hours (public tickers only — no holdings). Enable it at
**Settings → Pages → Source: GitHub Actions** (the workflow also tries to enable
it automatically). This is zero-server and reliable, but view-only — the live
tools/indicators need the server above.

## Considerations before charging money

- **Data licensing / ToS** — Yahoo restricts scraping & redistribution, more so
  commercially. Move to a licensed API before monetizing.
- **Not investment advice** — keep the disclaimers prominent; add a short
  Terms/Disclaimer page. Frame everything as analysis (you're not a licensed
  advisor).
- **Abuse / rate limits** — cache hard, rate-limit endpoints, prefer a fixed
  ticker universe so visitors can't drive unbounded fetches.
- **Secrets** — API/Stripe keys live in host env vars, never in the repo.
- **Multi-user state** — once there's auth + a DB, per-user watchlists/holdings
  replace the shared file; re-enable add-ticker scoped to the signed-in user.
