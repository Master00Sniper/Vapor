# PawnIO Driver Installer for Vapor
# This script installs the PawnIO driver required for CPU temperature monitoring
# Run this script as Administrator

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "This script requires Administrator privileges." -ForegroundColor Red
    Write-Host "Please right-click and select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host "================================" -ForegroundColor Cyan
Write-Host "  Vapor - PawnIO Driver Setup  " -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This will install the PawnIO driver for CPU temperature monitoring." -ForegroundColor White
Write-Host ""

# Check if winget is available
$wingetPath = Get-Command winget -ErrorAction SilentlyContinue
if (-not $wingetPath) {
    Write-Host "ERROR: Windows Package Manager (winget) is not installed." -ForegroundColor Red
    Write-Host "Please install winget from the Microsoft Store (App Installer)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# Check if PawnIO is already installed
Write-Host "Checking if PawnIO is already installed..." -ForegroundColor Gray
$installed = winget list --id "PawnIO.PawnIO" 2>$null | Select-String "PawnIO"

if ($installed) {
    Write-Host ""
    Write-Host "PawnIO is already installed!" -ForegroundColor Green
    Write-Host "CPU temperature monitoring should work in Vapor." -ForegroundColor White
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 0
}

# Install PawnIO
Write-Host ""
Write-Host "Installing PawnIO driver..." -ForegroundColor Yellow
Write-Host ""

try {
    winget install PawnIO.PawnIO --accept-package-agreements --accept-source-agreements

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "================================" -ForegroundColor Green
        Write-Host "  Installation Successful!     " -ForegroundColor Green
        Write-Host "================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "PawnIO driver has been installed." -ForegroundColor White
        Write-Host "Please restart Vapor for CPU temperature monitoring to work." -ForegroundColor Yellow
    } else {
        Write-Host ""
        Write-Host "Installation may have encountered an issue." -ForegroundColor Yellow
        Write-Host "Exit code: $LASTEXITCODE" -ForegroundColor Gray
    }
} catch {
    Write-Host ""
    Write-Host "ERROR: Failed to install PawnIO" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
