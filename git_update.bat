@echo off
setlocal enabledelayedexpansion

echo ============================================
echo Vapor Release Script
echo ============================================
echo.

:: Extract version from updater.py
echo Extracting version from updater.py...
for /f "tokens=2 delims='\"" %%a in ('findstr /C:"CURRENT_VERSION = " updater.py') do set VERSION=%%a

if "%VERSION%"=="" (
    echo ERROR: Could not extract version from updater.py
    exit /b 1
)

echo Detected version: %VERSION%
echo.

:: Check if RELEASE_NOTES.md exists
if not exist "RELEASE_NOTES.md" (
    echo ERROR: RELEASE_NOTES.md not found. Please create release notes first.
    exit /b 1
)

:: Confirm before proceeding
echo This will:
echo   1. Build Vapor.exe using Nuitka
echo   2. Create GitHub release v%VERSION%
echo.
set /p CONFIRM="Continue? (y/n): "
if /i not "%CONFIRM%"=="y" (
    echo Cancelled.
    exit /b 0
)

:: Run Nuitka build
echo.
echo ============================================
echo Building Vapor.exe with Nuitka...
echo ============================================
call build_nuitka.bat

if errorlevel 1 (
    echo ERROR: Build failed!
    exit /b 1
)

:: Check if Vapor.exe was created
if not exist "dist\Vapor.exe" (
    echo ERROR: dist\Vapor.exe not found. Build may have failed.
    exit /b 1
)

echo.
echo Build successful!
echo.

:: Create GitHub release
echo ============================================
echo Creating GitHub release v%VERSION%...
echo ============================================
gh release create v%VERSION% "dist/Vapor.exe" --repo Master00Sniper/Vapor --title "Vapor v%VERSION%" --notes-file RELEASE_NOTES.md --target main

if errorlevel 1 (
    echo ERROR: Failed to create GitHub release!
    exit /b 1
)

echo.
echo ============================================
echo Done! Release v%VERSION% created successfully.
echo ============================================
