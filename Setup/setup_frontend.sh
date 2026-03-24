#!/usr/bin/env bash
# =============================================================================
# setup_frontend.sh
# Speech-to-Code Framework — Frontend Setup (Linux)
# =============================================================================
# One-command install (run as root):
#   curl -sSL https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/dev/Setup/setup_frontend.sh | sudo bash
#
# MANUAL PREREQUISITES:
#   1. Install LM Studio from https://lmstudio.ai
#   2. Download model: meta-llama-3.1-8b-instruct
#   3. Start the local server in LM Studio (port 1234)
# =============================================================================

set -euo pipefail

MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10
INSTALL_DIR="/opt/speech-to-cobot"
ZIP_URL="https://github.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/archive/refs/heads/dev.zip"
ZIP_PATH="/tmp/speech-to-cobot.zip"
EXTRACT_PATH="/tmp/speech-to-cobot-extract"
VENV_DIR="$INSTALL_DIR/venv_frontend"
REQUIREMENTS="$INSTALL_DIR/Setup/requirements_frontend.txt"
LM_STUDIO_URL="http://localhost:1234/v1/models"
WHISPER_CACHE="$HOME/.cache/whisper"

step() { echo -e "\n\033[0;36m[SETUP] $1\033[0m"; }
ok()   { echo -e "  \033[0;32m[OK]   $1\033[0m"; }
warn() { echo -e "  \033[0;33m[WARN] $1\033[0m"; }
fail() { echo -e "  \033[0;31m[FAIL] $1\033[0m"; exit 1; }

# --- Root check ---------------------------------------------------------------

step "Checking root privileges"
if [ "$EUID" -ne 0 ]; then
    fail "This script must be run as root. Use: sudo bash setup_frontend.sh"
fi
ok "Running as root"

# --- Python -------------------------------------------------------------------

step "Checking Python (minimum $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR)"

PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VERSION=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        if [ "$MAJOR" -gt "$MIN_PYTHON_MAJOR" ] || \
           ([ "$MAJOR" -eq "$MIN_PYTHON_MAJOR" ] && [ "$MINOR" -ge "$MIN_PYTHON_MINOR" ]); then
            PYTHON_CMD="$cmd"
            ok "Python $VERSION ($cmd)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    fail "Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+ not found. Install via: apt install python3.11 python3.11-venv"
fi

# --- System dependencies ------------------------------------------------------

step "Installing system dependencies (ffmpeg, PortAudio, unzip, Python venv)"
if ! command -v apt &>/dev/null; then
    fail "apt not found. This script targets Debian/Ubuntu. Install ffmpeg and portaudio19-dev manually."
fi

apt-get update -qq
apt-get install -y ffmpeg portaudio19-dev python3-dev python3-venv unzip curl
ok "System dependencies installed"

# --- Download repository ------------------------------------------------------
# Downloads as ZIP — no git required on the target machine.
# GitHub extracts to a folder named <repo>-<branch>, which we rename to INSTALL_DIR.

step "Downloading repository to $INSTALL_DIR"
if [ -d "$INSTALL_DIR" ]; then
    warn "$INSTALL_DIR already exists — skipping download. Delete it to force a fresh install."
else
    echo "  Downloading..."
    curl -sSL "$ZIP_URL" -o "$ZIP_PATH"

    rm -rf "$EXTRACT_PATH"
    mkdir -p "$EXTRACT_PATH"
    unzip -q "$ZIP_PATH" -d "$EXTRACT_PATH"

    # GitHub ZIP extracts to a single subfolder — find and move it
    EXTRACTED_FOLDER=$(find "$EXTRACT_PATH" -mindepth 1 -maxdepth 1 -type d | head -n 1)
    if [ -z "$EXTRACTED_FOLDER" ]; then
        fail "ZIP extraction produced no folder. The download may be corrupt — re-run."
    fi
    mv "$EXTRACTED_FOLDER" "$INSTALL_DIR"

    rm -f "$ZIP_PATH"
    rm -rf "$EXTRACT_PATH"

    ok "Repository ready at $INSTALL_DIR"
fi

# --- Virtual environment ------------------------------------------------------

step "Creating virtual environment"
if [ -d "$VENV_DIR" ]; then
    warn "Virtual environment already exists — skipping. Delete $VENV_DIR to force a fresh install."
else
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    ok "Virtual environment created at $VENV_DIR"
fi

# --- Dependencies -------------------------------------------------------------

step "Installing Python dependencies"
if [ ! -f "$REQUIREMENTS" ]; then
    fail "$REQUIREMENTS not found. The repository structure may be unexpected — check $INSTALL_DIR."
fi
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$REQUIREMENTS"
ok "Dependencies installed"

# --- Whisper model ------------------------------------------------------------
# Pre-downloads the model so the first launch does not stall.
# Saved to ~/.cache/whisper — outside the install folder.
# cleanup_frontend.sh removes this.

step "Pre-downloading Whisper base model (~140 MB)"
warn "Saved to $WHISPER_CACHE — not inside install folder. cleanup_frontend.sh removes this."
if "$VENV_DIR/bin/python" -c "import whisper; whisper.load_model('base')"; then
    ok "Whisper base model ready"
else
    warn "Model pre-download failed. It will download on first launch instead."
fi

# --- LM Studio check ----------------------------------------------------------

step "Checking LM Studio at $LM_STUDIO_URL"
if curl -sf --max-time 5 "$LM_STUDIO_URL" > /dev/null 2>&1; then
    ok "LM Studio reachable"
else
    warn "LM Studio not reachable — expected if not started yet."
    warn "Start LM Studio, load meta-llama-3.1-8b-instruct, and enable the server before running the app."
fi

# --- Done ---------------------------------------------------------------------

echo ""
echo "============================================="
echo " Frontend setup complete."
echo " Installed to: $INSTALL_DIR"
echo " Launch with:"
echo "   cd $INSTALL_DIR"
echo "   $VENV_DIR/bin/python -m Frontend.main"
echo "============================================="