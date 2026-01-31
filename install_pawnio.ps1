# PawnIO Driver Silent Installer for Vapor
# This script silently installs the PawnIO driver required for CPU temperature monitoring
# Returns exit code 0 on success, 1 on failure

param(
    [switch]$Silent = $false
)

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    if (-not $Silent) {
        Write-Host "This script requires Administrator privileges." -ForegroundColor Red
    }
    exit 1
}

# Check if winget is available
$wingetPath = Get-Command winget -ErrorAction SilentlyContinue
if (-not $wingetPath) {
    if (-not $Silent) {
        Write-Host "ERROR: Windows Package Manager (winget) is not installed." -ForegroundColor Red
    }
    exit 1
}

# Check if PawnIO is already installed
$installed = winget list --id "PawnIO.PawnIO" 2>$null | Select-String "PawnIO"

if ($installed) {
    if (-not $Silent) {
        Write-Host "PawnIO is already installed." -ForegroundColor Green
    }
    exit 0
}

# Install PawnIO silently
try {
    $result = winget install PawnIO.PawnIO --accept-package-agreements --accept-source-agreements --silent 2>&1

    # Check if installation succeeded
    $verifyInstall = winget list --id "PawnIO.PawnIO" 2>$null | Select-String "PawnIO"

    if ($verifyInstall) {
        if (-not $Silent) {
            Write-Host "PawnIO installed successfully." -ForegroundColor Green
        }
        exit 0
    } else {
        if (-not $Silent) {
            Write-Host "PawnIO installation may have failed." -ForegroundColor Yellow
        }
        exit 1
    }
} catch {
    if (-not $Silent) {
        Write-Host "ERROR: Failed to install PawnIO" -ForegroundColor Red
    }
    exit 1
}
