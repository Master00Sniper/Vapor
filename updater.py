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
GITHUB_REPO = "Vapor"     # Your private repo name
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

def check_for_updates():
    """
    Checks for updates, downloads if available, and handles replacement.
    Runs in a background thread.
    """
    try:
        # Fetch latest release info
        response = requests.get(LATEST_RELEASE_URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
        release_data = response.json()

        latest_version = release_data.get("tag_name")
        if latest_version and compare_versions(latest_version, CURRENT_VERSION) > 0:
            print(f"Update available: {latest_version} (current: {CURRENT_VERSION})")

            # Find the asset (assuming your EXE is named 'vapor.exe')
            asset = next((a for a in release_data.get("assets", []) if a["name"] == "vapor.exe"), None)
            if asset:
                download_url = asset["url"]  # This is the API URL for the asset
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

                # Handle replacement and restart
                perform_update(temp_exe_path)
            else:
                print("No matching asset found in release.")
        else:
            print("No update available.")
    except requests.RequestException as e:
        print(f"Update check failed: {e}")
    except Exception as e:
        print(f"Unexpected error during update: {e}")

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

    # Batch content
    batch_content = f"""@echo off
timeout /t 3 /nobreak >nul
del "{current_exe}" >nul 2>&1
move "{new_exe_path}" "{current_exe}" >nul 2>&1
start "" "{current_exe}"
del "%~f0"
"""

    with open(batch_path, "w") as batch_file:
        batch_file.write(batch_content)

    # Run the batch and exit
    subprocess.Popen(batch_path, shell=True)
    sys.exit(0)  # Quit the app to allow replacement