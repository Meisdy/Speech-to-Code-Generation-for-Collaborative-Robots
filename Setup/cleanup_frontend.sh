#!/usr/bin/env bash
# =============================================================================
# cleanup_frontend.sh
# Speech-to-Code Framework — Frontend Cleanup (Linux)
# =============================================================================
# Removes everything installed by setup_frontend.sh.
# Run as root: sudo bash cleanup_frontend.sh
#
# Removes:
#   - /opt/speech-to-cobot/ (repo + venv)
#   - ~/.cache/whisper (~140 MB Whisper model)
#
# Does NOT remove (uninstall manually if needed):
#   - ffmpeg + PortAudio: sudo apt remove ffmpeg portaudio19-dev
#   - LM Studio: run its own uninstaller
#   - Python
# =============================================================================

set -euo pipefail

INSTALL_DIR="/opt/speech-to-cobot"
WHISPER_CACHE="$HOME/.cache/whisper"

step() { echo -e "\n\033[0;36m[CLEANUP] $1\033[0m"; }
ok()   { echo -e "  \033[0;32m[OK]   $1\033[0m"; }
warn() { echo -e "  \033[0;33m[WARN] $1\033[0m"; }
fail() { echo -e "  \033[0;31m[FAIL] $1\033[0m"; exit 1; }

# --- Root check ---------------------------------------------------------------

if [ "$EUID" -ne 0 ]; then
    fail "This script must be run as root. Use: sudo bash cleanup_frontend.sh"
fi

# --- Remove install directory -------------------------------------------------

step "Removing install directory ($INSTALL_DIR)"
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    ok "Removed $INSTALL_DIR"
else
    warn "$INSTALL_DIR not found — already removed or never installed"
fi

# --- Remove Whisper cache -----------------------------------------------------

step "Removing Whisper model cache ($WHISPER_CACHE)"
if [ -d "$WHISPER_CACHE" ]; then
    rm -rf "$WHISPER_CACHE"
    ok "Removed $WHISPER_CACHE"
else
    warn "$WHISPER_CACHE not found — already removed or never downloaded"
fi

echo ""
echo "============================================="
echo " Cleanup complete."
echo " To also remove system packages:"
echo "   sudo apt remove ffmpeg portaudio19-dev"
echo " To also remove LM Studio:"
echo "   Run the LM Studio uninstaller"
echo "============================================="