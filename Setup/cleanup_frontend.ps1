# =============================================================================
# cleanup_frontend.ps1
# Speech-to-Code Framework — Frontend Cleanup (Windows 11)
# =============================================================================
# Removes everything installed by setup_frontend.ps1.
# Run PowerShell as Administrator.
#
# Removes:
#   - C:\Program Files\Speech-to-Cobot\ (repo + venv)
#   - %USERPROFILE%\.cache\whisper (~140 MB Whisper model)
#
# Does NOT remove (uninstall manually if needed):
#   - ffmpeg:    winget uninstall --id Gyan.FFmpeg
#   - LM Studio: Windows Settings → Apps → LM Studio → Uninstall
#   - Python
# =============================================================================

$ErrorActionPreference = "Stop"

$INSTALL_DIR   = "C:\Program Files\Speech-to-Cobot"
$WHISPER_CACHE = "$env:USERPROFILE\.cache\whisper"

function Write-Step { param([string]$msg) Write-Host "`n[CLEANUP] $msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$msg) Write-Host "  [OK]   $msg"   -ForegroundColor Green }
function Write-Warn { param([string]$msg) Write-Host "  [WARN] $msg"   -ForegroundColor Yellow }
function Write-Fail { param([string]$msg) Write-Host "  [FAIL] $msg"   -ForegroundColor Red; exit 1 }

# --- Admin check --------------------------------------------------------------

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Fail "This script must be run as Administrator."
}

# --- Remove install directory -------------------------------------------------

Write-Step "Removing install directory ($INSTALL_DIR)"
if (Test-Path $INSTALL_DIR) {
    Remove-Item -Recurse -Force $INSTALL_DIR
    Write-OK "Removed $INSTALL_DIR"
} else {
    Write-Warn "$INSTALL_DIR not found — already removed or never installed"
}

# --- Remove Whisper cache -----------------------------------------------------

Write-Step "Removing Whisper model cache ($WHISPER_CACHE)"
if (Test-Path $WHISPER_CACHE) {
    Remove-Item -Recurse -Force $WHISPER_CACHE
    Write-OK "Removed $WHISPER_CACHE"
} else {
    Write-Warn "$WHISPER_CACHE not found — already removed or never downloaded"
}

Write-Host ""
Write-Host "============================================="  -ForegroundColor Green
Write-Host " Cleanup complete."                            -ForegroundColor Green
Write-Host " To also remove ffmpeg:"                      -ForegroundColor White
Write-Host "   winget uninstall --id Gyan.FFmpeg"         -ForegroundColor White
Write-Host " To also remove LM Studio:"                   -ForegroundColor White
Write-Host "   Windows Settings → Apps → LM Studio"       -ForegroundColor White
Write-Host "============================================="  -ForegroundColor Green