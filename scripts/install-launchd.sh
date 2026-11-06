#!/bin/sh
# Install (or reinstall) the weekly summary email as a launchd job.
# The address comes from WEEKLY_SUMMARY_EMAIL in .env / ~/.env at run time,
# so it never lands in the plist or the repo.
#   scripts/install-launchd.sh            Sundays 08:00
#   scripts/install-launchd.sh 1 7 30     weekday (0=Sunday), hour, minute
#   scripts/install-launchd.sh --uninstall
set -eu

LABEL=local.smart-oil-gauge.weekly-summary
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
REPO=$(cd "$(dirname "$0")/.." && pwd)

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$PLIST"
    echo "Removed $LABEL"
    exit 0
fi

WEEKDAY=${1:-0}
HOUR=${2:-8}
MINUTE=${3:-0}
mkdir -p "$REPO/logs"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$REPO/.venv/bin/python</string>
        <string>$REPO/src/smart_oil_gauge_mcp.py</string>
        <string>--send-summary</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>$WEEKDAY</integer>
        <key>Hour</key>
        <integer>$HOUR</integer>
        <key>Minute</key>
        <integer>$MINUTE</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$REPO/logs/weekly-summary.log</string>
    <key>StandardErrorPath</key>
    <string>$REPO/logs/weekly-summary.error.log</string>
</dict>
</plist>
PLIST
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed $LABEL (weekday $WEEKDAY, $HOUR:$(printf %02d "$MINUTE"))"
