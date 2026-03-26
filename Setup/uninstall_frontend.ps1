# =============================================================================
# uninstall_frontend.ps1
# Speech-to-Code Framework — Frontend Uninstaller (Windows 11)
# =============================================================================
# One-command uninstall (run PowerShell as Administrator):
#   irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/uninstall_frontend.ps1 | iex
#
# Or run directly from the install directory:
#   & "C:\Program Files\Speech-to-Cobot\uninstall_frontend.ps1"
#
# What this removes:
#   - C:\Program Files\Speech-to-Cobot\  (install directory)
#   - %USERPROFILE%\.cache\whisper\       (Whisper model cache)
#   - %USERPROFILE%\.cache\               (if empty after whisper removal)
#   - Desktop shortcut
#   - ffmpeg (optional — prompted)
#   - uv     (optional — prompted)
#
# What this does NOT remove:
#   - LM Studio — uninstall via Windows Settings -> Apps -> LM Studio
# =============================================================================

$INSTALL_DIR   = "C:\Program Files\Speech-to-Cobot"
$WHISPER_CACHE = "$env:USERPROFILE\.cache\whisper"
$CACHE_DIR     = "$env:USERPROFILE\.cache"
$SHORTCUT      = "$env:USERPROFILE\Desktop\Speech-to-Cobot.lnk"

function Write-Step { param([string]$msg) Write-Host "`n[UNINSTALL] $msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$msg) Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-Warn { param([string]$msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Fail {
    param([string]$msg)
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
    throw $msg
}

function Prompt-YesNo {
    param([string]$question)
    $response = Read-Host "$question [y/n]"
    return $response -eq "y" -or $response -eq "Y"
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

# --- Confirm ------------------------------------------------------------------

Write-Host ""
Write-Host "  This will remove Speech-to-Cobot from this machine." -ForegroundColor Yellow
Write-Host "  Install directory: $INSTALL_DIR"                     -ForegroundColor Yellow
Write-Host "  Whisper cache:     $WHISPER_CACHE"                   -ForegroundColor Yellow
Write-Host "  Desktop shortcut:  $SHORTCUT"                        -ForegroundColor Yellow
Write-Host ""
if (-not (Prompt-YesNo "  Proceed with uninstall?")) {
    Write-Host "  Uninstall cancelled." -ForegroundColor Gray
    exit 0
}

# --- Install directory --------------------------------------------------------

Write-Step "Removing install directory"
if (Test-Path $INSTALL_DIR) {
    # Script may be running from inside the install directory — move to safe location first
    Set-Location $env:USERPROFILE
    Remove-Item -Recurse -Force $INSTALL_DIR
    Write-OK "Removed $INSTALL_DIR"
} else {
    Write-Warn "$INSTALL_DIR not found — already removed or never installed"
}

# --- Desktop shortcut ---------------------------------------------------------

Write-Step "Removing Desktop shortcut"
if (Test-Path $SHORTCUT) {
    Remove-Item -Force $SHORTCUT
    Write-OK "Removed $SHORTCUT"
} else {
    Write-Warn "Shortcut not found — already removed or never created"
}

# --- Whisper cache ------------------------------------------------------------

Write-Step "Removing Whisper model cache"
if (Test-Path $WHISPER_CACHE) {
    Remove-Item -Recurse -Force $WHISPER_CACHE
    Write-OK "Removed $WHISPER_CACHE"
} else {
    Write-Warn "$WHISPER_CACHE not found — already removed or never downloaded"
}

# Remove .cache folder if now empty
if (Test-Path $CACHE_DIR) {
    $remaining = Get-ChildItem -Path $CACHE_DIR -Force
    if (-not $remaining) {
        Remove-Item -Force $CACHE_DIR
        Write-OK "Removed empty $CACHE_DIR"
    } else {
        Write-Warn "$CACHE_DIR still has other content — leaving it in place"
    }
}

# --- ffmpeg (optional) --------------------------------------------------------

Write-Step "ffmpeg"
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    if (Prompt-YesNo "  Remove ffmpeg?") {
        winget uninstall --id Gyan.FFmpeg --scope machine
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "ffmpeg uninstall may have failed — remove manually via winget or Settings -> Apps"
        } else {
            Write-OK "ffmpeg removed"
        }
    } else {
        Write-Warn "ffmpeg kept"
    }
} else {
    Write-Warn "ffmpeg not found on PATH — skipping"
}

# --- uv (optional) ------------------------------------------------------------

Write-Step "uv"
if (Get-Command uv -ErrorAction SilentlyContinue) {
    if (Prompt-YesNo "  Remove uv?") {
        # Remove uv's package cache and Python versions before uninstalling the tool
        $uvPackageCache = "$env:LOCALAPPDATA\uv"
        $uvPythonCache  = "$env:APPDATA\uv"
        if (Test-Path $uvPackageCache) {
            Remove-Item -Recurse -Force $uvPackageCache
            Write-OK "Removed uv package cache at $uvPackageCache"
        }
        if (Test-Path $uvPythonCache) {
            Remove-Item -Recurse -Force $uvPythonCache
            Write-OK "Removed uv Python cache at $uvPythonCache"
        }
        winget uninstall --id astral-sh.uv
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "uv uninstall may have failed — remove manually via winget or Settings -> Apps"
        } else {
            Write-OK "uv removed"
        }
    } else {
        Write-Warn "uv kept"
    }
} else {
    Write-Warn "uv not found — skipping"
}

# --- Done ---------------------------------------------------------------------

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host " Uninstall complete."                                  -ForegroundColor Green
Write-Host ""
Write-Host " To also remove LM Studio:"                           -ForegroundColor White
Write-Host "   Windows Settings -> Apps -> LM Studio -> Uninstall" -ForegroundColor White
Write-Host "=====================================================" -ForegroundColor Green