# =============================================================================
# setup_frontend.ps1
# Speech-to-Code Framework — Frontend Setup (Windows 11)
# =============================================================================
# Run once from the repository root before first use.
# One-command install:
#   irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/setup_frontend.ps1 | iex
#
# MANUAL PREREQUISITES:
#   1. Install LM Studio from https://lmstudio.ai
#   2. Download model: meta-llama-3.1-8b-instruct
#   3. Start the local server in LM Studio (port 1234)
# =============================================================================

$ErrorActionPreference = "Stop"

$MIN_PYTHON_MAJOR  = 3
$MIN_PYTHON_MINOR  = 10
$VENV_DIR          = "venv_frontend"
$REQUIREMENTS      = "Frontend\requirements_frontend.txt"
$LM_STUDIO_URL     = "http://localhost:1234/v1/models"
$WHISPER_CACHE     = "$env:USERPROFILE\.cache\whisper"

function Write-Step { param([string]$msg) Write-Host "`n[SETUP] $msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$msg) Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-Warn { param([string]$msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$msg) Write-Host "  [FAIL] $msg" -ForegroundColor Red; exit 1 }

# --- Execution policy ---------------------------------------------------------

Write-Step "Checking PowerShell execution policy"
$policy = Get-ExecutionPolicy -Scope CurrentUser
if ($policy -eq "Restricted" -or $policy -eq "AllSigned") {
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
    Write-OK "Execution policy set to RemoteSigned"
} else {
    Write-OK "Execution policy OK ($policy)"
}

# --- Repo root check ----------------------------------------------------------

Write-Step "Checking working directory"
if (-not (Test-Path $REQUIREMENTS)) {
    Write-Fail "$REQUIREMENTS not found. Run this script from the repository root."
}
Write-OK "Repository root confirmed"

# --- winget -------------------------------------------------------------------

Write-Step "Checking winget"
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Fail "winget not found. Install App Installer from the Microsoft Store and re-run."
}
Write-OK "winget available"

# --- Python -------------------------------------------------------------------

Write-Step "Checking Python (minimum $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR)"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Fail "Python not found. Install Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+ from https://python.org and add to PATH."
}

$version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
$parts   = $version.Split(".")
$major   = [int]$parts[0]
$minor   = [int]$parts[1]

if ($major -lt $MIN_PYTHON_MAJOR -or ($major -eq $MIN_PYTHON_MAJOR -and $minor -lt $MIN_PYTHON_MINOR)) {
    Write-Fail "Python $version found but $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+ required."
}
Write-OK "Python $version"

# --- ffmpeg -------------------------------------------------------------------

Write-Step "Installing ffmpeg (required by Whisper)"
$ffmpegCheck = winget list --id Gyan.FFmpeg 2>$null | Select-String "Gyan.FFmpeg"
if ($ffmpegCheck) {
    Write-OK "ffmpeg already installed"
} else {
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "ffmpeg install failed. Install manually from https://ffmpeg.org, add to PATH, then re-run."
    }
    Write-OK "ffmpeg installed"
}

# --- Virtual environment ------------------------------------------------------

Write-Step "Creating virtual environment ($VENV_DIR)"
if (Test-Path $VENV_DIR) {
    Write-Warn "$VENV_DIR already exists — skipping. Delete it to force a fresh install."
} else {
    python -m venv $VENV_DIR
    Write-OK "Virtual environment created"
}

# --- Dependencies -------------------------------------------------------------

Write-Step "Installing Python dependencies"
$pip = ".\$VENV_DIR\Scripts\pip.exe"
& $pip install --upgrade pip --quiet
& $pip install -r $REQUIREMENTS
if ($LASTEXITCODE -ne 0) {
    Write-Fail "pip install failed. Check output above for details."
}
Write-OK "Dependencies installed"

# --- Whisper model ------------------------------------------------------------
# Pre-downloads the model so the first launch does not stall.
# Saved to %USERPROFILE%\.cache\whisper — outside the venv.
# Run cleanup_frontend.ps1 to remove it.

Write-Step "Pre-downloading Whisper base model (~140 MB)"
Write-Warn "Saved to $WHISPER_CACHE — not inside venv. cleanup_frontend.ps1 removes this."
$python = ".\$VENV_DIR\Scripts\python.exe"
& $python -c "import whisper; whisper.load_model('base')"
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Model pre-download failed. It will download on first launch instead."
} else {
    Write-OK "Whisper base model ready"
}

# --- LM Studio check ----------------------------------------------------------

Write-Step "Checking LM Studio at $LM_STUDIO_URL"
try {
    Invoke-WebRequest -Uri $LM_STUDIO_URL -UseBasicParsing -TimeoutSec 5 | Out-Null
    Write-OK "LM Studio reachable"
} catch {
    Write-Warn "LM Studio not reachable — expected if not started yet."
    Write-Warn "Start LM Studio, load meta-llama-3.1-8b-instruct, and enable the server before running the app."
}

# --- Done ---------------------------------------------------------------------

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host " Frontend setup complete."                    -ForegroundColor Green
Write-Host " Launch with:"                               -ForegroundColor Green
Write-Host "   .\$VENV_DIR\Scripts\python.exe -m Frontend.main" -ForegroundColor White
Write-Host "=============================================" -ForegroundColor Green
