#!/data/data/com.termux/files/usr/bin/bash
# Fit-ingo — one-time Termux setup.
# Installs Python + Termux:API CLI and the server's Python deps.
set -e

echo "==> Updating packages"
pkg update -y
pkg install -y python termux-api

# Storage access (optional, lets you keep the DB on shared storage if you want).
termux-setup-storage || true

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "==> Installing Python requirements"
pip install --upgrade pip
pip install -r "$REPO_DIR/server/requirements.txt"

echo
echo "Setup complete."
echo "Next steps:"
echo "  1. Install the 'Termux:API' app (F-Droid) so notifications work."
echo "  2. (Optional) Install 'Termux:Boot' to auto-start on reboot — see termux/boot/."
echo "  3. Run:  bash termux/start.sh"
echo "  4. Open Chrome at http://localhost:8777 and 'Add to Home screen'."
