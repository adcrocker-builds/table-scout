#!/bin/bash
# ─────────────────────────────────────────────────────────
# Reservation Monitor — Auto-Start Setup Script
# Run this ONCE to make the monitor start automatically.
# ─────────────────────────────────────────────────────────

echo ""
echo "🍽️  Setting up Reservation Monitor to run automatically..."
echo ""

# Find where the script lives
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_SOURCE="$SCRIPT_DIR/com.reservationmonitor.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.reservationmonitor.plist"

# Check Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed."
    echo "   Please go to https://www.python.org/downloads/ and install it first."
    exit 1
fi

PYTHON_PATH=$(which python3)
echo "✅ Found Python at: $PYTHON_PATH"

# Fill in the real paths in the plist file
sed -i '' "s|REPLACE_WITH_YOUR_PATH|$SCRIPT_DIR|g" "$PLIST_SOURCE"
sed -i '' "s|/usr/bin/python3|$PYTHON_PATH|g" "$PLIST_SOURCE"

# Create LaunchAgents folder if it doesn't exist
mkdir -p "$HOME/Library/LaunchAgents"

# Copy plist to the right place
cp "$PLIST_SOURCE" "$PLIST_DEST"

# Unload first in case it's already running
launchctl unload "$PLIST_DEST" 2>/dev/null

# Load it
launchctl load "$PLIST_DEST"

if [ $? -eq 0 ]; then
    echo "✅ Success! The monitor is now running in the background."
    echo ""
    echo "   It will:"
    echo "   • Start automatically every time your Mac starts up"
    echo "   • Run silently — no Terminal window needed"
    echo "   • Text you when a reservation opens up"
    echo ""
    echo "   To check it's working, look at the log file:"
    echo "   $SCRIPT_DIR/monitor.log"
    echo ""
    echo "   To stop it at any time, run: bash stop_monitor.sh"
    echo ""
else
    echo "❌ Something went wrong. Try running Terminal as an admin, or"
    echo "   paste any error above into Claude for help."
fi
