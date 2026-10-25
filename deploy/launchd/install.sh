#!/bin/sh
# Schedules `ledger run daily` on macOS with launchd, for the current user.
#   install.sh install    install or update the job (CL_DAILY_HOUR / CL_DAILY_MINUTE, local time)
#   install.sh uninstall  remove it
#   install.sh run        start a run now
#   install.sh status     show whether it is loaded and its last exit code
set -eu

LABEL="io.github.csp4z.compromise-ledger.daily"
REPO=$(cd "$(dirname "$0")/../.." && pwd)
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"
HOUR=${CL_DAILY_HOUR:-21}
MINUTE=${CL_DAILY_MINUTE:-30}

case "${1:-}" in
install)
    [ -x "$REPO/.venv/bin/ledger" ] || { echo "No $REPO/.venv/bin/ledger: run 'make dev' first." >&2; exit 1; }
    case "$REPO" in *[\&\<\>\|]*) echo "Repository path contains characters this script can't escape." >&2; exit 1;; esac
    mkdir -p "$REPO/.lake/logs" "$HOME/Library/LaunchAgents"
    sed -e "s|@LABEL@|$LABEL|g" -e "s|@REPO@|$REPO|g" -e "s|@HOUR@|$HOUR|g" -e "s|@MINUTE@|$MINUTE|g" \
        "$REPO/deploy/launchd/daily.plist.in" > "$PLIST"
    plutil -lint -s "$PLIST"
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$PLIST"
    printf 'Scheduled daily at %02d:%02d local time. Log: %s\n' "$HOUR" "$MINUTE" "$REPO/.lake/logs/daily.log"
    ;;
uninstall)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Removed $LABEL."
    ;;
run)
    launchctl kickstart "$DOMAIN/$LABEL"
    echo "Started. Follow with: tail -f $REPO/.lake/logs/daily.log"
    ;;
status)
    launchctl print "$DOMAIN/$LABEL" | grep -E '^\s*(state|last exit code|runs) ' || echo "Not loaded."
    ;;
*)
    sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
