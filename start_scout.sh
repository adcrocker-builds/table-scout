#!/bin/bash
# ─────────────────────────────────────────────────────────
# Weekly Restaurant Scout — Setup Script
# Run this ONCE to schedule the Monday morning report.
# ─────────────────────────────────────────────────────────

echo ""
echo "🍽️  Setting up Weekly Restaurant Scout..."
echo ""

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_SOURCE="$SCRIPT_DIR/com.weekscout.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.weekscout.plist"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Install it from https://www.python.org/downloads/"
    exit 1
fi
PYTHON_PATH=$(which python3)
echo "✅ Found Python at: $PYTHON_PATH"

# Check beautifulsoup4 is installed
if ! "$PYTHON_PATH" -c "import bs4" &> /dev/null; then
    echo "📦 Installing beautifulsoup4..."
    "$PYTHON_PATH" -m pip install beautifulsoup4 --quiet
fi

# Fill in the correct Python path in the plist
sed -i '' "s|/usr/bin/python3|$PYTHON_PATH|g" "$PLIST_SOURCE"
sed -i '' "s|REPLACE_WITH_YOUR_PATH|$SCRIPT_DIR|g" "$PLIST_SOURCE"

# Install plist
mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SOURCE" "$PLIST_DEST"
launchctl unload "$PLIST_DEST" 2>/dev/null
launchctl load "$PLIST_DEST"

if [ $? -eq 0 ]; then
    echo "✅ Weekly scout scheduled! It will run every Monday at 7:00 AM."
    echo ""
    echo "   To run it right now as a test:"
    echo "   python3 $SCRIPT_DIR/weekly_scout.py --test"
    echo ""
    echo "   To stop it:"
    echo "   bash $SCRIPT_DIR/stop_scout.sh"
    echo ""
else
    echo "❌ Something went wrong loading the plist."
    echo "   Try pasting any error above into Claude for help."
fi
