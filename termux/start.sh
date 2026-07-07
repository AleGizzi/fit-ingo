#!/data/data/com.termux/files/usr/bin/bash
# Fit-ingo — start the local server.
# Holds a wake-lock so the reminder scheduler keeps running with the screen off.
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Keep the DB in the app's home so it survives app updates and stays private.
export FITINGO_DB="${FITINGO_DB:-$HOME/fit-ingo/data/fitingo.db}"
export FITINGO_PORT="${FITINGO_PORT:-8777}"
mkdir -p "$(dirname "$FITINGO_DB")"

# Prevent Android from suspending the process (so reminders fire on time).
termux-wake-lock || true

echo "Fit-ingo running at http://localhost:$FITINGO_PORT  (DB: $FITINGO_DB)"
echo "Press Ctrl-C to stop."
cd "$REPO_DIR/server"
exec python app.py
