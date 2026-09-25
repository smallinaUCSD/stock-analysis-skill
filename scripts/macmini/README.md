# Always-on board on a Mac mini

Runs the app at boot (no login needed), restarts it if it crashes, refreshes
prices every weekday, and publishes it with Tailscale.

| Service | What | Where |
|---|---|---|
| `com.stockskill.public` | the shared site (no Holdings/Alerts) | `https://<mac>.<tailnet>.ts.net` (anyone) |
| `com.stockskill.private` | your copy with Holdings + Alerts | `https://<mac>.<tailnet>.ts.net:8443` (your Tailscale devices only) |
| `com.stockskill.refresh` | price snapshot update | weekdays 7:00 and 16:10, Mac's local time |

Both servers listen on 127.0.0.1 only, so nothing on your network reaches them
except through Tailscale. They run as a standard user, not root.

## One-time setup

As the **app user** (e.g. `stockskill`):

```bash
git clone https://github.com/smallinaUCSD/stock-analysis-skill.git ~/stock-analysis-skill
curl -LsSf https://astral.sh/uv/install.sh | sh
```

From your laptop, copy the files that aren't in git (never email them):

```bash
scp .env holdings.csv data/added.json stockskill@stocks-mini.local:~/stock-analysis-skill/
```

(`data/added.json` goes in the `data/` folder; move it after copying.)

As the **admin** user:

```bash
brew install tailscale
sudo /Users/stockskill/stock-analysis-skill/scripts/macmini/install.sh stockskill
```

The installer prints a Tailscale sign-in link the first time, and a link to
turn on Funnel for your tailnet if it isn't on yet. Open them, then it finishes
and prints your two URLs. Install the Tailscale app on your phone and laptop
(same account) to open the private one.

For phone alerts, add `NTFY_TOPIC=...` to `.env` (see `/alerts`), then run
`update.sh` to restart.

## Day to day

```bash
sudo ~stockskill/stock-analysis-skill/scripts/macmini/status.sh     # is it up?
sudo ~stockskill/stock-analysis-skill/scripts/macmini/update.sh     # pull new code + restart
sudo ~stockskill/stock-analysis-skill/scripts/macmini/uninstall.sh  # remove the services
```

Logs are in `logs/` (trimmed to the last 5,000 lines daily).

The refresh times use the Mac's clock, so set its time zone to Eastern (or
shift the times in `install.sh`) so 16:10 lands after the US close.
