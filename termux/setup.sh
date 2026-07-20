#!/data/data/com.termux/files/usr/bin/bash
# Fit-ingo — one-time Termux setup.
# Installs Python + Termux:API CLI and the server's Python deps.
set -e

echo "==> Updating packages"
pkg update -y
# curl powers the "+250 ml" button on water reminders.
pkg install -y python termux-api curl

# Storage access (optional, lets you keep the DB on shared storage if you want).
termux-setup-storage || true

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "==> Installing Python requirements"
#pip install --upgrade pip
pip install -r "$REPO_DIR/server/requirements.txt"

echo "==> Checking Termux:API setup"
if command -v termux-notification >/dev/null 2>&1; then
  echo "  ✓ Termux:API CLI detected. Attempting test notification..."
  termux-notification --title "Fit-ingo" --content "Setup OK — notifications work! 🔥" || echo "  (notification command found but failed — see termux/TROUBLESHOOTING.md)"
else
  echo "  ⚠ termux-notification NOT found."
  echo "  The termux-api package (pkg install termux-api) and the Termux:API app"
  echo "  (from F-Droid, same source as Termux) are both required for notifications."
  echo "  See termux/TROUBLESHOOTING.md for details."
fi

echo
echo "Setup complete."
echo "Next steps:"
echo "  1. Install the 'Termux:API' app (F-Droid) so notifications work."
echo "  2. (Optional) Install 'Termux:Boot' to auto-start on reboot — see termux/boot/."
echo "  3. Run:  bash termux/start.sh"
echo "  4. Open Chrome at http://localhost:8777 and 'Add to Home screen'."
