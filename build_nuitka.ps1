# Nuitka Build Script for Vapor
# This compiles Vapor to a native Windows executable

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Vapor Nuitka Build Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Extract version from updater.py (single source of truth)
Write-Host "Extracting version from updater.py..."
$versionLine = Select-String -Path "updater.py" -Pattern 'CURRENT_VERSION = "([^"]+)"'
if ($versionLine) {
    $VERSION = $versionLine.Matches[0].Groups[1].Value
    Write-Host "Detected version: $VERSION" -ForegroundColor Green
} else {
    Write-Host "ERROR: Could not extract version from updater.py" -ForegroundColor Red
    exit 1
}

# Other metadata
$COMPANY = "Morton Apps"
$PRODUCT = "Vapor"
$COPYRIGHT = "Copyright (c) 2024-2026 Greg Morton. Licensed under GPL v3."

Write-Host ""

# Check if Nuitka is installed
Write-Host "Checking for Nuitka..."
$nuitkaCheck = python -m nuitka --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Nuitka not found. Installing..." -ForegroundColor Yellow
    pip install nuitka ordered-set zstandard
    Write-Host ""
}

Write-Host "Starting Nuitka compilation..." -ForegroundColor Cyan
Write-Host "This will take 10-30 minutes on first build."
Write-Host ""

# Build the Nuitka command
$nuitkaArgs = @(
    "-m", "nuitka",
    "--standalone",
    "--onefile",
    "--assume-yes-for-downloads",
    "--msvc=latest",
    "--windows-console-mode=disable",
    "--windows-icon-from-ico=Images/exe_icon.ico",
    "--output-filename=Vapor.exe",
    "--output-dir=dist",
    "--company-name=$COMPANY",
    "--product-name=$PRODUCT",
    "--file-version=$VERSION",
    "--product-version=$VERSION",
    "--file-description=Vapor - Your Personal Gaming Assistant",
    "--copyright=$COPYRIGHT",
    "--enable-plugin=tk-inter",
    "--include-data-dir=Images=Images",
    "--include-data-dir=lib=lib",
    "--include-data-dir=sounds=sounds",
    "--include-data-files=install_pawnio.ps1=install_pawnio.ps1",
    "--include-module=vapor_settings_ui",
    "--include-module=updater",
    "--include-module=core",
    "--include-module=utils",
    "--include-module=platform_utils",
    "--include-module=win32gui",
    "--include-module=win32con",
    "--include-module=win32event",
    "--include-module=win32api",
    "--include-module=win32file",
    "--include-module=win32timezone",
    "--include-module=win32com",
    "--include-module=win32com.client",
    "--include-module=pywintypes",
    "--include-module=pythoncom",
    "--include-module=comtypes",
    "--include-module=comtypes.client",
    "--include-module=pycaw",
    "--include-module=pycaw.pycaw",
    "--include-module=customtkinter",
    "--include-module=PIL",
    "--include-module=PIL.Image",
    "--include-module=PIL.ImageTk",
    "--include-module=keyboard",
    "--include-module=pystray",
    "--include-module=watchdog",
    "--include-module=watchdog.observers",
    "--include-module=win11toast",
    "--include-module=psutil",
    "--include-module=requests",
    "--include-module=certifi",
    "--include-module=pynvml",
    "--include-module=pyadl",
    "--include-module=wmi",
    "--include-module=clr",
    "--include-module=pythonnet",
    "--include-module=HardwareMonitor",
    "--include-package-data=HardwareMonitor",
    "--include-package-data=customtkinter",
    "steam_game_detector.py"
)

# Run Nuitka
& python $nuitkaArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host "BUILD FAILED" -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host "Check the error messages above."
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "BUILD SUCCESSFUL" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Output: dist\Vapor.exe"
Write-Host "Version: $VERSION"
Write-Host ""
