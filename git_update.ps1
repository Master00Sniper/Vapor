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

# Check if tag already exists
$existingTag = git tag -l "v$VERSION"
if ($existingTag) {
    Write-Host "ERROR: Tag v$VERSION already exists!" -ForegroundColor Red
    Write-Host "Either delete the existing tag or update the version in updater.py" -ForegroundColor Yellow
    exit 1
}

# Confirm before proceeding
Write-Host "This will:"
Write-Host "  1. Create and push tag v$VERSION"
Write-Host "  2. GitHub Actions will build Vapor.exe and create the release"
Write-Host ""
$confirm = Read-Host "Continue? (y/n)"
if ($confirm -ne "y") {
    Write-Host "Cancelled."
    exit 0
}

# Create and push the tag
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Creating tag v$VERSION..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

git tag "v$VERSION"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create tag!" -ForegroundColor Red
    exit 1
}

Write-Host "Pushing tag to GitHub..."
git push origin "v$VERSION"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to push tag!" -ForegroundColor Red
    # Clean up local tag if push failed
    git tag -d "v$VERSION"
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "Tag v$VERSION pushed successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "GitHub Actions is now building Vapor.exe..." -ForegroundColor Yellow
Write-Host "Check progress at: https://github.com/Master00Sniper/Vapor/actions" -ForegroundColor Yellow
Write-Host ""
Write-Host "Once complete, the release will be created automatically with:"
Write-Host "  - Title: Vapor v$VERSION"
Write-Host "  - Description: Contents of RELEASE_NOTES.md"
Write-Host "  - Files: Vapor.exe, LICENSE"
