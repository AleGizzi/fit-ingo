#!/data/data/com.termux/files/usr/bin/bash
# Termux:Boot autostart hook.
#
# Install:
#   1. Install the "Termux:Boot" app (F-Droid) and open it once.
#   2. Copy this file to ~/.termux/boot/ and make it executable:
#        mkdir -p ~/.termux/boot
#        cp termux/boot/fit-ingo.sh ~/.termux/boot/
#        chmod +x ~/.termux/boot/fit-ingo.sh
#   3. Edit REPO_DIR below to your checkout path if it isn't the default.
#
# On reboot, Termux:Boot runs this and Fit-ingo comes up on http://localhost:8777.
set -e

REPO_DIR="$HOME/fit-ingo-app"   # <-- adjust to where you cloned the repo

termux-wake-lock || true
exec bash "$REPO_DIR/termux/start.sh"
