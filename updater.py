# updater.py

import requests
import threading
import sys
import os
import subprocess
import tempfile
import time

# GitHub repository info
GITHUB_OWNER = "Master00Sniper"
GITHUB_REPO = "Vapor"

# Current app version - this is the single source of truth for the version
CURRENT_VERSION = "0.2.2"

# Cloudflare Worker proxy base URL
PROXY_BASE_URL = "https://vapor-githup-proxy.gkmorton1-b51.workers.dev"

# Proxy paths for GitHub API
LATEST_RELEASE_PROXY_PATH = f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

# Headers (no auth needed; handled by proxy)
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Vapor-Updater/1.0"
}

# Global variable to track pending update
pending_update_path = None


def log(message, category="UPDATE"):
    """Centralized logging with timestamp"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [{category}] {message}")


def is_development_mode():
    """Check if running from PyCharm or development environment"""
    # Not frozen = running as .py file, not .exe
    if not getattr(sys, 'frozen', False):
        return True
    return False


def check_for_updates(current_app_id=None, show_notification_func=None):
    """
    Checks for updates, downloads if available, and handles replacement.
    Only applies update when no game is running.
    """
    global pending_update_path

    # Skip updates in development mode
    if is_development_mode():
        log("Development mode detected - skipping update check", "UPDATE")
        return

    try:
        log(f"Checking for updates (current: v{CURRENT_VERSION})...")

        # Use proxy for release info
        proxy_url = f"{PROXY_BASE_URL}{LATEST_RELEASE_PROXY_PATH}"
        response = requests.get(proxy_url, headers=HEADERS, timeout=10)

        if response.status_code != 200:
            log(f"Proxy returned status {response.status_code}", "ERROR")
            return

        response.raise_for_status()
        release_data = response.json()

        latest_version = release_data.get("tag_name")

        if not latest_version:
            log("No version tag found in release", "ERROR")
            return

        comparison = compare_versions(latest_version, CURRENT_VERSION)

        if comparison > 0:
            log(f"Update available: v{latest_version}")

            assets = release_data.get("assets", [])
            asset = next((a for a in assets if a["name"].lower() == "vapor.exe"), None)

            if not asset:
                log("No vapor.exe found in release assets", "ERROR")
                return

            # For private repos, use the API asset URL (not browser_download_url) to ensure auth via proxy
            asset_api_path = asset["url"].replace("https://api.github.com", "")  # Strip base to append to proxy
            download_proxy_url = f"{PROXY_BASE_URL}{asset_api_path}"

            if current_app_id and current_app_id != 0:
                log(f"Game running (AppID: {current_app_id}) - postponing download")
                if show_notification_func:
                    show_notification_func(f"Update {latest_version} available! Will install after gaming.")
                return

            log("Starting download...")
            if show_notification_func:
                show_notification_func(f"Downloading Vapor update {latest_version}...")

            # Headers for binary download
            download_headers = {
                **HEADERS,
                "Accept": "application/octet-stream"
            }

            download_response = requests.get(download_proxy_url, headers=download_headers, stream=True, timeout=30)
            download_response.raise_for_status()

            temp_dir = tempfile.gettempdir()
            temp_exe_path = os.path.join(temp_dir, "vapor_new.exe")

            total_size = 0
            with open(temp_exe_path, "wb") as f:
                for chunk in download_response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    total_size += len(chunk)

            if os.path.exists(temp_exe_path) and os.path.getsize(temp_exe_path) > 0:
                log(f"Download complete: {total_size / 1024 / 1024:.2f} MB")
            else:
                log("Download failed - empty file", "ERROR")
                return

            pending_update_path = temp_exe_path

            if current_app_id and current_app_id != 0:
                log("Game running - update will apply after gaming session")
                if show_notification_func:
                    show_notification_func(f"Update {latest_version} ready! Will install after gaming.")
            else:
                log("Applying update immediately...")
                apply_pending_update(show_notification_func)
        else:
            log(f"Already up to date (v{CURRENT_VERSION})")

    except requests.RequestException as e:
        log(f"Network error: {e}", "ERROR")
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        import traceback
        traceback.print_exc()


def apply_pending_update(show_notification_func=None):
    """
    Applies a pending update if one exists.
    """
    global pending_update_path

    if pending_update_path and os.path.exists(pending_update_path):
        log(f"Applying pending update from: {pending_update_path}")

        if show_notification_func:
            show_notification_func("Update ready! Vapor will restart in 5 seconds...")

        time.sleep(5)
        perform_update(pending_update_path)
        pending_update_path = None
    else:
        if pending_update_path:
            log("Pending update file not found - cleaning up")
            try:
                os.remove(pending_update_path)
            except:
                pass
        pending_update_path = None


def periodic_update_check(stop_event, get_current_app_id_func, show_notification_func, check_interval=3600):
    """
    Periodically checks for updates in the background.
    """
    log("Update checker starting (first check in 30 seconds)...")

    if stop_event.wait(30):
        return

    check_count = 0
    while not stop_event.is_set():
        try:
            check_count += 1
            log(f"Periodic check #{check_count}")
            current_app_id = get_current_app_id_func() if get_current_app_id_func else 0
            check_for_updates(current_app_id, show_notification_func)
        except Exception as e:
            log(f"Error in periodic check: {e}", "ERROR")

        log(f"Next check in {check_interval // 60} minutes")
        if stop_event.wait(check_interval):
            break

    log("Update checker stopped")


def compare_versions(version1, version2):
    """
    Compare two semantic versions (e.g., '1.2.3' > '1.2.2' returns 1)
    """
    v1 = list(map(int, version1.lstrip('v').split('.')))
    v2 = list(map(int, version2.lstrip('v').split('.')))
    for a, b in zip(v1, v2):
        if a > b:
            return 1
        if a < b:
            return -1
    return 0 if len(v1) == len(v2) else (1 if len(v1) > len(v2) else -1)


def perform_update(new_exe_path):
    """
    Creates a VBScript wrapper to run batch file completely hidden,
    then executes the update process.
    """
    current_exe = sys.executable
    current_exe_dir = os.path.dirname(current_exe)
    temp_dir = tempfile.gettempdir()
    batch_path = os.path.join(temp_dir, "vapor_update.bat")
    vbs_path = os.path.join(temp_dir, "vapor_update.vbs")
    log_path = os.path.join(temp_dir, "vapor_update_log.txt")

    log(f"Creating update scripts...")
    log(f"Current exe: {current_exe}")
    log(f"Current exe dir: {current_exe_dir}")
    log(f"New exe: {new_exe_path}")

    # Batch file content - NO LEADING SPACES (critical for batch files)
    batch_content = f'''@echo off
set attempts=0
set max_attempts=30
echo %date% %time% - Starting update process... > "{log_path}"
echo Waiting for Vapor to close... >> "{log_path}"
ping 127.0.0.1 -n 3 > nul

echo Force-killing any lingering Vapor processes... >> "{log_path}"
taskkill /f /im vapor.exe >> "{log_path}" 2>&1
ping 127.0.0.1 -n 3 > nul

echo Cleaning up old PyInstaller temp folders... >> "{log_path}"
for /d %%i in ("%TEMP%\\_MEI*") do (
    rmdir /s /q "%%i" 2>nul
)
echo Cleanup complete. >> "{log_path}"

:delete_loop
set /a attempts+=1
echo Attempt %attempts%: Deleting old version... >> "{log_path}"
del /F /Q "{current_exe}" 2>> "{log_path}"
if exist "{current_exe}" (
    if %attempts% geq %max_attempts% (
        echo ERROR: Failed to delete after %max_attempts% attempts. >> "{log_path}"
        goto cleanup
    )
    echo Old exe still exists - retrying... >> "{log_path}"
    ping 127.0.0.1 -n 2 > nul
    goto delete_loop
)
echo Old version deleted after %attempts% attempt(s). >> "{log_path}"

echo Moving new version into place... >> "{log_path}"
move /Y "{new_exe_path}" "{current_exe}" >> "{log_path}" 2>&1
if not exist "{current_exe}" (
    echo ERROR: Move failed! >> "{log_path}"
    goto cleanup
)
echo Move successful. >> "{log_path}"
ping 127.0.0.1 -n 3 > nul

echo Starting updated Vapor... >> "{log_path}"
cd /d "{current_exe_dir}"
echo Working directory: %CD% >> "{log_path}"
echo Launching via explorer: "{current_exe}" >> "{log_path}"
explorer.exe "{current_exe}"
echo Launch complete. >> "{log_path}"
echo Start command issued. >> "{log_path}"

:cleanup
echo Cleaning up batch file... >> "{log_path}"
del /F /Q "{vbs_path}" 2>nul
del /F /Q "%~f0"
'''

    # VBScript to run batch file completely hidden (no window flash at all)
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & "{batch_path}" & chr(34), 0, False
Set WshShell = Nothing
'''

    try:
        # Write batch file
        with open(batch_path, "w", encoding="ascii", errors="replace") as f:
            f.write(batch_content)
        log("Batch file created")

        # Write VBScript wrapper
        with open(vbs_path, "w", encoding="ascii", errors="replace") as f:
            f.write(vbs_content)
        log("VBScript wrapper created")

        # Verify files exist
        if not os.path.exists(batch_path):
            log("Batch file creation failed!", "ERROR")
            return
        if not os.path.exists(vbs_path):
            log("VBScript creation failed!", "ERROR")
            return

        log("Executing update via VBScript (fully hidden)...")

        # Run VBScript with wscript (not cscript) for no console
        # CREATE_NO_WINDOW flag ensures absolutely no window
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            ["wscript.exe", "//nologo", vbs_path],
            creationflags=subprocess.DETACHED_PROCESS | CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )

        log("Update process launched - exiting Vapor...")

        # Give a tiny moment for the process to start
        time.sleep(0.5)

        # Force exit
        os._exit(0)

    except Exception as e:
        log(f"Update execution failed: {e}", "ERROR")
        import traceback
        traceback.print_exc()