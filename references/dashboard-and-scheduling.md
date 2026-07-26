# Dashboard & scheduling

## The dashboard
`stockskill dashboard` writes a **self-contained HTML file** (`dashboard.html`)
— no external assets, works offline, theme-aware (light/dark follow the OS).
It combines the market pulse (regime tiles, breadth, sector & factor rotation)
with the portfolio look-through (equity, economic exposure, effective leverage,
top exposures, factor groups). A header badge shows market status
(OPEN / PRE-MARKET / AFTER HOURS / CLOSED / WEEKEND) from the ET market clock.

The page carries `<meta http-equiv="refresh">`, so an open tab reloads itself
on the interval — when the scheduler rewrites the file, the tab picks it up.

```bash
uv run stockskill dashboard --open                 # generate once and open it
uv run stockskill dashboard --watch --interval 30  # live: regenerate every 30 min
```

All values come from the same tested functions as the CLI — the dashboard only
formats. Returns use zero-centered diverging bars (direction + a numeric label
carry the sign, so meaning isn't color-alone).

## Scheduling (macOS cron)
For hands-off updates around the trading day:

```bash
./scripts/install_schedule.sh
```

Installs one idempotent cron entry:

```
0,30 9-16 * * 1-5   ->   9:00, 9:30, ... 16:00, 16:30 ET, Mon-Fri
```

That's **pre-open (9:00) + every 30 min intraday + close (16:00/16:30)**, on
weekdays only. The wrapper (`scripts/run_dashboard.sh`) re-fetches fresh data
each run and regenerates **both** dashboards:
- `dashboard.html` — market pulse + your portfolio (logs to `.cache/dashboard.log`)
- `watchlist.html` — the multi-ticker technical dashboard (logs to `.cache/watchlist.log`)

Open either once and leave the tab open; each refreshes itself via a meta tag.

Remove it with `./scripts/uninstall_schedule.sh`.

**macOS caveat:** cron may need Full Disk Access. If the file stops updating,
add `/usr/sbin/cron` under System Settings → Privacy & Security → Full Disk
Access. The market clock is ET-based, so the schedule tracks the exchange even
if the Mac's timezone changes — but the cron *times* are in the machine's local
time, so if you leave ET, re-point the hours or switch to the `--watch` mode.

**Holidays:** the clock does not model exchange holidays — a holiday shows as a
normal weekday (the data simply won't move). Fine for a personal dashboard.

## No system change? Use `--watch`
`uv run stockskill dashboard --watch --interval 30` runs a foreground loop that
regenerates on the interval with zero cron/launchd setup — good when you just
want it live while you work. The scheduled cron path is better for
set-and-forget around open/close.
