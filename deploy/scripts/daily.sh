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
echo "== daily job finished with status ${status}"
exit "${status}"
