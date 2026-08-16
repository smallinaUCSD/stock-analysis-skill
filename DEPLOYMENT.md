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

### Deploy to a container host (example: Render)

1. Add a production WSGI server (gunicorn) — one dep, run:
   `gunicorn -w 2 -k gthread --threads 8 -t 120 "stockskill.server:create_app()"`
   (create_app reads `STOCKSKILL_PUBLIC` / `STOCKSKILL_BMC_URL` from the env).
2. Set env vars on the host: `STOCKSKILL_PUBLIC=1`, `STOCKSKILL_BMC_URL=…`,
   optionally `STOCKSKILL_CACHE_DIR` on a persistent disk.
3. Point the start command at the app; the host provides HTTPS + a URL.

> Note: with several workers each has its own cache and refetches. For real
> traffic, move to a shared cache (Redis/KV) and a background refresher, and
> switch to a licensed data API (Phase 1) so Yahoo doesn't rate-limit you.

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
