# GitHub Actions (automation)

Three workflows in `.github/workflows/`:

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | push / PR | Runs `uv run pytest` — continuous testing. |
| `dashboard.yml` | every 30 min, market hours (weekdays) + manual | Renders the **watchlist** dashboard and publishes it to **GitHub Pages**. |
| `refresh-watchlist.yml` | daily ~08:00 ET (weekdays) + manual | Rebuilds the dynamic `data/smart_tickers.csv` and commits it, so the dashboard renders a fresh growth/value/sector list. |

## One-time setup
1. **Merge to `main`.** Scheduled workflows only run from the default branch, so
   these take effect after this branch is merged.
2. **Enable Pages:** repo **Settings → Pages → Source: GitHub Actions**.
3. **Actions permissions:** Settings → Actions → General → allow workflows to run
   and (for the refresh workflow) "Read and write permissions".
4. First run: trigger `dashboard.yml` manually (Actions tab → Run workflow). The
   published URL appears on the workflow's `github-pages` environment.

## Privacy — deliberate
Only the **watchlist** (public tickers, purely public-data analysis) is
published. The **portfolio dashboard is never published** — it contains real
holdings, and `holdings.csv` is gitignored so CI can't see it regardless.

## Notes / caveats
- **yfinance from cloud runners** can be rate-limited or blocked by Yahoo
  (datacenter IPs). If a run produces an empty dashboard, that's usually why —
  re-run, or reduce the ticker count.
- GitHub cron is UTC and best-effort (runs can be delayed or skipped under load);
  `dashboard.yml` uses `*/30 13-21 * * 1-5` to cover US market hours year-round.
- `refresh-watchlist.yml` commits to the default branch (`[skip ci]` so it
  doesn't retrigger CI). Disable it if you'd rather not have bot commits.
- This is the cloud analogue of the local cron (`scripts/install_schedule.sh`);
  use whichever you prefer, or both.
