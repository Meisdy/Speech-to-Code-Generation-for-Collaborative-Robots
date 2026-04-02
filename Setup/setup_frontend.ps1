# =============================================================================
# setup_frontend.ps1
# Speech-to-Code Framework — Frontend Setup (Windows 11)
# =============================================================================
# One-command install (run PowerShell as Administrator):
#   irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_frontend.ps1 | iex
#
# MANUAL PREREQUISITES:
#   1. Install LM Studio from https://lmstudio.ai
#   2. Download model: meta-llama-3.1-8b-instruct
#   3. Start the local server in LM Studio (port 1234)
#
# This script installs uv, which manages Python 3.12 and all dependencies
# automatically. No manual Python installation required.
# =============================================================================

$INSTALL_DIR   = "C:\Program Files\Speech-to-Cobot"
$RELEASE_TAG   = "v1.1.0"
$ZIP_URL       = "https://github.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/releases/download/$RELEASE_TAG/stcgcr-frontend.zip"
$ZIP_PATH      = "C:\Windows\Temp\stcgcr-frontend.zip"
$EXTRACT_PATH  = "C:\Windows\Temp\stcgcr-frontend-extract"
$LM_STUDIO_URL = "http://localhost:1234/v1/models"
$WHISPER_CACHE = "$env:USERPROFILE\.cache\whisper"

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

# --- ffmpeg -------------------------------------------------------------------
# Check PATH first — instant. Only call winget if ffmpeg is genuinely missing.

Write-Step "Checking ffmpeg (required by Whisper)"
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-OK "ffmpeg found at $((Get-Command ffmpeg).Source)"
} else {
    Write-Host "  ffmpeg not on PATH — installing via winget..." -ForegroundColor Gray
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "ffmpeg install failed. Install manually from https://ffmpeg.org, add to PATH, then re-run."
    }
    # Refresh PATH so ffmpeg is available in this session without a restart
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
    Write-OK "ffmpeg installed"
}

# --- uv -----------------------------------------------------------------------
# uv manages Python version and dependencies — no manual Python install needed.
# It installs Python 3.12 if missing and creates an isolated .venv in the
# project directory.

Write-Step "Checking uv"
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-OK "uv found at $((Get-Command uv).Source)"
} else {
    Write-Host "  uv not found — installing via winget..." -ForegroundColor Gray
    winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "uv install failed."
    }
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
    Write-OK "uv installed"
}

# --- Download repository ------------------------------------------------------
# Uses curl.exe (built into Windows 11) for native progress output.
# Release ZIPs are flat — contents are moved directly into INSTALL_DIR.
# try/finally guarantees temp files are cleaned up even if extraction fails.

Write-Step "Downloading repository to $INSTALL_DIR"
if (Test-Path $INSTALL_DIR) {
    Write-Warn "$INSTALL_DIR already exists — skipping download. Delete it to force a fresh install."
} else {
    $stepStart = Get-Date
    try {
        Write-Host "  Downloading from GitHub..." -ForegroundColor Gray
        curl.exe -L --progress-bar $ZIP_URL -o $ZIP_PATH
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $ZIP_PATH)) {
            Write-Fail "Download failed. Check your internet connection and re-run."
        }

        Write-Host "  Extracting..." -ForegroundColor Gray
        if (Test-Path $EXTRACT_PATH) { Remove-Item -Recurse -Force $EXTRACT_PATH }
        Expand-Archive -Path $ZIP_PATH -DestinationPath $EXTRACT_PATH -Force

        # Release ZIPs are flat (no wrapping subfolder) — move contents directly
        New-Item -ItemType Directory -Path $INSTALL_DIR -Force | Out-Null
        Get-ChildItem -Path $EXTRACT_PATH | Move-Item -Destination $INSTALL_DIR
    } finally {
        if (Test-Path $ZIP_PATH)     { Remove-Item -Force $ZIP_PATH }
        if (Test-Path $EXTRACT_PATH) { Remove-Item -Recurse -Force $EXTRACT_PATH }
    }

    # Grant read and execute to all users so the app runs without Administrator
    icacls "$INSTALL_DIR" /grant "Users:(OI)(CI)RX" /T | Out-Null

    # Grant write access to the logs directory — the app writes log files at runtime
    $logsDir = "$INSTALL_DIR\Frontend\logs"
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    icacls "$logsDir" /grant "Users:(OI)(CI)F" /T | Out-Null

    $elapsed = [math]::Round(((Get-Date) - $stepStart).TotalSeconds, 1)
    Write-OK "Repository ready at $INSTALL_DIR ($elapsed s)"
}

# --- Install Python and dependencies via uv -----------------------------------
# uv reads pyproject.toml at the repo root, installs Python 3.12 if needed,
# creates .venv inside the project directory, and installs all dependencies.
# Nothing outside the project directory or uv's own cache is modified.

Write-Step "Installing Python 3.12 and frontend dependencies via uv"
$stepStart = Get-Date
Set-Location $INSTALL_DIR
uv sync --only-group frontend
if ($LASTEXITCODE -ne 0) {
    Write-Fail "uv sync failed — see output above."
}
$elapsed = [math]::Round(((Get-Date) - $stepStart).TotalSeconds, 1)
Write-OK "Python 3.12 and all dependencies installed ($elapsed s)"

# --- Desktop shortcut ---------------------------------------------------------
# Uses wscript.exe + a VBS launcher — the only reliable way on Windows to launch
# a process from a shortcut with absolutely no console or PowerShell window.
# uv full path is resolved at install time — regular users may not have it on PATH.

Write-Step "Creating Desktop shortcut"
$vbsPath      = "$INSTALL_DIR\launch_frontend.vbs"
$shortcutPath = "$env:USERPROFILE\Desktop\Speech-to-Cobot.lnk"

$uvFullPath = (Get-Command uv).Source
if (-not $uvFullPath) {
    Write-Fail "Cannot resolve uv path — re-run setup to fix."
}

@"
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "$INSTALL_DIR"
shell.Run "$uvFullPath run pythonw -m Frontend.main", 0, False
"@ | Set-Content -Path $vbsPath -Encoding ASCII

$shell     = New-Object -ComObject WScript.Shell
$shortcut  = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath       = "wscript.exe"
$shortcut.Arguments        = "`"$vbsPath`""
$shortcut.WorkingDirectory = $INSTALL_DIR
$shortcut.Description      = "Launch Speech-to-Cobot Frontend"
$shortcut.Save()
Write-OK "Shortcut created at $shortcutPath"

# --- Whisper model ------------------------------------------------------------
# Pre-downloads the model so the first launch does not stall.
# Saved to %USERPROFILE%\.cache\whisper — outside the project directory.
# uninstall_frontend.ps1 removes this.

Write-Step "Pre-downloading Whisper small model (~466 MB)"
Write-Host "  Model will be saved to $WHISPER_CACHE" -ForegroundColor Gray
Write-Warn "This is outside the project directory. Run uninstall_frontend.ps1 to remove it."
$stepStart = Get-Date
uv run python -c "import whisper; whisper.load_model('small')"
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Whisper model pre-download failed — it will download on first application launch instead."
} else {
    $elapsed = [math]::Round(((Get-Date) - $stepStart).TotalSeconds, 1)
    Write-OK "Whisper small model ready ($elapsed s)"
}

# --- LM Studio check ----------------------------------------------------------
# Does not install LM Studio — that must be done manually (see prerequisites).
# Only checks whether the API server is already running.

Write-Step "Checking LM Studio server ($LM_STUDIO_URL)"
try {
    Invoke-WebRequest -Uri $LM_STUDIO_URL -UseBasicParsing -TimeoutSec 5 | Out-Null
    Write-OK "LM Studio server reachable"
} catch {
    Write-Warn "LM Studio server not reachable — expected if not started yet."
    Write-Warn "Before running: open LM Studio, load meta-llama-3.1-8b-instruct, start the server."
}

# --- Done ---------------------------------------------------------------------

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host " Setup complete. Installed to:"                        -ForegroundColor Green
Write-Host "   $INSTALL_DIR"                                       -ForegroundColor White
Write-Host ""
Write-Host " To launch the application:"                           -ForegroundColor Green
Write-Host "   Double-click Speech-to-Cobot on the Desktop"       -ForegroundColor White
Write-Host "   or: cd '$INSTALL_DIR'"                             -ForegroundColor White
Write-Host "   and: uv run pythonw -m Frontend.main"              -ForegroundColor White
Write-Host "=====================================================" -ForegroundColor Green