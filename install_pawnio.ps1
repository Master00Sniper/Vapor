# PawnIO Driver Silent Installer for Vapor
# This script silently installs the PawnIO driver required for CPU temperature monitoring
# Returns exit code 0 on success, 1 on failure

param(
    [switch]$Silent = $false
)

Write-Host "=== PawnIO Installer Started ==="
Write-Host "Running as admin check..."

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script requires Administrator privileges." -ForegroundColor Red
    exit 1
}
Write-Host "Admin check passed."

# Check if winget is available
Write-Host "Checking winget availability..."
$wingetPath = Get-Command winget -ErrorAction SilentlyContinue
if (-not $wingetPath) {
    Write-Host "ERROR: Windows Package Manager (winget) is not installed." -ForegroundColor Red
    exit 1
}
Write-Host "Winget found at: $($wingetPath.Source)"

# Check if PawnIO is already installed
Write-Host "Checking if PawnIO is already installed..."
$installed = winget list --id "namazso.PawnIO" 2>$null | Select-String "PawnIO"

if ($installed) {
    Write-Host "PawnIO is already installed." -ForegroundColor Green
    exit 0
}
Write-Host "PawnIO not found, proceeding with installation..."

# Install PawnIO
Write-Host "Running: winget install namazso.PawnIO --accept-package-agreements --accept-source-agreements --silent"
try {
    $result = winget install namazso.PawnIO --accept-package-agreements --accept-source-agreements --silent 2>&1

    Write-Host "=== Winget Output ===" -ForegroundColor Cyan
    Write-Host $result
    Write-Host "=== End Winget Output ===" -ForegroundColor Cyan

    # Check if installation succeeded
    Write-Host "Verifying installation..."
    $verifyInstall = winget list --id "namazso.PawnIO" 2>$null | Select-String "PawnIO"

    if ($verifyInstall) {
        Write-Host "PawnIO installed successfully." -ForegroundColor Green
        exit 0
    } else {
        Write-Host "PawnIO installation may have failed - not found in winget list." -ForegroundColor Yellow
        Write-Host "Checking alternative detection methods..."

        # Try searching in Program Files
        $pawnioPath = Get-ChildItem -Path "C:\Program Files" -Filter "*PawnIO*" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($pawnioPath) {
            Write-Host "Found PawnIO at: $($pawnioPath.FullName)" -ForegroundColor Green
            exit 0
        }

        Write-Host "PawnIO not detected. Installation failed." -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "ERROR: Exception during installation: $_" -ForegroundColor Red
    exit 1
}
