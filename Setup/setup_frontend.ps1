# =============================================================================
# setup_frontend.ps1
# Speech-to-Code Framework — Frontend Setup (Windows 11)
# =============================================================================
# One-command install (run PowerShell as Administrator):
#   irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/dev/Setup/setup_frontend.ps1 | iex
#
# MANUAL PREREQUISITES:
#   1. Install LM Studio from https://lmstudio.ai
#   2. Download model: meta-llama-3.1-8b-instruct
#   3. Start the local server in LM Studio (port 1234)
# =============================================================================

$MIN_PYTHON_MAJOR = 3
$MIN_PYTHON_MINOR = 10
$INSTALL_DIR      = "C:\Program Files\Speech-to-Cobot"
$ZIP_URL          = "https://github.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/archive/refs/heads/dev.zip"
$ZIP_PATH         = "$env:TEMP\speech-to-cobot.zip"
$EXTRACT_PATH     = "$env:TEMP\speech-to-cobot-extract"
$VENV_DIR         = "$INSTALL_DIR\venv_frontend"
$REQUIREMENTS     = "$INSTALL_DIR\Setup\requirements_frontend.txt"
$LM_STUDIO_URL    = "http://localhost:1234/v1/models"
$WHISPER_CACHE    = "$env:USERPROFILE\.cache\whisper"

function Write-Step { param([string]$msg) Write-Host "`n[SETUP] $msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$msg) Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-Warn { param([string]$msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Fail {
    param([string]$msg)
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
    throw $msg
}

# --- Admin check --------------------------------------------------------------

Write-Step "Checking Administrator privileges"
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Fail "Must be run as Administrator. Right-click PowerShell and select 'Run as administrator'."
}
Write-OK "Running as Administrator"

# --- Execution policy ---------------------------------------------------------

Write-Step "Checking PowerShell execution policy"
$policy = Get-ExecutionPolicy -Scope CurrentUser
if ($policy -eq "Restricted" -or $policy -eq "AllSigned") {
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
    Write-OK "Execution policy set to RemoteSigned"
} else {
    Write-OK "Execution policy OK ($policy)"
}

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
    Write-Fail "Python $version found but $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+ required. Install from https://python.org"
}
Write-OK "Python $version"

# --- ffmpeg -------------------------------------------------------------------
# Check PATH first — instant. Only call winget if ffmpeg is genuinely missing.
# winget output is shown directly so the user sees exactly what is happening.

Write-Step "Checking ffmpeg (required by Whisper)"
$ffmpegPath = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpegPath) {
    Write-OK "ffmpeg found at $($ffmpegPath.Source)"
} else {
    Write-Host "  ffmpeg not found on PATH — installing via winget..." -ForegroundColor Gray
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "ffmpeg install failed. Install manually from https://ffmpeg.org, add to PATH, then re-run."
    }
    # Refresh PATH so ffmpeg is immediately available in this session
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
    Write-OK "ffmpeg installed"
}

# --- Download repository ------------------------------------------------------
# Uses curl.exe (built into Windows 11) for native progress output.
# GitHub ZIPs extract to a single subfolder named <repo>-<branch> — we rename it.

Write-Step "Downloading repository to $INSTALL_DIR"
if (Test-Path $INSTALL_DIR) {
    Write-Warn "$INSTALL_DIR already exists — skipping download. Delete it to force a fresh install."
} else {
    Write-Host "  Downloading from GitHub..." -ForegroundColor Gray
    curl.exe -L --progress-bar $ZIP_URL -o $ZIP_PATH
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $ZIP_PATH)) {
        Write-Fail "Download failed. Check your internet connection and re-run."
    }

    Write-Host "  Extracting..." -ForegroundColor Gray
    if (Test-Path $EXTRACT_PATH) { Remove-Item -Recurse -Force $EXTRACT_PATH }
    Expand-Archive -Path $ZIP_PATH -DestinationPath $EXTRACT_PATH -Force

    $extractedFolder = Get-ChildItem -Path $EXTRACT_PATH -Directory | Select-Object -First 1
    if (-not $extractedFolder) {
        Write-Fail "ZIP extraction produced no folder. The download may be corrupt — re-run."
    }
    Move-Item -Path $extractedFolder.FullName -Destination $INSTALL_DIR

    Remove-Item -Force $ZIP_PATH
    Remove-Item -Recurse -Force $EXTRACT_PATH

    Write-OK "Repository ready at $INSTALL_DIR"
}

# --- Virtual environment ------------------------------------------------------

Write-Step "Creating virtual environment"
if (Test-Path $VENV_DIR) {
    Write-Warn "Virtual environment already exists — skipping. Delete $VENV_DIR to force a fresh install."
} else {
    python -m venv $VENV_DIR
    Write-OK "Virtual environment created"
}

# --- Python dependencies ------------------------------------------------------
# pip output is shown directly — each package install is visible.

Write-Step "Installing Python dependencies"
if (-not (Test-Path $REQUIREMENTS)) {
    Write-Fail "$REQUIREMENTS not found. Repository structure may be unexpected — check $INSTALL_DIR."
}

$pip = "$VENV_DIR\Scripts\pip.exe"
Write-Host "  Upgrading pip..." -ForegroundColor Gray
& $pip install --upgrade pip
Write-Host ""
Write-Host "  Installing packages from requirements_frontend.txt..." -ForegroundColor Gray
& $pip install -r $REQUIREMENTS
if ($LASTEXITCODE -ne 0) {
    Write-Fail "pip install failed — see output above."
}
Write-OK "Python dependencies installed"

# --- Whisper model ------------------------------------------------------------
# Downloads ~140 MB to %USERPROFILE%\.cache\whisper — outside the install folder.
# This is Whisper's standard cache location. cleanup_frontend.ps1 removes it.

Write-Step "Pre-downloading Whisper base model (~140 MB)"
Write-Host "  Model will be saved to $WHISPER_CACHE" -ForegroundColor Gray
Write-Warn "This location is outside the install folder. Run cleanup_frontend.ps1 to remove it."
$python = "$VENV_DIR\Scripts\python.exe"
& $python -c "import whisper; whisper.load_model('base')"
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Whisper model pre-download failed — it will download on first application launch instead."
} else {
    Write-OK "Whisper base model ready"
}

# --- LM Studio check ----------------------------------------------------------
# Does not install LM Studio — that must be done manually.
# Only checks whether the API server is already running.

Write-Step "Checking LM Studio server ($LM_STUDIO_URL)"
try {
    Invoke-WebRequest -Uri $LM_STUDIO_URL -UseBasicParsing -TimeoutSec 5 | Out-Null
    Write-OK "LM Studio server reachable"
} catch {
    Write-Warn "LM Studio server not reachable — this is expected if you have not started it yet."
    Write-Warn "Before running the app: open LM Studio, load meta-llama-3.1-8b-instruct, and start the server."
}

# --- Done ---------------------------------------------------------------------

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host " Setup complete. Installed to:"                        -ForegroundColor Green
Write-Host "   $INSTALL_DIR"                                       -ForegroundColor White
Write-Host ""                                                       -ForegroundColor Green
Write-Host " To launch the application:"                           -ForegroundColor Green
Write-Host "   cd '$INSTALL_DIR'"                                  -ForegroundColor White
Write-Host "   '$VENV_DIR\Scripts\python.exe' -m Frontend.main"   -ForegroundColor White
Write-Host "=====================================================" -ForegroundColor Green