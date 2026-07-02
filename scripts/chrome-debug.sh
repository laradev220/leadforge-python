#!/usr/bin/env bash
# Start Chrome with remote debugging enabled for LeadForge social profiling.
#
# Usage:
#   ./scripts/chrome-debug.sh
#
# This opens Chrome with your existing profile (logged-in sessions)
# and enables CDP on port 9222 so the social worker can crawl
# social profiles using your authenticated sessions.
#
# Prerequisites:
#   - Close ALL Chrome windows first (Chrome won't reuse an existing instance)
#   - Log into LinkedIn, Instagram, Facebook, etc. in this Chrome session

set -euo pipefail

PORT=9222
PROFILE_DIR="$HOME/.config/google-chrome"

# Detect Chrome binary
CHROME=""
for candidate in \
    google-chrome \
    google-chrome-stable \
    /usr/bin/google-chrome \
    /usr/bin/google-chrome-stable \
    /opt/google/chrome/chrome \
    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    chromium-browser \
    chromium; do
    if command -v "$candidate" &>/dev/null || [ -x "$candidate" ]; then
        CHROME="$candidate"
        break
    fi
done

if [ -z "$CHROME" ]; then
    echo "Error: Chrome/Chromium not found. Install it first."
    exit 1
fi

echo "Starting Chrome with remote debugging on port $PORT..."
echo "Profile: $PROFILE_DIR"
echo ""
echo "IMPORTANT: Close all Chrome windows first, or this will fail."
echo "After Chrome opens, log into your social platforms."
echo ""

exec "$CHROME" \
    --remote-debugging-port="$PORT" \
    --user-data-dir="$PROFILE_DIR" \
    --no-first-run \
    --disable-default-apps \
    --disable-popup-blocking \
    --disable-translate \
    --disable-background-timer-throttling \
    --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding \
    "$@"
