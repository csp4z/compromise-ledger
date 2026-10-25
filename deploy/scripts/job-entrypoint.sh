#!/bin/sh
# On a fresh install, build everything once so the site isn't empty until the first schedule.
set -u
if [ ! -e /srv/site/current ]; then
    echo "== first start: running the daily job now"
    /app/deploy/scripts/daily.sh
fi
exec supercronic -passthrough-logs /app/deploy/crontab
