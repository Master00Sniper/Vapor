# updater.py
# Handles automatic updates for Vapor via GitHub releases through a Cloudflare proxy.

import requests
import subprocess
import tempfile
import time
import sys
import os

# =============================================================================
# Configuration
# =============================================================================

GITHUB_OWNER = "Master00Sniper"
GITHUB_REPO = "Vapor"
CURRENT_VERSION = "0.3.7"  # Single source of truth for app version

# Cloudflare Worker proxy (handles GitHub API authentication)
PROXY_BASE_URL = "https://vapor-proxy.mortonapps.com"
LATEST_RELEASE_PROXY_PATH = f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Vapor-Updater/1.0",
    #Token is for rate limiting purposes, anonymous telemetry, and GitHub issues submission. Nothing important.
    #If you'd really like to spam me with GitHub issues, I'd feel honored I at least got some attention.
    "X-Vapor-Auth": "ombxslvdyyqvlkiiogwmjlkpocwqufaa"
}

# Telemetry heartbeat interval in seconds (1 hour = 3600, can be changed to 12h or 24h later)
HEARTBEAT_INTERVAL = 3600

# Tracks downloaded update waiting to be applied
pending_update_path = None


# =============================================================================
# Logging
# =============================================================================

# Log file for debugging (stored in %APPDATA%/Vapor)
_appdata_dir = os.path.join(os.getenv('APPDATA', ''), 'Vapor')
os.makedirs(_appdata_dir, exist_ok=True)
DEBUG_LOG_FILE = os.path.join(_appdata_dir, 'vapor_logs.log')

# Maximum log file size (2 MB) - will be truncated when exceeded
MAX_LOG_SIZE = 2 * 1024 * 1024


def log(message, category="UPDATE"):
    """Print timestamped log message and write to log file."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [{category}] {message}"

    # Print to console (if available)
    try:
        print(formatted)
    except (OSError, ValueError):
        pass

    # Also write to log file
    try:
        # Check if log file is too large and truncate if needed
        if os.path.exists(DEBUG_LOG_FILE):
            if os.path.getsize(DEBUG_LOG_FILE) > MAX_LOG_SIZE:
                # Keep last 500 lines
                with open(DEBUG_LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[-500:]
                with open(DEBUG_LOG_FILE, 'w', encoding='utf-8') as f:
                    f.writelines(lines)

        with open(DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{formatted}\n")
    except Exception:
        pass


# =============================================================================
# Utility Functions
# =============================================================================


def is_development_mode():
    """Check if running from source (not compiled .exe)."""
    return not getattr(sys, 'frozen', False)


def compare_versions(version1, version2):
    """
    Compare semantic versions (e.g., '1.2.3' vs '1.2.2').
    Returns: 1 if v1 > v2, -1 if v1 < v2, 0 if equal.
    """
    v1 = list(map(int, version1.lstrip('v').split('.')))
    v2 = list(map(int, version2.lstrip('v').split('.')))

    for a, b in zip(v1, v2):
        if a > b:
            return 1
        if a < b:
            return -1

    # Handle different version lengths (e.g., 1.2 vs 1.2.1)
    return 0 if len(v1) == len(v2) else (1 if len(v1) > len(v2) else -1)


# =============================================================================
# Telemetry (Anonymous Usage Analytics)
# =============================================================================

# File to store unique installation ID
INSTALL_ID_FILE = os.path.join(_appdata_dir, 'install_id')


def _get_or_create_install_id():
    """Get existing install ID or create a new one."""
    import uuid
    try:
        if os.path.exists(INSTALL_ID_FILE):
            with open(INSTALL_ID_FILE, 'r') as f:
                install_id = f.read().strip()
                if install_id:
                    return install_id

        # Generate new UUID for this installation
        install_id = str(uuid.uuid4())
        with open(INSTALL_ID_FILE, 'w') as f:
            f.write(install_id)
        return install_id
    except Exception:
        return "unknown"


def _get_os_info():
    """Get basic OS information."""
    import platform
    try:
        return f"{platform.system()} {platform.release()}"
    except Exception:
        return "unknown"


def send_telemetry(event="app_start"):
    """
    Send anonymous usage telemetry to the proxy.
    This helps track how many people are using Vapor.

    Data sent:
    - event: Type of event (app_start, app_close, etc.)
    - version: App version
    - os: Operating system info
    - install_id: Anonymous unique installation identifier

    No personal information is collected.
    Telemetry can be disabled in Settings > Preferences.
    """
    import threading

    # Check if telemetry is enabled in settings
    try:
        from utils.settings import get_setting
        if not get_setting('enable_telemetry', True):
            log("Telemetry disabled by user setting", "TELEMETRY")
            return
    except Exception:
        pass  # If settings can't be read, proceed with telemetry (default enabled)

    def _send():
        try:
            payload = {
                "event": event,
                "version": CURRENT_VERSION,
                "os": _get_os_info(),
                "install_id": _get_or_create_install_id()
            }

            response = requests.post(
                f"{PROXY_BASE_URL}/telemetry",
                headers=HEADERS,
                json=payload,
                timeout=5
            )

            if response.status_code == 200:
                log(f"Telemetry sent: {event}", "TELEMETRY")
            else:
                log(f"Telemetry failed: {response.status_code}", "TELEMETRY")
        except Exception as e:
            # Fail silently - telemetry should never affect the app
            log(f"Telemetry error (ignored): {e}", "TELEMETRY")

    # Run in background thread to not block startup
    threading.Thread(target=_send, daemon=True).start()


# =============================================================================
# Update Check & Download
# =============================================================================

def check_for_updates(current_app_id=None, show_notification_func=None):
    """
    Check GitHub for new releases and download if available.
    Postpones installation if a game is currently running.

    Args:
        current_app_id: Steam AppID of running game (0 or None if no game)
        show_notification_func: Callback to display user notifications
    """
    global pending_update_path

    if is_development_mode():
        log("Development mode - skipping update check")
        return

    try:
        log(f"Checking for updates (current: v{CURRENT_VERSION})...")
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

        # Compare versions to determine if update is needed
        if compare_versions(latest_version, CURRENT_VERSION) <= 0:
            log(f"Already up to date (v{CURRENT_VERSION})")
            return

        log(f"Update available: v{latest_version}")

        # Find the vapor.exe asset in the release
        assets = release_data.get("assets", [])
        asset = next((a for a in assets if a["name"].lower() == "vapor.exe"), None)
        if not asset:
            log("No vapor.exe found in release assets", "ERROR")
            return

        # Build download URL through proxy
        asset_api_path = asset["url"].replace("https://api.github.com", "")
        download_proxy_url = f"{PROXY_BASE_URL}{asset_api_path}"

        # Postpone download if game is running
        if current_app_id and current_app_id != 0:
            log(f"Game running (AppID: {current_app_id}) - postponing download")
            if show_notification_func:
                show_notification_func(f"Update {latest_version} available! Will install after gaming.")
            return

        # Download the update
        log("Starting download...")
        if show_notification_func:
            show_notification_func(f"Downloading and installing update {latest_version}...")

        download_headers = {**HEADERS, "Accept": "application/octet-stream"}
        download_response = requests.get(download_proxy_url, headers=download_headers, stream=True, timeout=30)
        download_response.raise_for_status()

        # Save to temp directory
        temp_dir = tempfile.gettempdir()
        temp_exe_path = os.path.join(temp_dir, "vapor_new.exe")

        total_size = 0
        with open(temp_exe_path, "wb") as f:
            for chunk in download_response.iter_content(chunk_size=8192):
                f.write(chunk)
                total_size += len(chunk)

        # Verify download succeeded
        if not os.path.exists(temp_exe_path) or os.path.getsize(temp_exe_path) == 0:
            log("Download failed - empty file", "ERROR")
            return

        log(f"Download complete: {total_size / 1024 / 1024:.2f} MB")
        pending_update_path = temp_exe_path

        # Apply immediately if no game running, otherwise wait
        if current_app_id and current_app_id != 0:
            log("Game running - update will apply after gaming session")
            if show_notification_func:
                show_notification_func(f"Update {latest_version} ready! Will install after gaming.")
        else:
            log("Applying update immediately...")
            apply_pending_update(show_notification_func)

    except requests.exceptions.ConnectionError as e:
        log(f"Connection error: {e}", "ERROR")
    except requests.exceptions.Timeout as e:
        log(f"Timeout error: {e}", "ERROR")
    except requests.exceptions.SSLError as e:
        log(f"SSL error: {e}", "ERROR")
    except requests.RequestException as e:
        log(f"Network error: {e}", "ERROR")
    except Exception as e:
        log(f"Unexpected error: {type(e).__name__}: {e}", "ERROR")
        import traceback
        traceback.print_exc()


# =============================================================================
# Update Application
# =============================================================================

def apply_pending_update(show_notification_func=None):
    """
    Apply a previously downloaded update.
    Shows notification and restarts Vapor with the new version.
    """
    global pending_update_path

    if not pending_update_path or not os.path.exists(pending_update_path):
        if pending_update_path:
            log("Pending update file not found - cleaning up")
            try:
                os.remove(pending_update_path)
            except:
                pass
        pending_update_path = None
        return

    log(f"Applying pending update from: {pending_update_path}")

    if show_notification_func:
        show_notification_func("Vapor will restart in a few seconds...")

    time.sleep(5)
    perform_update(pending_update_path)
    pending_update_path = None


def perform_update(new_exe_path):
    """
    Execute the update by replacing the current executable.
    Uses a VBScript wrapper to run the update batch file silently (no window flash).
    """
    # Determine the actual Vapor.exe path
    # Nuitka: use sys.argv[0] for the executable path
    if getattr(sys, 'frozen', False):
        current_exe = sys.argv[0]
    else:
        current_exe = sys.executable
    current_exe_dir = os.path.dirname(current_exe)
    temp_dir = tempfile.gettempdir()
    batch_path = os.path.join(temp_dir, "vapor_update.bat")
    vbs_path = os.path.join(temp_dir, "vapor_update.vbs")
    log_path = os.path.join(temp_dir, "vapor_update_log.txt")

    log("Creating update scripts...")
    log(f"Current exe: {current_exe}")
    log(f"New exe: {new_exe_path}")

    # Batch script: waits for Vapor to close, replaces exe, restarts
    # Note: No leading spaces - critical for batch file syntax
    batch_content = f'''@echo off
set attempts=0
set max_attempts=30
echo %date% %time% - Starting update process... > "{log_path}"
echo Waiting for Vapor to close... >> "{log_path}"
ping 127.0.0.1 -n 3 > nul

echo Force-killing any lingering Vapor processes... >> "{log_path}"
taskkill /f /im vapor.exe >> "{log_path}" 2>&1
ping 127.0.0.1 -n 3 > nul

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

:cleanup
echo Cleaning up batch file... >> "{log_path}"
del /F /Q "{vbs_path}" 2>nul
del /F /Q "%~f0"
'''

    # VBScript wrapper: runs batch file completely hidden (no console window)
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & "{batch_path}" & chr(34), 0, False
Set WshShell = Nothing
'''

    try:
        # Write update scripts
        with open(batch_path, "w", encoding="ascii", errors="replace") as f:
            f.write(batch_content)
        log("Batch file created")

        with open(vbs_path, "w", encoding="ascii", errors="replace") as f:
            f.write(vbs_content)
        log("VBScript wrapper created")

        if not os.path.exists(batch_path) or not os.path.exists(vbs_path):
            log("Script creation failed!", "ERROR")
            return

        log("Executing update via VBScript (fully hidden)...")

        # Launch VBScript with no window
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            ["wscript.exe", "//nologo", vbs_path],
            creationflags=subprocess.DETACHED_PROCESS | CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )

        log("Update process launched - exiting Vapor...")
        time.sleep(0.5)
        os._exit(0)

    except Exception as e:
        log(f"Update execution failed: {e}", "ERROR")
        import traceback
        traceback.print_exc()


# =============================================================================
# Background Update Checker
# =============================================================================

def periodic_update_check(stop_event, get_current_app_id_func, show_notification_func, check_interval=3600):
    """
    Background thread that periodically checks for updates and sends telemetry heartbeats.

    Args:
        stop_event: Threading event to signal shutdown
        get_current_app_id_func: Callback returning current game's Steam AppID
        show_notification_func: Callback to display user notifications
        check_interval: Seconds between checks (default: 1 hour)
    """
    log(f"Update checker starting (first check in {check_interval // 60} minutes)...")

    check_count = 0
    last_heartbeat_time = time.time()  # Track when we last sent a heartbeat

    while not stop_event.is_set():
        # Wait before checking (first check waits full interval, no immediate check on startup)
        log(f"Next check in {check_interval // 60} minutes")
        if stop_event.wait(check_interval):
            break

        try:
            check_count += 1
            log(f"Periodic check #{check_count}")

            # Send telemetry heartbeat if enough time has passed
            current_time = time.time()
            if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL:
                log("Sending telemetry heartbeat...")
                send_telemetry("heartbeat")
                last_heartbeat_time = current_time

            current_app_id = get_current_app_id_func() if get_current_app_id_func else 0
            check_for_updates(current_app_id, show_notification_func)
        except Exception as e:
            log(f"Error in periodic check: {e}", "ERROR")

    log("Update checker stopped")