#!/bin/bash
# Wrapper invoked by cron/launchd. Regenerates the dashboard with fresh data.
# cron runs with a minimal PATH, so use absolute paths.
set -uo pipefail

PROJECT="/Volumes/Data/stock-analysis-skill"
UV="/Users/smallina/.local/bin/uv"

cd "$PROJECT" || exit 1
mkdir -p "$PROJECT/.cache"

"$UV" run stockskill dashboard \
    --out "$PROJECT/dashboard.html" \
    --holdings "$PROJECT/holdings.csv" \
    --price-map "$PROJECT/.cache/pm.json" \
    --refresh \
    --interval 30 \
    >> "$PROJECT/.cache/dashboard.log" 2>&1
