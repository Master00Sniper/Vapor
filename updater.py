# updater.py

import requests
import threading
import sys
import os
import subprocess
import tempfile
import time

# Replace these with your actual values
GITHUB_OWNER = "Master00Sniper"  # e.g., "Master00Sniper"
GITHUB_REPO = "Vapor"  # Your private repo name
GITHUB_PAT = "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"  # Your PAT - obfuscate this in production (e.g., use base64 or env var)

# Current app version - this is the single source of truth for the version
CURRENT_VERSION = "0.1.1"

# GitHub API endpoint for latest release
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

# Headers for authentication
HEADERS = {
    "Authorization": f"token {GITHUB_PAT}",
    "Accept": "application/vnd.github.v3+json"
}

# Global variable to track pending update
pending_update_path = None


def check_for_updates(current_app_id=None, show_notification_func=None):
    """
    Checks for updates, downloads if available, and handles replacement.
    Only applies update when no game is running.

    Args:
        current_app_id: The currently running Steam game ID (0 if none)
        show_notification_func: Function to show notifications to user
    """
    global pending_update_path

    try:
        print(f"[UPDATE] Checking for updates... Current version: {CURRENT_VERSION}")
        print(f"[UPDATE] API URL: {LATEST_RELEASE_URL}")

        # Fetch latest release info
        response = requests.get(LATEST_RELEASE_URL, headers=HEADERS, timeout=10)
        print(f"[UPDATE] Response status: {response.status_code}")
        response.raise_for_status()
        release_data = response.json()
        print(f"[UPDATE] Release data received: {release_data.get('tag_name', 'No tag')}")

        latest_version = release_data.get("tag_name")
        print(f"[UPDATE] Latest version on GitHub: {latest_version}")
        print(
            f"[UPDATE] Version comparison result: {compare_versions(latest_version, CURRENT_VERSION) if latest_version else 'N/A'}")

        if latest_version and compare_versions(latest_version, CURRENT_VERSION) > 0:
            print(f"[UPDATE] Update available: {latest_version} (current: {CURRENT_VERSION})")

            # Find the asset (assuming your EXE is named 'vapor.exe')
            assets = release_data.get("assets", [])
            print(f"[UPDATE] Found {len(assets)} asset(s): {[a['name'] for a in assets]}")
            asset = next((a for a in assets if a["name"] == "vapor.exe"), None)
            if asset:
                print(f"[UPDATE] Found vapor.exe asset")
                download_url = asset["url"]  # This is the API URL for the asset

                # Check if game is running before downloading
                if current_app_id and current_app_id != 0:
                    print(f"[UPDATE] Game is running (AppID: {current_app_id}) - postponing update download")
                    if show_notification_func:
                        show_notification_func(
                            f"Update {latest_version} available! Will install after you finish gaming.")
                    return

                print(f"[UPDATE] Starting download from {download_url}")
                # Notify user that update is downloading
                if show_notification_func:
                    show_notification_func(f"Downloading Vapor update {latest_version}...")

                # Download with auth and Accept for binary
                download_headers = {
                    **HEADERS,
                    "Accept": "application/octet-stream"
                }
                download_response = requests.get(download_url, headers=download_headers, stream=True, timeout=30)
                download_response.raise_for_status()

                # Save to temp file
                temp_dir = tempfile.gettempdir()
                temp_exe_path = os.path.join(temp_dir, "vapor_new.exe")
                with open(temp_exe_path, "wb") as f:
                    for chunk in download_response.iter_content(chunk_size=8192):
                        f.write(chunk)

                print(f"Downloaded update to {temp_exe_path}")
                pending_update_path = temp_exe_path
                print(f"[UPDATE] Pending update stored at: {pending_update_path}")

                # Check if game is running before applying update
                if current_app_id and current_app_id != 0:
                    print(f"[UPDATE] Game is running (AppID: {current_app_id}) - postponing update installation")
                    if show_notification_func:
                        show_notification_func(
                            f"Update {latest_version} downloaded! Will install after you finish gaming.")
                else:
                    # No game running, apply update immediately
                    print(f"[UPDATE] No game running - applying update immediately")
                    apply_pending_update(show_notification_func)
            else:
                print("[UPDATE] ERROR: No matching asset found in release (looking for 'vapor.exe')")
        else:
            print(f"[UPDATE] No update available. Latest: {latest_version}, Current: {CURRENT_VERSION}")
    except requests.RequestException as e:
        print(f"[UPDATE] ERROR - Update check failed (network/API error): {e}")
    except Exception as e:
        print(f"[UPDATE] ERROR - Unexpected error during update: {e}")
        import traceback
        traceback.print_exc()


def apply_pending_update(show_notification_func=None):
    """
    Applies a pending update if one exists.
    Should only be called when no game is running.
    """
    global pending_update_path

    if pending_update_path and os.path.exists(pending_update_path):
        print(f"Applying pending update from {pending_update_path}")

        # Notify user before updating
        if show_notification_func:
            show_notification_func("Update ready! Vapor will restart in 5 seconds...")

        time.sleep(5)

        # Handle replacement and restart
        perform_update(pending_update_path)
        pending_update_path = None


def periodic_update_check(stop_event, get_current_app_id_func, show_notification_func, check_interval=3600):
    """
    Periodically checks for updates in the background.

    Args:
        stop_event: Threading event to stop the loop
        get_current_app_id_func: Function that returns the current Steam game ID
        show_notification_func: Function to show notifications
        check_interval: How often to check (in seconds, default 1 hour)
    """
    # Wait a bit before first check to let app initialize
    if stop_event.wait(60):  # Wait 60 seconds before first check
        return

    while not stop_event.is_set():
        try:
            current_app_id = get_current_app_id_func() if get_current_app_id_func else 0
            check_for_updates(current_app_id, show_notification_func)
        except Exception as e:
            print(f"Error in periodic update check: {e}")

        # Wait for the check interval or until stop_event is set
        if stop_event.wait(check_interval):
            break


def compare_versions(version1, version2):
    """
    Compare two semantic versions (e.g., '1.2.3' > '1.2.2' returns 1)
    Returns: 1 if v1 > v2, -1 if v1 < v2, 0 if equal
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
    Creates a batch file to replace the current EXE and restart.
    """
    current_exe = sys.executable  # Path to current running EXE
    batch_path = os.path.join(tempfile.gettempdir(), "vapor_update.bat")

    print(f"[UPDATE] Creating batch file at: {batch_path}")
    print(f"[UPDATE] Current exe: {current_exe}")
    print(f"[UPDATE] New exe: {new_exe_path}")

    # Batch content - added echo statements for debugging
    batch_content = f"""@echo off
echo Waiting for Vapor to close...
timeout /t 3 /nobreak >nul
echo Deleting old version...
del "{current_exe}" >nul 2>&1
echo Moving new version...
move "{new_exe_path}" "{current_exe}" >nul 2>&1
echo Starting updated Vapor...
start "" "{current_exe}"
echo Cleaning up...
del "%~f0"
"""

    try:
        with open(batch_path, "w") as batch_file:
            batch_file.write(batch_content)
        print(f"[UPDATE] Batch file created successfully")

        # Verify batch file exists
        if os.path.exists(batch_path):
            print(f"[UPDATE] Batch file verified at: {batch_path}")
        else:
            print(f"[UPDATE] ERROR: Batch file not found after creation!")
            return

        # Run the batch file
        print(f"[UPDATE] Starting batch file...")
        subprocess.Popen(["cmd.exe", "/c", batch_path],
                         creationflags=subprocess.CREATE_NEW_CONSOLE)

        print(f"[UPDATE] Exiting application...")
        # Force exit the entire process
        os._exit(0)

    except Exception as e:
        print(f"[UPDATE] ERROR creating/running batch file: {e}")
        import traceback
        traceback.print_exc()