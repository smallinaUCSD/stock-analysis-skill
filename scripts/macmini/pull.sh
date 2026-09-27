#!/usr/bin/env bash
# Pull the latest code without tripping over the local price cache (run by update.sh as the app user).
# The daily refresh rewrites the committed snapshot and the market crawl adds files for other stocks;
# drop local copies of anything the pull would bring in so it can't conflict.
set -euo pipefail
cd "$(dirname "$0")/../.."
git restore data/cache 2>/dev/null || git checkout -- data/cache
git fetch -q
git diff --name-only --diff-filter=A HEAD '@{u}' -- data/cache | while IFS= read -r f; do
  if [ -e "$f" ] && ! git ls-files --error-unmatch "$f" >/dev/null 2>&1; then rm -f "$f"; fi
done
git pull --ff-only
