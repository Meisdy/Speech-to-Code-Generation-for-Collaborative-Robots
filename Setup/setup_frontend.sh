#!/usr/bin/env bash
# =============================================================================
# setup_frontend.sh
# Speech-to-Code Framework — Frontend Setup (Linux)
# =============================================================================
# Run once from the repository root before first use.
# One-command install:
#   curl -sSL https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/setup_frontend.sh | bash
#
# MANUAL PREREQUISITES:
#   1. Install LM Studio from https://lmstudio.ai
#   2. Download model: meta-llama-3.1-8b-instruct
#   3. Start the local server in LM Studio (port 1234)
# =============================================================================

set -euo pipefail

MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10
VENV_DIR="venv_frontend"
REQUIREMENTS="Frontend/requirements_frontend.txt"
LM_STUDIO_URL="http://localhost:1234/v1/models"
WHISPER_CACHE="$HOME/.cache/whisper"

step() { echo -e "\n\033[0;36m[SETUP] $1\033[0m"; }
ok()   { echo -e "  \033[0;32m[OK]   $1\033[0m"; }
warn() { echo -e "  \033[0;33m[WARN] $1\033[0m"; }
fail() { echo -e "  \033[0;31m[FAIL] $1\033[0m"; exit 1; }

# --- Repo root check ----------------------------------------------------------

step "Checking working directory"
if [ ! -f "$REQUIREMENTS" ]; then
    fail "$REQUIREMENTS not found. Run this script from the repository root."
fi
ok "Repository root confirmed"

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
    fail "Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+ not found. Install via: sudo apt install python3.11 python3.11-venv"
fi

# --- System dependencies ------------------------------------------------------

step "Installing system dependencies (ffmpeg, PortAudio, Python venv)"
if ! command -v apt &>/dev/null; then
    fail "apt not found. This script targets Debian/Ubuntu. Install ffmpeg and portaudio19-dev manually for your distribution."
fi

sudo apt-get update -qq
sudo apt-get install -y ffmpeg portaudio19-dev python3-dev python3-venv
ok "System dependencies installed"

# --- Virtual environment ------------------------------------------------------

step "Creating virtual environment ($VENV_DIR)"
if [ -d "$VENV_DIR" ]; then
    warn "$VENV_DIR already exists — skipping. Delete it to force a fresh install."
else
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    ok "Virtual environment created"
fi

# --- Dependencies -------------------------------------------------------------

step "Installing Python dependencies"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$REQUIREMENTS"
ok "Dependencies installed"

# --- Whisper model ------------------------------------------------------------
# Pre-downloads the model so the first launch does not stall.
# Saved to ~/.cache/whisper — outside the venv.
# Run cleanup_frontend.sh to remove it.

step "Pre-downloading Whisper base model (~140 MB)"
warn "Saved to $WHISPER_CACHE — not inside venv. cleanup_frontend.sh removes this."
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
echo " Launch with:"
echo "   ./$VENV_DIR/bin/python -m Frontend.main"
echo "============================================="
