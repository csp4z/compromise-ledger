#!/bin/sh
# Starts the Dagster daemon (schedules, sensors, and the runs themselves) or the web UI.
# Usage: dagster-entrypoint.sh daemon|webserver
set -eu
cp /app/deploy/dagster/dagster.yaml /app/deploy/dagster/workspace.yaml "${DAGSTER_HOME}/"
workspace="${DAGSTER_HOME}/workspace.yaml"
case "${1:-}" in
    daemon)
        # On a fresh install, build everything once so the site isn't empty until the schedule.
        if [ ! -e /srv/site/current ]; then
            echo "== first start: running the daily job now"
            dagster job execute -w "${workspace}" -j daily || echo "== first run failed; see the UI"
        fi
        exec dagster-daemon run -w "${workspace}"
        ;;
    webserver)
        exec dagster-webserver -w "${workspace}" -h 0.0.0.0 -p 3000
        ;;
    *)
        echo "usage: $0 daemon|webserver" >&2
        exit 2
        ;;
esac
