#!/bin/bash
# ─────────────────────────────────────────────────────────
# Reservation Monitor — Stop Script
# Run this to stop the monitor from running in the background.
# ─────────────────────────────────────────────────────────

PLIST_DEST="$HOME/Library/LaunchAgents/com.reservationmonitor.plist"

echo ""
echo "🛑 Stopping Reservation Monitor..."

launchctl unload "$PLIST_DEST" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Monitor stopped. It will not run again until you run start_monitor.sh"
else
    echo "⚠️  Monitor may not have been running, or was already stopped."
fi
echo ""
