#!/usr/bin/env bash
# =============================================================================
# cleanup_frontend.sh
# Speech-to-Code Framework — Frontend Cleanup (Linux)
# =============================================================================
# Removes everything installed by setup_frontend.sh.
# Run from the repository root.
#
# Removes:
#   - venv_frontend
#   - ~/.cache/whisper (~140 MB Whisper model)
#
# Does NOT remove (uninstall manually if needed):
#   - ffmpeg:     sudo apt remove ffmpeg
#   - PortAudio:  sudo apt remove portaudio19-dev
#   - LM Studio:  run its own uninstaller
#   - Python
# =============================================================================

set -euo pipefail

VENV_DIR      ="venv_frontend"
WHISPER_CACHE="$HOME/.cache/whisper"

step() { echo -e "\n\033[0;36m[CLEANUP] $1\033[0m"; }
ok()   { echo -e "  \033[0;32m[OK]   $1\033[0m"; }
warn() { echo -e "  \033[0;33m[WARN] $1\033[0m"; }

step "Removing virtual environment ($VENV_DIR)"
if [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
    ok "Removed $VENV_DIR"
else
    warn "$VENV_DIR not found — already removed or never created"
fi

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
