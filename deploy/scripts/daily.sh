#!/bin/sh
# The daily job on the server: refresh the data, rebuild the site, then back up.
# Later steps run even if a source failed, so the site and backups keep the last good data.
set -u
status=0
ledger run daily || status=$?
if [ -f "${CL_EXPORTS_DIR}/datasets.json" ]; then
    /app/deploy/scripts/publish-site.sh || status=1
fi
ledger backup "${CL_BACKUP_DIR:-/data/backups}" --keep "${CL_BACKUP_KEEP:-7}" || status=1
# `ledger run daily` pings healthchecks.io before the publish and the backup, so report any
# later failure too. The ping URL is a secret: pass it through the environment, never argv.
if [ "${status}" -ne 0 ] && [ -n "${CL_HEALTHCHECKS_URL:-}" ]; then
    python -c 'import os, httpx; httpx.get(os.environ["CL_HEALTHCHECKS_URL"].rstrip("/") + "/fail", timeout=15).raise_for_status()' \
        || echo "daily: healthchecks.io failure ping not delivered" >&2
fi
echo "== daily job finished with status ${status}"
exit "${status}"
