# =============================================================================
# setup_backend.ps1
# Speech-to-Code Framework — Backend Setup (Windows 11)
# =============================================================================
# One-command install (run PowerShell as Administrator):
#   irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_backend.ps1 | iex
#
# Installs the backend server supporting Mock and UR adapters.
# Franka requires a pre-configured ROS Noetic workstation — see documentation.
#
# This script installs uv, which manages Python 3.12 and all dependencies
# automatically. No manual Python installation required.
# =============================================================================

$INSTALL_DIR   = "C:\Program Files\Speech-to-Cobot-Backend"
$RELEASE_TAG   = "v1.1.2"
$ZIP_URL       = "https://github.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/releases/download/$RELEASE_TAG/stcgcr-backend.zip"
$ZIP_PATH      = "C:\Windows\Temp\stcgcr-backend.zip"
$EXTRACT_PATH  = "C:\Windows\Temp\stcgcr-backend-extract"

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

# --- uv -----------------------------------------------------------------------
# uv manages Python version and dependencies — no manual Python install needed.

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

    # Grant modify access to all users — allows editing config files without Administrator
    icacls "$INSTALL_DIR" /grant "Users:(OI)(CI)M" /T | Out-Null

    # Grant write access to the logs directory — the backend writes log files at runtime
    $logsDir = "$INSTALL_DIR\Backend\logs"
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    icacls "$logsDir" /grant "Users:(OI)(CI)F" /T | Out-Null

    $elapsed = [math]::Round(((Get-Date) - $stepStart).TotalSeconds, 1)
    Write-OK "Repository ready at $INSTALL_DIR ($elapsed s)"
}

# --- Install Python and dependencies via uv -----------------------------------

Write-Step "Installing Python 3.12 and backend dependencies via uv"
$stepStart = Get-Date
Set-Location $INSTALL_DIR
uv sync --only-group backend
if ($LASTEXITCODE -ne 0) {
    Write-Fail "uv sync failed — see output above."
}
$elapsed = [math]::Round(((Get-Date) - $stepStart).TotalSeconds, 1)
Write-OK "Python 3.12 and all dependencies installed ($elapsed s)"

# --- Launcher -----------------------------------------------------------------
# Creates launch_backend.bat in the install directory.
# Terminal window stays open so backend logs are visible while the server runs.

Write-Step "Creating launcher and Desktop shortcut"
$batPath      = "$INSTALL_DIR\launch_backend.bat"
$shortcutPath = "$env:USERPROFILE\Desktop\Speech-to-Cobot Backend.lnk"

@"
@echo off
cd /d "C:\Program Files\Speech-to-Cobot-Backend"
echo Starting Speech-to-Cobot Backend Server...
echo Press Ctrl+C to stop.
echo.
uv run python -m Backend.main
pause
"@ | Set-Content -Path $batPath -Encoding ASCII
Write-OK "Launcher created at $batPath"

# Shortcut points directly to the bat file — terminal window is intentional for the backend
$shell     = New-Object -ComObject WScript.Shell
$shortcut  = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath       = $batPath
$shortcut.WorkingDirectory = $INSTALL_DIR
$shortcut.Description      = "Start Speech-to-Cobot Backend Server"
$shortcut.Save()
Write-OK "Shortcut created at $shortcutPath"

# Set shortcut to always run as Administrator (sets flag byte in .lnk file)
$bytes = [System.IO.File]::ReadAllBytes($shortcutPath)
$bytes[0x15] = $bytes[0x15] -bor 0x20
[System.IO.File]::WriteAllBytes($shortcutPath, $bytes)
Write-OK "Shortcut set to run as Administrator"

# --- Done ---------------------------------------------------------------------

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host " Backend setup complete. Installed to:"               -ForegroundColor Green
Write-Host "   $INSTALL_DIR"                                       -ForegroundColor White
Write-Host ""
Write-Host " To start the backend server:"                         -ForegroundColor Green
Write-Host "   Double-click launch_backend.bat in $INSTALL_DIR"   -ForegroundColor White
Write-Host "   or: cd '$INSTALL_DIR'"                             -ForegroundColor White
Write-Host "   and: uv run python -m Backend.main"                -ForegroundColor White
Write-Host "=====================================================" -ForegroundColor Green