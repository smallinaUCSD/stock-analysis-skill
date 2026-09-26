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
scp .env holdings.csv stockskill@stocks-mini.local:~/stock-analysis-skill/
scp data/added.json stockskill@stocks-mini.local:~/stock-analysis-skill/data/
```

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

## Text alerts by iMessage (free)

The site can send its text alerts (summaries, big moves, politician trades,
sign-in alerts, confirmation codes) as iMessages from this Mac instead of
paying for Twilio. macOS only lets a logged-in user's session control
Messages, so a small helper does the sending:

1. Log in on the Mac mini's screen (or Screen Sharing) with the account that
   should send the texts, open **Messages** and sign in to iMessage. A
   separate Apple ID just for the site is best, so texts don't come from your
   personal number.
2. In Terminal, as that account (no sudo), with your own number for a test:

   ```bash
   ~/stock-analysis-skill/scripts/macmini/imessage_setup.sh +15551234567
   ```

   (Use the repo's real path if it lives in another user's home.) macOS asks
   whether the helper may control Messages: click **OK**.
3. Turn on **System Settings > Users & Groups > Automatically log in as** that
   account, so the helper is back after a restart.

The admin page shows "Text messages: iMessage" when it's working. iMessages
only reach iPhones, iPads and Macs; for other phones, set up Twilio (see
`.env.example`), which is used whenever the iMessage helper isn't running.
Failed sends are kept for 7 days in `/Users/Shared/smi-imessage/failed/`.
