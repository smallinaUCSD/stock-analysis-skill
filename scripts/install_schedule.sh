#!/bin/bash
# Install the market-hours cron schedule for the dashboard. Idempotent:
# re-running replaces the existing stockskill entry rather than duplicating it.
#
#   0,30 9-16 * * 1-5  ->  9:00, 9:30, ... 16:00, 16:30 ET, Mon-Fri
#   = pre-open + every 30 min intraday + close, weekdays only.
#
# macOS note: cron may need Full Disk Access. If the dashboard stops updating,
# add /usr/sbin/cron under System Settings > Privacy & Security > Full Disk Access.
set -euo pipefail

PROJECT="/Volumes/Data/stock-analysis-skill"
WRAPPER="$PROJECT/scripts/run_dashboard.sh"
MARK="# stockskill-dashboard"

chmod +x "$WRAPPER"

CRON_LINE="0,30 9-16 * * 1-5 $WRAPPER $MARK"

# Preserve other crontab entries; drop any prior stockskill line; add ours.
( crontab -l 2>/dev/null | grep -v "$MARK" || true; echo "$CRON_LINE" ) | crontab -

echo "Installed. Active stockskill schedule:"
crontab -l | grep "$MARK"
echo
echo "Dashboard: $PROJECT/dashboard.html   (open it once; it auto-refreshes)"
echo "Logs:      $PROJECT/.cache/dashboard.log"
