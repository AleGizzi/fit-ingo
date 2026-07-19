#!/data/data/com.termux/files/usr/bin/bash
# Fit-ingo — update the app on the phone.
# Pulls the latest build from GitHub, restarts the server, and lets the
# service worker pick up the new frontend on the next app launch.
#
# Run:  bash termux/update.sh
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

if ! [ -d .git ]; then
  echo "Not a git checkout: $REPO_DIR — clone the repo instead (see README)."
  exit 1
fi

echo "==> Fetching latest version..."
git fetch origin
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse '@{u}')

if [ "$LOCAL" = "$REMOTE" ]; then
  echo "Already up to date ($(git log -1 --format='%h %s'))."
else
  git pull --ff-only
  echo "Updated to: $(git log -1 --format='%h %s')"
  # Requirements rarely change, but when they do, forgetting this bricks the
  # server on the next start — cheap enough to always run.
  echo "==> Syncing Python requirements..."
  pip install -q -r server/requirements.txt
fi

VERSION=$(grep -o '"[0-9][0-9.]*"' frontend/src/lib/version.ts | tr -d '"')
echo "==> App version: ${VERSION:-unknown} (Settings ▸ Version should match after reopening the app)"

# Restart so the backend runs the new code. The frontend needs no restart to
# be *served* (Flask reads dist/ per request), but the phone's PWA shows it
# only after the service worker swaps builds — hence the note below.
echo "==> Restarting server..."
# start.sh execs `python app.py` from server/, so that's the cmdline to match.
pkill -f "python app.py" 2>/dev/null || true
sleep 1

cat <<'EOF'

Server restarting. Now open the Fit-ingo app:
  - it downloads the new version in the background (a few seconds),
  - then close and reopen it once — or use Settings ▸ Check for updates.
If Settings ▸ Version still shows the old number, reopen the app once more.

EOF

exec bash "$REPO_DIR/termux/start.sh"
