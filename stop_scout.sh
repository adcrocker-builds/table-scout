#!/bin/bash
# ─────────────────────────────────────────────────────────
# Weekly Scout — Stop Script
# ─────────────────────────────────────────────────────────

PLIST_DEST="$HOME/Library/LaunchAgents/com.weekscout.plist"

echo ""
echo "🛑 Stopping Weekly Restaurant Scout..."
launchctl unload "$PLIST_DEST" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Scout stopped. Run start_scout.sh to restart it."
else
    echo "⚠️  Scout may not have been running, or was already stopped."
fi
echo ""
