# =============================================================================
# uninstall_backend.ps1
# Speech-to-Code Framework — Backend Uninstaller (Windows 11)
# =============================================================================
# One-command uninstall (run PowerShell as Administrator):
#   irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/dev/Setup/uninstall_backend.ps1 | iex
#
# Or run directly from the install directory:
#   & "C:\Program Files\Speech-to-Cobot-Backend\uninstall_backend.ps1"
#
# What this removes:
#   - C:\Program Files\Speech-to-Cobot-Backend\  (install directory)
#   - uv package and Python cache (optional — prompted)
#
# What this does NOT remove:
#   - uv itself (optional — prompted)
#   - Frontend install if present
# =============================================================================

$INSTALL_DIR = "C:\Program Files\Speech-to-Cobot-Backend"

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
Write-Host "  This will remove Speech-to-Cobot Backend from this machine." -ForegroundColor Yellow
Write-Host "  Install directory: $INSTALL_DIR"                              -ForegroundColor Yellow
Write-Host ""
if (-not (Prompt-YesNo "  Proceed with uninstall?")) {
    Write-Host "  Uninstall cancelled." -ForegroundColor Gray
    exit 0
}

# --- Install directory --------------------------------------------------------

Write-Step "Removing install directory"
if (Test-Path $INSTALL_DIR) {
    Set-Location $env:USERPROFILE
    Remove-Item -Recurse -Force $INSTALL_DIR
    Write-OK "Removed $INSTALL_DIR"
} else {
    Write-Warn "$INSTALL_DIR not found — already removed or never installed"
}

# --- uv (optional) ------------------------------------------------------------
# Only prompt if frontend is not installed — removing uv affects both.

Write-Step "uv"
$frontendInstalled = Test-Path "C:\Program Files\Speech-to-Cobot"
if ($frontendInstalled) {
    Write-Warn "Frontend is also installed — skipping uv removal to avoid breaking it."
    Write-Warn "Run uninstall_frontend.ps1 first if you want to remove uv."
} elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    if (Prompt-YesNo "  Remove uv?") {
        $uvPackageCache = "$env:LOCALAPPDATA\uv"
        $uvPythonCache  = "$env:APPDATA\uv"
        if (Test-Path $uvPackageCache) {
            Remove-Item -Recurse -Force $uvPackageCache
            Write-OK "Removed uv package cache"
        }
        if (Test-Path $uvPythonCache) {
            Remove-Item -Recurse -Force $uvPythonCache
            Write-OK "Removed uv Python cache"
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
Write-Host "=====================================================" -ForegroundColor Green
