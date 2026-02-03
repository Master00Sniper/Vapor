# Vapor Release Script
# Run with: .\git_update.ps1

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Vapor Release Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Extract version from updater.py
Write-Host "Extracting version from updater.py..."
$versionLine = Select-String -Path "updater.py" -Pattern 'CURRENT_VERSION = "([^"]+)"'
if ($versionLine) {
    $VERSION = $versionLine.Matches[0].Groups[1].Value
} else {
    Write-Host "ERROR: Could not extract version from updater.py" -ForegroundColor Red
    exit 1
}

Write-Host "Detected version: $VERSION" -ForegroundColor Green
Write-Host ""

# Check if RELEASE_NOTES.md exists
if (-not (Test-Path "RELEASE_NOTES.md")) {
    Write-Host "ERROR: RELEASE_NOTES.md not found. Please create release notes first." -ForegroundColor Red
    exit 1
}

# Confirm before proceeding
Write-Host "This will:"
Write-Host "  1. Create GitHub release v$VERSION"
Write-Host "  2. GitHub Actions will automatically build and attach Vapor.exe"
Write-Host ""
$confirm = Read-Host "Continue? (y/n)"
if ($confirm -ne "y") {
    Write-Host "Cancelled."
    exit 0
}

# Create GitHub release (GitHub Actions will build and attach the .exe)
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Creating GitHub release v$VERSION..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
gh release create "v$VERSION" --repo Master00Sniper/Vapor --title "Vapor v$VERSION" --notes-file RELEASE_NOTES.md --target main

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create GitHub release!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "Release v$VERSION created successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "GitHub Actions is now building Vapor.exe..." -ForegroundColor Yellow
Write-Host "Check progress at: https://github.com/Master00Sniper/Vapor/actions" -ForegroundColor Yellow
Write-Host ""
Write-Host "Once complete, Vapor.exe will be attached to the release automatically."
