# steam_game_detector.py
# Main Vapor application - monitors Steam games and manages system resources during gameplay.

# =============================================================================
# Single Instance Check (runs before anything else)
# =============================================================================

import sys
import os

# Only enforce single instance for main app, not settings UI
VAPOR_MUTEX = None  # Global mutex handle for single instance check
if '--ui' not in sys.argv:
    import win32api, win32event, winerror

    mutex_name = "Vapor_SingleInstance_Mutex"
    VAPOR_MUTEX = win32event.CreateMutex(None, True, mutex_name)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        sys.exit(0)


    def cleanup_stale_mei_folders():
        """
        Remove leftover PyInstaller _MEI folders from previous crashes.
        Must run early to prevent the PyInstaller warning dialog.
        """
        try:
            import shutil
            import tempfile
            temp_dir = tempfile.gettempdir()
            current_mei = getattr(sys, '_MEIPASS', None)

            for item in os.listdir(temp_dir):
                if item.startswith('_MEI'):
                    mei_path = os.path.join(temp_dir, item)
                    # Don't delete our own folder
                    if current_mei and mei_path == current_mei:
                        continue
                    # Only delete if it's a directory
                    if os.path.isdir(mei_path):
                        try:
                            shutil.rmtree(mei_path)
                        except (PermissionError, OSError):
                            # Folder is in use by another process, skip it
                            pass
        except Exception:
            pass  # Don't let cleanup errors prevent app from starting


    if getattr(sys, 'frozen', False):
        cleanup_stale_mei_folders()


# =============================================================================
# Splash Screen
# =============================================================================

def show_splash_screen():
    """Display a 2-second splash screen if splash_screen.png exists."""
    try:
        import tkinter as tk
        from PIL import Image, ImageTk

        # Determine base directory
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        splash_path = os.path.join(base_dir, 'Images', 'splash_screen.png')

        if not os.path.exists(splash_path):
            return  # Skip if no splash image

        # Create splash window
        splash = tk.Tk()
        splash.overrideredirect(True)  # Remove window decorations

        # Load image
        img = Image.open(splash_path)
        photo = ImageTk.PhotoImage(img)

        # Get screen dimensions and center the splash
        screen_width = splash.winfo_screenwidth()
        screen_height = splash.winfo_screenheight()
        x = (screen_width - img.width) // 2
        y = (screen_height - img.height) // 2

        splash.geometry(f"{img.width}x{img.height}+{x}+{y}")

        # Display image
        label = tk.Label(splash, image=photo)
        label.pack()

        # Close after 2 seconds
        splash.after(2000, splash.destroy)
        splash.mainloop()
    except Exception:
        pass  # Skip splash on any error


# Only show splash for main app, not settings UI, and not when restarting elevated
if '--ui' not in sys.argv and '--elevated' not in sys.argv:
    show_splash_screen()

# =============================================================================
# Imports
# =============================================================================

# GUI libraries (keep imports even if PyCharm marks as unused - needed for frozen exe)
import win32gui
import customtkinter

# Standard library
import winreg
import requests
import time
import psutil
import subprocess
import os
import json
import win32api, win32con, win32event, winerror
import keyboard
import pystray
from pystray import MenuItem as item
from PIL import Image
import threading
import ctypes
import ctypes.wintypes
import sys
import re

# Audio control (pycaw)
import comtypes
from comtypes import CLSCTX_ALL, COINIT_MULTITHREADED
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from pycaw.constants import CLSID_MMDeviceEnumerator, EDataFlow, ERole
from pycaw.pycaw import IMMDeviceEnumerator

# File watching for settings changes
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Windows toast notifications
import win11toast

# Core modules (temperature and audio)
from core import (
    NVML_AVAILABLE, PYADL_AVAILABLE, WMI_AVAILABLE, HWMON_AVAILABLE, LHM_AVAILABLE,
    get_gpu_temperature, get_cpu_temperature, show_temperature_alert,
    TemperatureTracker, temperature_tracker,
    TEMP_HISTORY_DIR, get_temp_history_path, load_temp_history, save_temp_history, get_lifetime_max_temps,
    set_system_volume, find_game_pids, set_game_volume,
)

import atexit
import signal


# =============================================================================
# Admin Privilege Functions
# =============================================================================

def request_admin_restart():
    """
    Request admin privileges by restarting the application elevated.
    Returns True if elevation was requested (app will restart), False otherwise.
    """
    if is_admin():
        return False  # Already admin, no need to restart

    try:
        # Get the executable path and working directory
        if getattr(sys, 'frozen', False):
            executable = sys.executable
            # Add --elevated flag to skip splash screen on restart
            existing_params = ' '.join(sys.argv[1:])
            params = f'{existing_params} --elevated'.strip()
            work_dir = os.path.dirname(sys.executable)
        else:
            # Use pythonw.exe to avoid console window when elevated
            python_dir = os.path.dirname(sys.executable)
            pythonw_exe = os.path.join(python_dir, 'pythonw.exe')
            if os.path.exists(pythonw_exe):
                executable = pythonw_exe
            else:
                executable = sys.executable
            script_path = os.path.abspath(__file__)
            # Add --elevated flag to skip splash screen on restart
            params = f'"{script_path}" --elevated'
            work_dir = os.path.dirname(script_path)

        # Request elevation using ShellExecute with 'runas'
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, params, work_dir, 1
        )

        # ShellExecuteW returns > 32 on success
        if result > 32:
            return True  # Elevation requested, caller should exit
        return False
    except Exception:
        return False


# =============================================================================
# Console Cleanup (ensures no orphan console windows)
# =============================================================================

def _cleanup_console():
    """Free console on exit to prevent orphan windows."""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.kernel32.FreeConsole()
    except:
        pass


def _signal_handler(signum, frame):
    """Handle termination signals by cleaning up console."""
    _cleanup_console()
    sys.exit(0)


atexit.register(_cleanup_console)

# Register signal handlers for graceful shutdown
try:
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGBREAK, _signal_handler)  # Windows-specific
except (AttributeError, ValueError):
    pass  # Some signals may not be available

# =============================================================================
# Path Configuration
# =============================================================================

# Set working directory for frozen executable compatibility
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(application_path)
sys.path.append(application_path)

# Import shared utilities (logging, constants, paths, settings)
from utils import (
    base_dir, appdata_dir, SETTINGS_FILE, DEBUG_LOG_FILE,
    MAX_LOG_SIZE, TRAY_ICON_PATH, PROTECTED_PROCESSES, log,
    load_settings as load_settings_dict, save_settings as save_settings_dict,
    create_default_settings as create_default_settings_shared, DEFAULT_SETTINGS
)

# Import platform utilities (admin checks, PawnIO driver)
from platform_utils import (
    is_admin, is_pawnio_installed, run_pawnio_installer,
    clear_pawnio_cache
)

# Additional paths specific to main application
NOTIFICATION_WARNING_DISMISSED_FILE = os.path.join(appdata_dir, 'notification_warning_dismissed')
UI_SCRIPT_PATH = os.path.join(base_dir, 'vapor_settings_ui.py')
STEAM_PATH = r"C:\Program Files (x86)\Steam\steamapps"

from updater import check_for_updates, CURRENT_VERSION


# =============================================================================
# Windows Notification Check
# =============================================================================

def are_windows_notifications_enabled():
    """
    Check if Windows notifications are enabled and not blocked by Do Not Disturb.
    Returns tuple: (notifications_enabled, reason_string)
    """
    try:
        # Check 1: Main notification toggle
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
            value, _ = winreg.QueryValueEx(key, "ToastEnabled")
            winreg.CloseKey(key)
            if value == 0:
                return False, "notifications_disabled"
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Check 2: Newer notification settings path
        try:
            key_path2 = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path2)
            try:
                value, _ = winreg.QueryValueEx(key, "NOC_GLOBAL_SETTING_TOASTS_ENABLED")
                if value == 0:
                    winreg.CloseKey(key)
                    return False, "notifications_disabled"
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Check 3: Windows 11 Do Not Disturb via CloudStore
        # The data contains the profile name as UTF-16LE after a binary header
        # We search for the byte patterns directly:
        # - b'U\x00n\x00r\x00e\x00s\x00t\x00r\x00i\x00c\x00t\x00e\x00d' = Unrestricted (DND OFF)
        # - b'P\x00r\x00i\x00o\x00r\x00i\x00t\x00y\x00O\x00n\x00l\x00y' = PriorityOnly (DND ON)
        # - b'A\x00l\x00a\x00r\x00m\x00s\x00O\x00n\x00l\x00y' = AlarmsOnly (DND ON)
        try:
            base_path = r"Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base_path)

            # Find the quiethourssettings key (has GUID prefix)
            i = 0
            settings_key_name = None
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    if 'quiethourssettings' in subkey_name.lower() and 'profile' not in subkey_name.lower():
                        settings_key_name = subkey_name
                        break
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)

            if settings_key_name:
                # Read the nested subkey with the actual Data
                full_path = f"{base_path}\\{settings_key_name}\\windows.data.donotdisturb.quiethourssettings"
                try:
                    dnd_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, full_path)
                    data, _ = winreg.QueryValueEx(dnd_key, "Data")
                    winreg.CloseKey(dnd_key)

                    # Search for profile name patterns in the raw bytes
                    # UTF-16LE encoding means each ASCII char is followed by \x00
                    if b'U\x00n\x00r\x00e\x00s\x00t\x00r\x00i\x00c\x00t\x00e\x00d' in data:
                        # DND is OFF - notifications are enabled
                        pass
                    elif b'P\x00r\x00i\x00o\x00r\x00i\x00t\x00y\x00O\x00n\x00l\x00y' in data:
                        return False, "do_not_disturb"
                    elif b'A\x00l\x00a\x00r\x00m\x00s\x00O\x00n\x00l\x00y' in data:
                        return False, "do_not_disturb"
                except FileNotFoundError:
                    pass
                except Exception:
                    pass
        except FileNotFoundError:
            pass
        except Exception:
            pass

        return True, "enabled"
    except Exception:
        return True, "enabled"


def was_notification_warning_dismissed():
    """Check if user has previously dismissed the notification warning."""
    return os.path.exists(NOTIFICATION_WARNING_DISMISSED_FILE)


def mark_notification_warning_dismissed():
    """Mark that user has dismissed the notification warning."""
    try:
        with open(NOTIFICATION_WARNING_DISMISSED_FILE, 'w') as f:
            f.write('dismissed')
    except Exception:
        pass


def show_notification_warning_popup(reason="notifications_disabled"):
    """
    Show a styled popup warning about Windows notifications being disabled.
    Uses CustomTkinter to match the settings UI style.

    Args:
        reason: Either "notifications_disabled" or "do_not_disturb"
    """
    import customtkinter as ctk

    # Create popup window
    popup = ctk.CTk()

    # Register popup for cleanup on quit
    register_popup(popup)

    def on_close():
        unregister_popup(popup)
        popup.destroy()

    popup.protocol("WM_DELETE_WINDOW", on_close)

    if reason == "do_not_disturb":
        popup.title("Vapor - Do Not Disturb Enabled")
        title_text = "Do Not Disturb is Enabled"
        message_text = """Vapor uses Windows notifications to keep you informed about:

  *  When Vapor starts monitoring your games
  *  Playtime summaries after gaming sessions
  *  App updates and other important messages

Windows "Do Not Disturb" (Focus) mode is currently on, so you 
won't see these messages. Vapor will still function normally.

To see Vapor notifications, either:
  *  Turn off Do Not Disturb in the system tray
  *  Add Vapor to your priority notifications list"""
    else:
        popup.title("Vapor - Notifications Disabled")
        title_text = "Windows Notifications Disabled"
        message_text = """Vapor uses Windows notifications to keep you informed about:

  *  When Vapor starts monitoring your games
  *  Playtime summaries after gaming sessions
  *  App updates and other important messages

Your Windows notifications appear to be turned off, so you 
won't see these messages. Vapor will still function normally.

To enable notifications, go to:
Windows Settings > System > Notifications"""

    popup.geometry("500x340")
    popup.resizable(False, False)

    # Center on screen
    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()
    x = (screen_width - 500) // 2
    y = (screen_height - 340) // 2
    popup.geometry(f"500x340+{x}+{y}")

    # Set window icon
    icon_path = os.path.join(base_dir, 'Images', 'exe_icon.ico')
    if os.path.exists(icon_path):
        try:
            popup.iconbitmap(icon_path)
        except Exception:
            pass

    # Title
    title_label = ctk.CTkLabel(
        master=popup,
        text=title_text,
        font=("Calibri", 20, "bold")
    )
    title_label.pack(pady=(25, 15))

    # Message
    message_label = ctk.CTkLabel(
        master=popup,
        text=message_text,
        font=("Calibri", 12),
        justify="left",
        wraplength=450
    )
    message_label.pack(pady=(0, 20), padx=25)

    # Button frame
    button_frame = ctk.CTkFrame(master=popup, fg_color="transparent")
    button_frame.pack(pady=(0, 25))

    def on_ok():
        unregister_popup(popup)
        popup.destroy()

    def on_dont_show_again():
        mark_notification_warning_dismissed()
        unregister_popup(popup)
        popup.destroy()

    ok_button = ctk.CTkButton(
        master=button_frame,
        text="OK",
        command=on_ok,
        width=120,
        height=35,
        corner_radius=10,
        fg_color="green",
        hover_color="#228B22",
        font=("Calibri", 14)
    )
    ok_button.pack(side="left", padx=10)

    dont_show_button = ctk.CTkButton(
        master=button_frame,
        text="Don't Show Again",
        command=on_dont_show_again,
        width=150,
        height=35,
        corner_radius=10,
        fg_color="gray",
        hover_color="#555555",
        font=("Calibri", 14)
    )
    dont_show_button.pack(side="left", padx=10)

    popup.mainloop()


def check_and_warn_notifications():
    """
    Check if Windows notifications are disabled and show warning if needed.
    Only shows warning once unless user clicks OK (vs Don't Show Again).
    """
    if was_notification_warning_dismissed():
        log("Notification warning previously dismissed - skipping check", "INIT")
        return

    enabled, reason = are_windows_notifications_enabled()
    if not enabled:
        log(f"Windows notifications blocked (reason: {reason}) - showing warning", "INIT")
        show_notification_warning_popup(reason)
    else:
        log("Windows notifications are enabled", "INIT")


# =============================================================================
# Console Visibility Control
# =============================================================================

def set_console_visibility(visible):
    """Show or hide the debug console window."""
    try:
        kernel32 = ctypes.windll.kernel32

        if visible:
            # Allocate a new console window
            kernel32.AllocConsole()

            # Redirect stdout/stderr to the new console
            sys.stdout = open('CONOUT$', 'w')
            sys.stderr = open('CONOUT$', 'w')

            # Set console title
            kernel32.SetConsoleTitleW("Vapor Debug Console")

            # Center the console window
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                screen_width = ctypes.windll.user32.GetSystemMetrics(0)
                screen_height = ctypes.windll.user32.GetSystemMetrics(1)

                rect = ctypes.wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                console_width = rect.right - rect.left
                console_height = rect.bottom - rect.top

                x = (screen_width - console_width) // 2
                y = (screen_height - console_height) // 2

                ctypes.windll.user32.SetWindowPos(hwnd, None, x, y, 0, 0, 0x0001)

            log("Debug console opened", "DEBUG")
        else:
            # Check if there's a console to free
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                # Redirect stdout/stderr to null device before freeing console
                # This prevents errors when trying to write after console is freed
                sys.stdout = open(os.devnull, 'w')
                sys.stderr = open(os.devnull, 'w')

                # Free the console
                kernel32.FreeConsole()
    except Exception as e:
        # Can't log here if console is being freed
        pass


# =============================================================================
# Settings Management
# =============================================================================

def create_default_settings():
    """Create default settings file on first run. Uses shared settings module."""
    create_default_settings_shared()


def load_process_names_and_startup():
    """
    Load all settings from JSON file and return as tuple.

    Uses the shared load_settings() function internally but maintains
    the tuple return format for backward compatibility.
    """
    settings = load_settings_dict()

    # Extract all settings with appropriate defaults
    return (
        settings.get('notification_processes', DEFAULT_SETTINGS['notification_processes']),
        settings.get('resource_processes', DEFAULT_SETTINGS['resource_processes']),
        settings.get('launch_at_startup', DEFAULT_SETTINGS['launch_at_startup']),
        settings.get('launch_settings_on_start', DEFAULT_SETTINGS['launch_settings_on_start']),
        settings.get('close_on_startup', DEFAULT_SETTINGS['close_on_startup']),
        settings.get('resource_close_on_startup', DEFAULT_SETTINGS['resource_close_on_startup']),
        settings.get('close_on_hotkey', DEFAULT_SETTINGS['close_on_hotkey']),
        settings.get('resource_close_on_hotkey', DEFAULT_SETTINGS['resource_close_on_hotkey']),
        settings.get('relaunch_on_exit', DEFAULT_SETTINGS['relaunch_on_exit']),
        settings.get('resource_relaunch_on_exit', DEFAULT_SETTINGS['resource_relaunch_on_exit']),
        settings.get('enable_playtime_summary', DEFAULT_SETTINGS['enable_playtime_summary']),
        settings.get('playtime_summary_mode', DEFAULT_SETTINGS['playtime_summary_mode']),
        settings.get('enable_system_audio', DEFAULT_SETTINGS['enable_system_audio']),
        settings.get('system_audio_level', DEFAULT_SETTINGS['system_audio_level']),
        settings.get('enable_game_audio', DEFAULT_SETTINGS['enable_game_audio']),
        settings.get('game_audio_level', DEFAULT_SETTINGS['game_audio_level']),
        settings.get('enable_during_power', DEFAULT_SETTINGS['enable_during_power']),
        settings.get('during_power_plan', DEFAULT_SETTINGS['during_power_plan']),
        settings.get('enable_after_power', DEFAULT_SETTINGS['enable_after_power']),
        settings.get('after_power_plan', DEFAULT_SETTINGS['after_power_plan']),
        settings.get('enable_game_mode_start', DEFAULT_SETTINGS['enable_game_mode_start']),
        settings.get('enable_game_mode_end', DEFAULT_SETTINGS['enable_game_mode_end']),
        settings.get('enable_debug_mode', DEFAULT_SETTINGS['enable_debug_mode']),
        settings.get('enable_cpu_thermal', DEFAULT_SETTINGS['enable_cpu_thermal']),
        settings.get('enable_gpu_thermal', DEFAULT_SETTINGS['enable_gpu_thermal']),
        settings.get('enable_cpu_temp_alert', DEFAULT_SETTINGS['enable_cpu_temp_alert']),
        settings.get('cpu_temp_warning_threshold', DEFAULT_SETTINGS['cpu_temp_warning_threshold']),
        settings.get('cpu_temp_critical_threshold', DEFAULT_SETTINGS['cpu_temp_critical_threshold']),
        settings.get('enable_gpu_temp_alert', DEFAULT_SETTINGS['enable_gpu_temp_alert']),
        settings.get('gpu_temp_warning_threshold', DEFAULT_SETTINGS['gpu_temp_warning_threshold']),
        settings.get('gpu_temp_critical_threshold', DEFAULT_SETTINGS['gpu_temp_critical_threshold']),
    )


# =============================================================================
# Windows Startup Registry
# =============================================================================

def set_startup(enabled):
    """Add or remove Vapor from Windows startup via registry."""
    key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
    app_name = 'Vapor'
    log(f"Setting startup registry: enabled={enabled}", "STARTUP")

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)

        if enabled:
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(__file__)

            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            log(f"Added to startup: {exe_path}", "STARTUP")
        else:
            try:
                winreg.DeleteValue(key, app_name)
                log("Removed from startup", "STARTUP")
            except FileNotFoundError:
                log("Not in startup - no change needed", "STARTUP")
        winreg.CloseKey(key)
    except Exception as e:
        log(f"Startup registry error: {e}", "ERROR")


# =============================================================================
# Steam Integration
# =============================================================================

def get_running_steam_app_id():
    """Get the AppID of currently running Steam game (0 if none)."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        app_id, _ = winreg.QueryValueEx(key, "RunningAppID")
        winreg.CloseKey(key)
        return int(app_id)
    except:
        return 0


def get_game_name(app_id):
    """Fetch game name from Steam API for given AppID."""
    if app_id == 0:
        return "No game running"
    log(f"Fetching game name for AppID {app_id} from Steam API...", "STEAM")
    try:
        url = f"http://store.steampowered.com/api/appdetails?appids={app_id}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if response.status_code == 200 and str(app_id) in data and data[str(app_id)]["success"]:
            name = data[str(app_id)]["data"]["name"]
            log(f"Game name resolved: {name}", "STEAM")
            return name
    except Exception as e:
        log(f"Failed to fetch game name: {e}", "ERROR")
    return "Unknown"


def get_game_header_image(app_id):
    """Fetch game header image URL from Steam API for given AppID."""
    if app_id == 0:
        return None
    try:
        url = f"http://store.steampowered.com/api/appdetails?appids={app_id}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if response.status_code == 200 and str(app_id) in data and data[str(app_id)]["success"]:
            header_image = data[str(app_id)]["data"].get("header_image")
            if header_image:
                log(f"Got header image URL for AppID {app_id}", "STEAM")
                return header_image
    except Exception as e:
        log(f"Failed to fetch game header image: {e}", "ERROR")
    return None


def get_game_store_details(app_id):
    """Fetch game details from Steam Store API.

    Returns dict with: developers, publishers, release_date, metacritic_score, metacritic_url
    """
    if app_id == 0:
        return None
    try:
        url = f"http://store.steampowered.com/api/appdetails?appids={app_id}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if response.status_code == 200 and str(app_id) in data and data[str(app_id)]["success"]:
            game_data = data[str(app_id)]["data"]

            details = {
                'developers': game_data.get('developers', []),
                'publishers': game_data.get('publishers', []),
                'release_date': game_data.get('release_date', {}).get('date', 'Unknown'),
                'metacritic_score': None,
                'metacritic_url': None
            }

            # Metacritic data (may not exist for all games)
            metacritic = game_data.get('metacritic')
            if metacritic:
                details['metacritic_score'] = metacritic.get('score')
                details['metacritic_url'] = metacritic.get('url')

            log(f"Got store details for AppID {app_id}", "STEAM")
            return details
    except Exception as e:
        log(f"Failed to fetch game store details: {e}", "ERROR")
    return None


# Pre-loaded game details for instant popup display
_preloaded_game_details = None
_preloaded_game_details_lock = threading.Lock()


def preload_game_details(app_id):
    """Pre-load game details from Steam Store API for instant display."""
    global _preloaded_game_details

    if app_id == 0:
        return

    details = get_game_store_details(app_id)
    if details:
        with _preloaded_game_details_lock:
            _preloaded_game_details = details
        log(f"Pre-loaded game details for AppID {app_id}", "CACHE")


def get_preloaded_game_details():
    """Get the pre-loaded game details (or None if not available)."""
    global _preloaded_game_details
    with _preloaded_game_details_lock:
        details = _preloaded_game_details
        _preloaded_game_details = None  # Clear after use
        return details


# Directory for cached game header images
HEADER_IMAGE_CACHE_DIR = os.path.join(appdata_dir, 'images')
os.makedirs(HEADER_IMAGE_CACHE_DIR, exist_ok=True)


def get_cached_header_image_path(app_id):
    """Get the path to the cached header image for a game."""
    return os.path.join(HEADER_IMAGE_CACHE_DIR, f"{app_id}.jpg")


def cache_game_header_image(app_id):
    """Download and cache the game header image for later use.

    Should be called when a game starts so the image is ready when the game ends.
    Runs in the background to avoid blocking.
    """
    if app_id == 0:
        return

    cache_path = get_cached_header_image_path(app_id)

    # Skip if already cached
    if os.path.exists(cache_path):
        log(f"Header image already cached for AppID {app_id}", "CACHE")
        return

    try:
        # Get the image URL from Steam API
        header_image_url = get_game_header_image(app_id)
        if not header_image_url:
            return

        # Download the image
        response = requests.get(header_image_url, timeout=10)
        if response.status_code == 200:
            # Save to cache
            with open(cache_path, 'wb') as f:
                f.write(response.content)
            log(f"Cached header image for AppID {app_id}", "CACHE")
    except Exception as e:
        log(f"Failed to cache header image for AppID {app_id}: {e}", "ERROR")


# Pre-loaded image for instant popup display
_preloaded_header_image = None
_preloaded_header_image_lock = threading.Lock()


def preload_header_image(app_id):
    """Pre-load and resize the header image into memory for instant display.

    Should be called after cache_game_header_image() completes.
    """
    global _preloaded_header_image
    from PIL import Image

    if app_id == 0:
        return

    cache_path = get_cached_header_image_path(app_id)
    if not os.path.exists(cache_path):
        return

    try:
        pil_image = Image.open(cache_path)
        # Pre-resize to the exact size needed for the popup
        aspect_ratio = pil_image.height / pil_image.width
        new_width = 400
        new_height = int(new_width * aspect_ratio)
        pil_image = pil_image.resize((new_width, new_height), Image.LANCZOS)

        with _preloaded_header_image_lock:
            _preloaded_header_image = pil_image
        log(f"Pre-loaded header image for AppID {app_id}", "CACHE")
    except Exception as e:
        log(f"Failed to pre-load header image: {e}", "ERROR")


def get_preloaded_header_image():
    """Get the pre-loaded header image (or None if not available)."""
    global _preloaded_header_image
    with _preloaded_header_image_lock:
        img = _preloaded_header_image
        _preloaded_header_image = None  # Clear after use
        return img


def warmup_customtkinter():
    """Pre-initialize CustomTkinter by creating and destroying a hidden window.

    This loads themes, fonts, etc. so the actual popup appears faster.
    """
    try:
        import customtkinter as ctk
        # Create a tiny hidden window to trigger CTk initialization
        root = ctk.CTk()
        root.withdraw()  # Hide immediately
        root.update()    # Process initialization
        root.destroy()   # Clean up
        log("CustomTkinter pre-initialized", "CACHE")
    except Exception as e:
        log(f"Failed to pre-initialize CustomTkinter: {e}", "ERROR")


def prepare_session_popup(app_id):
    """Background task to prepare everything needed for the session popup.

    Called when a game starts. Downloads/caches image, pre-loads it into memory,
    fetches game details from Steam, and warms up CustomTkinter so the popup
    appears instantly when the game ends.
    """
    cache_game_header_image(app_id)
    preload_header_image(app_id)
    preload_game_details(app_id)
    warmup_customtkinter()


# =============================================================================
# Process Management
# =============================================================================

def kill_processes(process_names, killed_processes, purpose=""):
    """
    Terminate processes from the given list.
    Stores process info in killed_processes dict for potential relaunch.
    """
    purpose_str = f" ({purpose})" if purpose else ""
    log(f"Attempting to close {len(process_names)} {purpose} process type(s)...", "PROCESS")
    for name in process_names:
        # Skip protected system processes
        if name.lower() in PROTECTED_PROCESSES:
            log(f"Skipping protected process: {name}", "PROCESS")
            continue

        killed_count = 0
        path_to_store = None
        for proc in psutil.process_iter(['name', 'exe']):
            if proc.info['name'].lower() == name.lower():
                try:
                    path = proc.info['exe']
                    if path and os.path.exists(path):
                        log(f"Terminating{purpose_str}: {name} (PID: {proc.pid})", "PROCESS")
                        proc.terminate()
                        proc.wait(timeout=5)
                        killed_count += 1
                        if path_to_store is None:
                            path_to_store = path
                except psutil.TimeoutExpired:
                    log(f"Timeout waiting for {name} - force killing", "PROCESS")
                    proc.kill()
                except Exception as e:
                    log(f"Error closing {name}: {e}", "ERROR")

        if killed_count > 0:
            killed_processes[name] = path_to_store
            log(f"Closed {killed_count} instance(s) of {name}{purpose_str}", "PROCESS")


def relaunch_processes(killed_processes, relaunch_on_exit, purpose=""):
    """Relaunch previously terminated processes (minimized)."""
    purpose_str = f" ({purpose})" if purpose else ""
    if not relaunch_on_exit:
        log(f"Relaunch disabled for {purpose} apps - skipping", "RELAUNCH")
        return

    log(f"Relaunching {len(killed_processes)} {purpose} process(es)...", "RELAUNCH")
    for name, path in list(killed_processes.items()):
        is_running = any(p.info['name'].lower() == name.lower() for p in psutil.process_iter(['name']))
        if is_running:
            log(f"{name} already running - skipping", "RELAUNCH")
            killed_processes.pop(name, None)
            continue
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = win32con.SW_SHOWMINIMIZED
            subprocess.Popen(path, startupinfo=startupinfo)
            log(f"Relaunched {name}{purpose_str} (minimized)", "RELAUNCH")
            killed_processes.pop(name, None)
        except Exception as e:
            log(f"Failed to relaunch {name}: {e}", "ERROR")


# =============================================================================
# Notifications
# =============================================================================

def show_notification(message):
    """Display a Windows toast notification."""
    log(f"Showing notification: {message}", "NOTIFY")
    icon_path = os.path.abspath(TRAY_ICON_PATH)
    win11toast.notify(body=message, app_id='Vapor - Streamline Gaming', duration='short', icon=icon_path,
                      audio={'silent': 'true'})


def show_brief_summary(session_data):
    """Display a brief toast notification with session summary."""
    hours = session_data['hours']
    minutes = session_data['minutes']
    game_name = session_data['game_name']
    closed_apps_count = session_data['closed_apps_count']
    max_cpu_temp = session_data.get('max_cpu_temp')
    max_gpu_temp = session_data.get('max_gpu_temp')

    # Build playtime string
    if hours == 0:
        playtime_str = f"{minutes} minutes"
    elif hours == 1:
        playtime_str = f"{hours} hour and {minutes} minutes"
    else:
        playtime_str = f"{hours} hours and {minutes} minutes"

    # Build temperature string
    temp_parts = []
    if max_cpu_temp is not None:
        temp_parts.append(f"CPU: {max_cpu_temp}°C")
    if max_gpu_temp is not None:
        temp_parts.append(f"GPU: {max_gpu_temp}°C")

    if temp_parts:
        temp_str = f" Max temps: {', '.join(temp_parts)}."
        log(f"Max temperatures - {', '.join(temp_parts)}", "GAME")
    else:
        temp_str = ""

    message = f"You played {game_name} for {playtime_str}. Vapor closed {closed_apps_count} apps when you started.{temp_str}"
    show_notification(message)


def show_detailed_summary(session_data):
    """Display a detailed popup window with session statistics."""
    import customtkinter as ctk
    from PIL import Image
    from io import BytesIO

    app_id = session_data.get('app_id', 0)
    game_name = session_data['game_name']
    hours = session_data['hours']
    minutes = session_data['minutes']
    seconds = session_data['seconds']
    closed_apps_count = session_data['closed_apps_count']
    closed_apps_list = session_data.get('closed_apps_list', [])
    start_cpu_temp = session_data.get('start_cpu_temp')
    start_gpu_temp = session_data.get('start_gpu_temp')
    max_cpu_temp = session_data.get('max_cpu_temp')
    max_gpu_temp = session_data.get('max_gpu_temp')
    lifetime_max_cpu = session_data.get('lifetime_max_cpu')
    lifetime_max_gpu = session_data.get('lifetime_max_gpu')

    # Run popup in a separate thread to avoid blocking
    def show_popup():
        # Get pre-loaded game details (developer, metacritic, etc.)
        game_details = get_preloaded_game_details()

        popup = ctk.CTk()
        popup.title("Vapor - Game Session Details")

        # Register popup for cleanup on quit
        register_popup(popup)

        def on_close():
            unregister_popup(popup)
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", on_close)

        # Window dimensions - similar to settings window, use screen-based height
        window_width = 550
        screen_height = popup.winfo_screenheight()
        # Use 70% of screen height, clamped between 600 and 850
        window_height = int(screen_height * 0.70)
        window_height = max(600, min(window_height, 850))

        popup.geometry(f"{window_width}x{window_height}")
        popup.resizable(False, False)

        # Center on screen
        screen_width = popup.winfo_screenwidth()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        popup.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Set window icon
        icon_path = os.path.join(base_dir, 'Images', 'exe_icon.ico')
        if os.path.exists(icon_path):
            try:
                popup.iconbitmap(icon_path)
            except Exception:
                pass

        # IMPORTANT: Pack bottom bar FIRST so it reserves space at the bottom
        bottom_bar = ctk.CTkFrame(master=popup, fg_color="transparent")
        bottom_bar.pack(side="bottom", fill="x")

        # Separator above button bar
        sep_bottom = ctk.CTkFrame(master=bottom_bar, height=2, fg_color="gray50")
        sep_bottom.pack(fill="x", padx=40, pady=(10, 0))

        # Button container
        button_container = ctk.CTkFrame(master=bottom_bar, fg_color="transparent")
        button_container.pack(pady=15)

        ok_button = ctk.CTkButton(
            master=button_container,
            text="OK",
            command=on_close,
            width=150,
            height=35,
            corner_radius=10,
            fg_color="green",
            hover_color="#228B22",
            font=("Calibri", 15)
        )
        ok_button.pack()

        # Content frame (fills remaining space above bottom bar)
        content_frame = ctk.CTkFrame(master=popup, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=15, pady=(20, 10))

        # Title
        title_label = ctk.CTkLabel(
            master=content_frame,
            text="Game Session Details",
            font=("Calibri", 22, "bold")
        )
        title_label.pack(pady=(0, 5))

        # Game name
        game_label = ctk.CTkLabel(
            master=content_frame,
            text=game_name,
            font=("Calibri", 17),
            text_color="gray70"
        )
        game_label.pack(pady=(0, 10))

        # Game header image (try pre-loaded first, fall back to cache)
        pil_image = get_preloaded_header_image()
        if pil_image is None and app_id:
            # Fallback: load from cache if pre-loaded image not available
            cached_image_path = get_cached_header_image_path(app_id)
            if cached_image_path and os.path.exists(cached_image_path):
                try:
                    pil_image = Image.open(cached_image_path)
                    aspect_ratio = pil_image.height / pil_image.width
                    new_width = 400
                    new_height = int(new_width * aspect_ratio)
                    pil_image = pil_image.resize((new_width, new_height), Image.LANCZOS)
                except Exception as e:
                    log(f"Failed to load cached game header image: {e}", "NOTIFY")
                    pil_image = None

        if pil_image is not None:
            try:
                new_width = pil_image.width
                new_height = pil_image.height
                ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image,
                                         size=(new_width, new_height))
                image_label = ctk.CTkLabel(master=content_frame, image=ctk_image, text="")
                image_label.image = ctk_image  # Keep reference to prevent garbage collection
                image_label.pack(pady=(5, 10))
            except Exception as e:
                log(f"Failed to display game header image: {e}", "NOTIFY")

        # Separator
        sep1 = ctk.CTkFrame(master=content_frame, height=2, fg_color="gray50")
        sep1.pack(fill="x", padx=20, pady=5)

        # Stats frame using grid for alignment
        stats_frame = ctk.CTkFrame(master=content_frame, fg_color="transparent")
        stats_frame.pack(pady=10, padx=20, fill="x")

        # Time Played
        ctk.CTkLabel(master=stats_frame, text="Time Played:", font=("Calibri", 14, "bold"),
                     anchor="w").grid(row=0, column=0, sticky="w", pady=3)
        time_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
        ctk.CTkLabel(master=stats_frame, text=time_str, font=("Calibri", 14),
                     anchor="e").grid(row=0, column=1, sticky="e", pady=3)

        # Apps Closed
        ctk.CTkLabel(master=stats_frame, text="Apps Closed:", font=("Calibri", 14, "bold"),
                     anchor="w").grid(row=1, column=0, sticky="w", pady=3)
        ctk.CTkLabel(master=stats_frame, text=str(closed_apps_count), font=("Calibri", 14),
                     anchor="e").grid(row=1, column=1, sticky="e", pady=3)

        stats_frame.grid_columnconfigure(1, weight=1)

        # Show closed apps list if any
        if closed_apps_list:
            apps_list_frame = ctk.CTkFrame(master=content_frame, fg_color="transparent")
            apps_list_frame.pack(pady=(0, 5), padx=40, fill="x")

            # Format app names nicely (remove .exe extension)
            app_names = [app.replace('.exe', '').replace('.EXE', '') for app in closed_apps_list]
            apps_text = ", ".join(app_names[:8])  # Limit to first 8 apps
            if len(app_names) > 8:
                apps_text += f" (+{len(app_names) - 8} more)"

            apps_list_label = ctk.CTkLabel(
                master=apps_list_frame,
                text=apps_text,
                font=("Calibri", 12),
                text_color="gray60",
                wraplength=400
            )
            apps_list_label.pack(anchor="w")

        # Game Info section (from Steam Store API)
        if game_details:
            # Separator before game info
            sep_info = ctk.CTkFrame(master=content_frame, height=2, fg_color="gray50")
            sep_info.pack(fill="x", padx=20, pady=5)

            info_frame = ctk.CTkFrame(master=content_frame, fg_color="transparent")
            info_frame.pack(pady=5, padx=20, fill="x")

            info_row = 0

            # Developer
            developers = game_details.get('developers', [])
            if developers:
                ctk.CTkLabel(master=info_frame, text="Developer:", font=("Calibri", 14, "bold"),
                             anchor="w").grid(row=info_row, column=0, sticky="w", pady=2)
                ctk.CTkLabel(master=info_frame, text=", ".join(developers[:2]), font=("Calibri", 14),
                             anchor="e").grid(row=info_row, column=1, sticky="e", pady=2)
                info_row += 1

            # Publisher (only if different from developer)
            publishers = game_details.get('publishers', [])
            if publishers and publishers != developers:
                ctk.CTkLabel(master=info_frame, text="Publisher:", font=("Calibri", 14, "bold"),
                             anchor="w").grid(row=info_row, column=0, sticky="w", pady=2)
                ctk.CTkLabel(master=info_frame, text=", ".join(publishers[:2]), font=("Calibri", 14),
                             anchor="e").grid(row=info_row, column=1, sticky="e", pady=2)
                info_row += 1

            # Release Date
            release_date = game_details.get('release_date')
            if release_date and release_date != 'Unknown':
                ctk.CTkLabel(master=info_frame, text="Released:", font=("Calibri", 14, "bold"),
                             anchor="w").grid(row=info_row, column=0, sticky="w", pady=2)
                ctk.CTkLabel(master=info_frame, text=release_date, font=("Calibri", 14),
                             anchor="e").grid(row=info_row, column=1, sticky="e", pady=2)
                info_row += 1

            # Metacritic Score
            metacritic_score = game_details.get('metacritic_score')
            if metacritic_score:
                ctk.CTkLabel(master=info_frame, text="Metacritic:", font=("Calibri", 14, "bold"),
                             anchor="w").grid(row=info_row, column=0, sticky="w", pady=2)
                # Color code the score
                if metacritic_score >= 75:
                    score_color = "#66CC33"  # Green
                elif metacritic_score >= 50:
                    score_color = "#FFCC33"  # Yellow
                else:
                    score_color = "#FF0000"  # Red
                ctk.CTkLabel(master=info_frame, text=str(metacritic_score), font=("Calibri", 14, "bold"),
                             text_color=score_color, anchor="e").grid(row=info_row, column=1, sticky="e", pady=2)
                info_row += 1

            info_frame.grid_columnconfigure(1, weight=1)

        # Separator
        sep2 = ctk.CTkFrame(master=content_frame, height=2, fg_color="gray50")
        sep2.pack(fill="x", padx=20, pady=5)

        # Temperature section
        temp_title = ctk.CTkLabel(
            master=content_frame,
            text="Temperatures",
            font=("Calibri", 15, "bold")
        )
        temp_title.pack(pady=(5, 3))

        # Subtitle explaining lifetime max
        temp_subtitle = ctk.CTkLabel(
            master=content_frame,
            text=f"Lifetime Max = highest recorded temperature for {game_name}",
            font=("Calibri", 12),
            text_color="gray50"
        )
        temp_subtitle.pack(pady=(0, 8))

        temp_frame = ctk.CTkFrame(master=content_frame, fg_color="transparent")
        temp_frame.pack(pady=5, padx=20, fill="x")

        has_temps = False

        # Column headers - changed "Lifetime" to "Lifetime Max"
        ctk.CTkLabel(master=temp_frame, text="", font=("Calibri", 12),
                     anchor="w").grid(row=0, column=0, sticky="w", pady=3)
        ctk.CTkLabel(master=temp_frame, text="Start", font=("Calibri", 12, "bold"),
                     text_color="gray60").grid(row=0, column=1, sticky="e", pady=3, padx=(15, 0))
        ctk.CTkLabel(master=temp_frame, text="Session Max", font=("Calibri", 12, "bold"),
                     text_color="gray60").grid(row=0, column=2, sticky="e", pady=3, padx=(15, 0))
        ctk.CTkLabel(master=temp_frame, text="Lifetime Max", font=("Calibri", 12, "bold"),
                     text_color="#FFD700").grid(row=0, column=3, sticky="e", pady=3, padx=(15, 0))

        # CPU temps
        if start_cpu_temp is not None or max_cpu_temp is not None or lifetime_max_cpu is not None:
            has_temps = True
            ctk.CTkLabel(master=temp_frame, text="CPU:", font=("Calibri", 14, "bold"),
                         anchor="w").grid(row=1, column=0, sticky="w", pady=3)

            start_text = f"{start_cpu_temp}°C" if start_cpu_temp is not None else "N/A"
            max_text = f"{max_cpu_temp}°C" if max_cpu_temp is not None else "N/A"
            lifetime_text = f"{lifetime_max_cpu}°C" if lifetime_max_cpu is not None else "N/A"

            ctk.CTkLabel(master=temp_frame, text=start_text,
                         font=("Calibri", 13)).grid(row=1, column=1, sticky="e", pady=3, padx=(15, 0))
            ctk.CTkLabel(master=temp_frame, text=max_text,
                         font=("Calibri", 13)).grid(row=1, column=2, sticky="e", pady=3, padx=(15, 0))
            ctk.CTkLabel(master=temp_frame, text=lifetime_text,
                         font=("Calibri", 13), text_color="#FFD700").grid(row=1, column=3, sticky="e", pady=3, padx=(15, 0))

        # GPU temps
        if start_gpu_temp is not None or max_gpu_temp is not None or lifetime_max_gpu is not None:
            has_temps = True
            row = 2 if (start_cpu_temp is not None or max_cpu_temp is not None or lifetime_max_cpu is not None) else 1
            ctk.CTkLabel(master=temp_frame, text="GPU:", font=("Calibri", 14, "bold"),
                         anchor="w").grid(row=row, column=0, sticky="w", pady=3)

            start_text = f"{start_gpu_temp}°C" if start_gpu_temp is not None else "N/A"
            max_text = f"{max_gpu_temp}°C" if max_gpu_temp is not None else "N/A"
            lifetime_text = f"{lifetime_max_gpu}°C" if lifetime_max_gpu is not None else "N/A"

            ctk.CTkLabel(master=temp_frame, text=start_text,
                         font=("Calibri", 13)).grid(row=row, column=1, sticky="e", pady=3, padx=(15, 0))
            ctk.CTkLabel(master=temp_frame, text=max_text,
                         font=("Calibri", 13)).grid(row=row, column=2, sticky="e", pady=3, padx=(15, 0))
            ctk.CTkLabel(master=temp_frame, text=lifetime_text,
                         font=("Calibri", 13), text_color="#FFD700").grid(row=row, column=3, sticky="e", pady=3, padx=(15, 0))

        # No temps available message
        if not has_temps:
            ctk.CTkLabel(
                master=temp_frame,
                text="Temperature monitoring not enabled",
                font=("Calibri", 13),
                text_color="gray60"
            ).grid(row=0, column=0, columnspan=4, pady=10)

        temp_frame.grid_columnconfigure(3, weight=1)

        popup.mainloop()

    # Run in a thread to avoid blocking the main monitoring loop
    threading.Thread(target=show_popup, daemon=True).start()
    log(f"Showing detailed summary for {game_name}", "NOTIFY")


# =============================================================================
# Power Management
# =============================================================================

def get_power_plan_guid(plan_name):
    """Map power plan name to Windows GUID."""
    plan_map = {
        'Balanced': '381b4222-f694-41f0-9685-ff5bb260df2e',
        'High Performance': '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c',
        'Power saver': 'a1841308-3541-4fab-bc81-f71556f20b4a'
    }
    return plan_map.get(plan_name)


def set_power_plan(plan_name):
    """Activate a Windows power plan by name."""
    log(f"Setting power plan to: {plan_name}", "POWER")
    guid = get_power_plan_guid(plan_name)
    if guid:
        try:
            # Use CREATE_NO_WINDOW to prevent black console box from appearing
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            subprocess.run(['powercfg', '/setactive', guid], check=True,
                           startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW)
            log(f"Power plan set to {plan_name}", "POWER")
        except Exception as e:
            log(f"Failed to set power plan: {e}", "ERROR")
    else:
        log(f"Unknown power plan: {plan_name}", "ERROR")


# =============================================================================
# Windows Game Mode
# =============================================================================

def set_game_mode(enabled):
    """Enable or disable Windows Game Mode via registry."""
    log(f"Setting Windows Game Mode to: {'Enabled' if enabled else 'Disabled'}", "GAMEMODE")
    try:
        key_path = r"Software\Microsoft\GameBar"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        winreg.SetValueEx(key, "AutoGameModeEnabled", 0, winreg.REG_DWORD, 1 if enabled else 0)
        winreg.CloseKey(key)
        log(f"Windows Game Mode {'enabled' if enabled else 'disabled'}", "GAMEMODE")
    except FileNotFoundError:
        # Key doesn't exist, try to create it
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            winreg.SetValueEx(key, "AutoGameModeEnabled", 0, winreg.REG_DWORD, 1 if enabled else 0)
            winreg.CloseKey(key)
            log(f"Windows Game Mode {'enabled' if enabled else 'disabled'} (created key)", "GAMEMODE")
        except Exception as e:
            log(f"Failed to create Game Mode registry key: {e}", "ERROR")
    except Exception as e:
        log(f"Failed to set Game Mode: {e}", "ERROR")


# Track open popup windows for cleanup on quit
_open_popups = []
_open_popups_lock = threading.Lock()


def register_popup(popup):
    """Register a popup window for cleanup on quit."""
    with _open_popups_lock:
        _open_popups.append(popup)


def unregister_popup(popup):
    """Unregister a popup window when it's closed."""
    with _open_popups_lock:
        if popup in _open_popups:
            _open_popups.remove(popup)


def close_all_popups():
    """Close all registered popup windows."""
    with _open_popups_lock:
        for popup in _open_popups[:]:  # Copy list to avoid modification during iteration
            try:
                popup.after(0, popup.destroy)
            except Exception:
                pass
        _open_popups.clear()


# =============================================================================
# Steam Path Detection
# =============================================================================

def get_steam_path():
    """Detect Steam installation path from registry."""
    log("Detecting Steam installation path...", "STEAM")
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        path, _ = winreg.QueryValueEx(key, "SteamPath")
        winreg.CloseKey(key)
        steamapps = os.path.join(path, "steamapps")
        log(f"Steam path detected: {steamapps}", "STEAM")
        return steamapps
    except Exception as e:
        log(f"Failed to auto-detect Steam path: {e} - using default", "STEAM")
        return STEAM_PATH


def get_library_folders():
    """Scan for all Steam library folders (including additional drives)."""
    log("Scanning for Steam library folders...", "STEAM")
    main_steamapps = get_steam_path()
    steam_install_dir = os.path.dirname(main_steamapps)
    vdf_paths = [
        os.path.join(steam_install_dir, 'steamapps', 'libraryfolders.vdf'),
        os.path.join(steam_install_dir, 'config', 'libraryfolders.vdf')
    ]

    libraries = set()
    for vdf_path in vdf_paths:
        if os.path.exists(vdf_path):
            log(f"Found VDF: {vdf_path}", "STEAM")
            try:
                with open(vdf_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                paths = re.findall(r'"path"\s+"(.*?)"', content)
                for p in paths:
                    lib_path = p.replace('\\\\', '\\')
                    steamapps = os.path.join(lib_path, 'steamapps')
                    if os.path.exists(steamapps):
                        libraries.add(steamapps)
            except Exception as e:
                log(f"Error parsing VDF: {e}", "ERROR")

    if os.path.exists(main_steamapps):
        libraries.add(main_steamapps)

    libraries = list(libraries)
    log(f"Found {len(libraries)} library folder(s)", "STEAM")
    return libraries


def get_game_folder(app_id):
    """Locate the installation folder for a Steam game by AppID."""
    log(f"Locating game folder for AppID {app_id}...", "STEAM")
    libraries = get_library_folders()
    for lib in libraries:
        manifest_path = os.path.join(lib, f"appmanifest_{app_id}.acf")
        if os.path.exists(manifest_path):
            log(f"Found manifest: {manifest_path}", "STEAM")
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                installdir_match = re.search(r'"installdir"\s+"(.*?)"', content)
                if installdir_match:
                    installdir = installdir_match.group(1).replace('\\\\', '\\')
                    game_folder = os.path.join(lib, "common", installdir)
                    if os.path.exists(game_folder):
                        log(f"Game folder found: {game_folder}", "STEAM")
                        return game_folder
            except Exception as e:
                log(f"Error parsing manifest: {e}", "ERROR")
    log(f"Could not find game folder for AppID {app_id}", "STEAM")
    return None


# =============================================================================
# Settings File Watcher
# =============================================================================

class SettingsFileHandler(FileSystemEventHandler):
    """Watch for settings file changes and trigger reload callback."""

    def __init__(self, callback):
        self.callback = callback

    def on_modified(self, event):
        if event.src_path.endswith(SETTINGS_FILE):
            log("Settings file changed - triggering reload", "SETTINGS")
            self.callback()


# =============================================================================
# Main Game Monitoring Loop
# =============================================================================

def monitor_steam_games(stop_event, killed_notification, killed_resource, is_first_run=False):
    """
    Main monitoring loop that watches for Steam game launches.
    Manages process termination, audio, power plans, and more.
    """
    log("=" * 50, "INIT")
    log(f"Vapor v{CURRENT_VERSION} starting...", "INIT")
    log("=" * 50, "INIT")

    (notification_processes, resource_processes, launch_at_startup, launch_settings_on_start,
     notification_close_on_startup, resource_close_on_startup, notification_close_on_hotkey,
     resource_close_on_hotkey, notification_relaunch_on_exit, resource_relaunch_on_exit,
     enable_playtime_summary, playtime_summary_mode, enable_system_audio, system_audio_level,
     enable_game_audio, game_audio_level, enable_during_power, during_power_plan, enable_after_power,
     after_power_plan, enable_game_mode_start, enable_game_mode_end,
     enable_debug_mode, enable_cpu_thermal, enable_gpu_thermal, enable_cpu_temp_alert,
     cpu_temp_warning_threshold, cpu_temp_critical_threshold, enable_gpu_temp_alert,
     gpu_temp_warning_threshold, gpu_temp_critical_threshold) = load_process_names_and_startup()

    # Set console visibility based on debug mode
    set_console_visibility(enable_debug_mode)

    set_startup(launch_at_startup)

    # Launch settings on start if enabled or if first run
    if is_first_run or launch_settings_on_start:
        log("Launching settings window on startup...", "INIT")
        try:
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable, '--ui', str(os.getpid())])
            else:
                subprocess.Popen([sys.executable, __file__, '--ui', str(os.getpid())])
        except Exception as e:
            log(f"Failed to launch settings: {e}", "ERROR")

    is_hotkey_registered = notification_close_on_hotkey or resource_close_on_hotkey
    if is_hotkey_registered:
        keyboard.add_hotkey('ctrl+alt+k', lambda: (
            kill_processes(notification_processes, killed_notification,
                           "notification") if notification_close_on_hotkey else None,
            kill_processes(resource_processes, killed_resource, "resource") if resource_close_on_hotkey else None
        ))
        log("Hotkey registered: Ctrl+Alt+K", "INIT")

    previous_app_id = get_running_steam_app_id()
    start_time = None
    current_game_name = None

    if previous_app_id != 0:
        game_name = get_game_name(previous_app_id)
        log(f"Game already running at startup: {game_name} (AppID {previous_app_id})", "GAME")
        start_time = time.time()
        current_game_name = game_name
        if notification_close_on_startup:
            kill_processes(notification_processes, killed_notification, "notification")
        if resource_close_on_startup:
            kill_processes(resource_processes, killed_resource, "resource")
        if enable_system_audio:
            set_system_volume(system_audio_level)
        if enable_game_audio:
            game_folder = get_game_folder(previous_app_id)
            game_pids = find_game_pids(game_folder)
            set_game_volume(game_pids, game_audio_level, game_folder, current_game_name)
        if enable_during_power:
            set_power_plan(during_power_plan)
        if enable_game_mode_start:
            set_game_mode(True)
        # Start temperature monitoring for game already in progress
        temperature_tracker.start_monitoring(stop_event, enable_cpu_thermal, enable_gpu_thermal,
                                             enable_cpu_temp_alert, cpu_temp_warning_threshold,
                                             cpu_temp_critical_threshold, enable_gpu_temp_alert,
                                             gpu_temp_warning_threshold, gpu_temp_critical_threshold,
                                             game_name=current_game_name)
        # Pre-cache image, pre-load into memory, and warm up CTk for instant session popup
        threading.Thread(target=prepare_session_popup, args=(previous_app_id,), daemon=True).start()
    else:
        log("No game running at startup", "GAME")

    log("Vapor is now monitoring Steam games", "INIT")
    show_notification("Vapor is now monitoring Steam games")

    def reload_settings():
        nonlocal notification_processes, resource_processes, launch_at_startup, launch_settings_on_start, \
            notification_close_on_startup, resource_close_on_startup, notification_close_on_hotkey, \
            resource_close_on_hotkey, notification_relaunch_on_exit, resource_relaunch_on_exit, \
            enable_playtime_summary, playtime_summary_mode, enable_system_audio, system_audio_level, \
            enable_game_audio, game_audio_level, is_hotkey_registered, enable_during_power, during_power_plan, \
            enable_after_power, after_power_plan, enable_game_mode_start, enable_game_mode_end, enable_debug_mode, \
            enable_cpu_thermal, enable_gpu_thermal, enable_cpu_temp_alert, cpu_temp_warning_threshold, \
            cpu_temp_critical_threshold, enable_gpu_temp_alert, gpu_temp_warning_threshold, gpu_temp_critical_threshold

        log("Reloading settings...", "SETTINGS")
        (new_notification_processes, new_resource_processes, new_startup, new_launch_settings_on_start,
         new_notification_close_startup, new_resource_close_startup, new_notification_close_hotkey,
         new_resource_close_hotkey, new_notification_relaunch, new_resource_relaunch,
         new_enable_playtime_summary, new_playtime_summary_mode, new_enable_system_audio, new_system_audio_level,
         new_enable_game_audio, new_game_audio_level, new_enable_during_power, new_during_power_plan,
         new_enable_after_power, new_after_power_plan, new_enable_game_mode_start,
         new_enable_game_mode_end, new_enable_debug_mode,
         new_enable_cpu_thermal, new_enable_gpu_thermal, new_enable_cpu_temp_alert, new_cpu_temp_warning_threshold,
         new_cpu_temp_critical_threshold, new_enable_gpu_temp_alert, new_gpu_temp_warning_threshold,
         new_gpu_temp_critical_threshold) = load_process_names_and_startup()

        notification_processes[:] = new_notification_processes
        resource_processes[:] = new_resource_processes

        if new_startup != launch_at_startup:
            launch_at_startup = new_startup
            set_startup(launch_at_startup)

        launch_settings_on_start = new_launch_settings_on_start

        new_is_hotkey_registered = new_notification_close_hotkey or new_resource_close_hotkey
        if new_is_hotkey_registered != is_hotkey_registered:
            if new_is_hotkey_registered:
                keyboard.add_hotkey('ctrl+alt+k', lambda: (
                    kill_processes(notification_processes,
                                   killed_notification, "notification") if new_notification_close_hotkey else None,
                    kill_processes(resource_processes, killed_resource,
                                   "resource") if new_resource_close_hotkey else None
                ))
                log("Hotkey enabled", "SETTINGS")
            else:
                try:
                    keyboard.remove_hotkey('ctrl+alt+k')
                except:
                    pass
                log("Hotkey disabled", "SETTINGS")
            is_hotkey_registered = new_is_hotkey_registered

        notification_close_on_startup = new_notification_close_startup
        resource_close_on_startup = new_resource_close_startup
        notification_close_on_hotkey = new_notification_close_hotkey
        resource_close_on_hotkey = new_resource_close_hotkey
        notification_relaunch_on_exit = new_notification_relaunch
        resource_relaunch_on_exit = new_resource_relaunch
        enable_playtime_summary = new_enable_playtime_summary
        playtime_summary_mode = new_playtime_summary_mode
        enable_system_audio = new_enable_system_audio
        system_audio_level = new_system_audio_level
        enable_game_audio = new_enable_game_audio
        game_audio_level = new_game_audio_level
        enable_during_power = new_enable_during_power
        during_power_plan = new_during_power_plan
        enable_after_power = new_enable_after_power
        after_power_plan = new_after_power_plan
        enable_game_mode_start = new_enable_game_mode_start
        enable_game_mode_end = new_enable_game_mode_end

        # Update console visibility if debug mode changed
        if new_enable_debug_mode != enable_debug_mode:
            set_console_visibility(new_enable_debug_mode)
        enable_debug_mode = new_enable_debug_mode
        enable_cpu_thermal = new_enable_cpu_thermal
        enable_gpu_thermal = new_enable_gpu_thermal
        enable_cpu_temp_alert = new_enable_cpu_temp_alert
        cpu_temp_warning_threshold = new_cpu_temp_warning_threshold
        cpu_temp_critical_threshold = new_cpu_temp_critical_threshold
        enable_gpu_temp_alert = new_enable_gpu_temp_alert
        gpu_temp_warning_threshold = new_gpu_temp_warning_threshold
        gpu_temp_critical_threshold = new_gpu_temp_critical_threshold

        log("Settings reloaded successfully", "SETTINGS")

    event_handler = SettingsFileHandler(reload_settings)
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(os.path.abspath(SETTINGS_FILE)) or '.', recursive=False)
    observer.start()
    log("Settings file watcher started", "INIT")

    poll_count = 0
    try:
        while True:
            current_app_id = get_running_steam_app_id()
            poll_count += 1

            # Log polling status every 20 polls (~20 seconds)
            if poll_count % 20 == 0:
                if current_app_id == 0:
                    log("Polling... No game detected", "MONITOR")
                else:
                    log(f"Polling... Game running: AppID {current_app_id}", "MONITOR")

            if current_app_id != previous_app_id:
                if current_app_id == 0:
                    log("=" * 40, "GAME")
                    log("GAME ENDED", "GAME")
                    log("=" * 40, "GAME")

                    if previous_app_id != 0:
                        # Stop temperature monitoring and get temp data
                        temp_data = temperature_tracker.stop_monitoring()

                        # Save temperature history and get lifetime max temps
                        max_cpu = temp_data.get('max_cpu')
                        max_gpu = temp_data.get('max_gpu')
                        if max_cpu is not None or max_gpu is not None:
                            save_temp_history(previous_app_id, current_game_name, max_cpu, max_gpu)
                        lifetime_temps = get_lifetime_max_temps(previous_app_id)

                        if enable_playtime_summary and start_time is not None:
                            end_time = time.time()
                            duration = end_time - start_time
                            hours = int(duration // 3600)
                            minutes = int((duration % 3600) // 60)
                            seconds = int(duration % 60)
                            closed_apps_count = len(killed_notification) + len(killed_resource)
                            log(f"Session duration: {hours}h {minutes}m", "GAME")
                            log(f"Apps closed during session: {closed_apps_count}", "GAME")

                            # Build list of closed app names
                            closed_apps_list = list(killed_notification.keys()) + list(killed_resource.keys())

                            # Build session data for summary
                            session_data = {
                                'app_id': previous_app_id,
                                'game_name': current_game_name,
                                'hours': hours,
                                'minutes': minutes,
                                'seconds': seconds,
                                'closed_apps_count': closed_apps_count,
                                'closed_apps_list': closed_apps_list,
                                'start_cpu_temp': temp_data.get('start_cpu'),
                                'start_gpu_temp': temp_data.get('start_gpu'),
                                'max_cpu_temp': temp_data.get('max_cpu'),
                                'max_gpu_temp': temp_data.get('max_gpu'),
                                'lifetime_max_cpu': lifetime_temps.get('lifetime_max_cpu'),
                                'lifetime_max_gpu': lifetime_temps.get('lifetime_max_gpu')
                            }

                            if playtime_summary_mode == 'detailed':
                                # Show detailed popup window
                                show_detailed_summary(session_data)
                            else:
                                # Show brief toast notification
                                show_brief_summary(session_data)

                        if notification_relaunch_on_exit:
                            relaunch_processes(killed_notification, notification_relaunch_on_exit, "notification")
                        if resource_relaunch_on_exit:
                            relaunch_processes(killed_resource, resource_relaunch_on_exit, "resource")

                        if enable_after_power:
                            set_power_plan(after_power_plan)

                        if enable_game_mode_end:
                            set_game_mode(False)

                        log("Checking for pending updates...", "UPDATE")
                        from updater import apply_pending_update
                        apply_pending_update(show_notification)

                        start_time = None
                        current_game_name = None
                else:
                    game_name = get_game_name(current_app_id)
                    log("=" * 40, "GAME")
                    log(f"GAME STARTED: {game_name} (AppID {current_app_id})", "GAME")
                    log("=" * 40, "GAME")

                    if previous_app_id == 0:
                        start_time = time.time()
                        current_game_name = game_name

                        if notification_close_on_startup:
                            log("Closing notification apps...", "GAME")
                            kill_processes(notification_processes, killed_notification, "notification")
                        if resource_close_on_startup:
                            log("Closing resource apps...", "GAME")
                            kill_processes(resource_processes, killed_resource, "resource")
                        if enable_system_audio:
                            set_system_volume(system_audio_level)
                        if enable_game_audio:
                            log("Configuring game audio...", "GAME")
                            game_folder = get_game_folder(current_app_id)
                            game_pids = find_game_pids(game_folder)
                            set_game_volume(game_pids, game_audio_level, game_folder, game_name)
                        if enable_during_power:
                            set_power_plan(during_power_plan)
                        if enable_game_mode_start:
                            set_game_mode(True)

                        # Start temperature monitoring for new game session
                        temperature_tracker.start_monitoring(stop_event, enable_cpu_thermal, enable_gpu_thermal,
                                                             enable_cpu_temp_alert, cpu_temp_warning_threshold,
                                                             cpu_temp_critical_threshold, enable_gpu_temp_alert,
                                                             gpu_temp_warning_threshold, gpu_temp_critical_threshold,
                                                             game_name=game_name)

                        # Pre-cache image, pre-load into memory, and warm up CTk for instant session popup
                        threading.Thread(target=prepare_session_popup, args=(current_app_id,), daemon=True).start()

                        log(f"Game session started for: {game_name}", "GAME")

                previous_app_id = current_app_id

            if stop_event.wait(1):
                break

    finally:
        log("Stopping settings file watcher...", "SHUTDOWN")
        observer.stop()
        observer.join()


# =============================================================================
# Tray Menu Actions
# =============================================================================

def open_settings(icon, query):
    """Launch the settings UI window."""
    log("Opening settings UI...", "UI")
    try:
        if getattr(sys, 'frozen', False):
            subprocess.Popen([sys.executable, '--ui', str(os.getpid())])
        else:
            subprocess.Popen([sys.executable, __file__, '--ui', str(os.getpid())])
        log("Settings UI launched", "UI")
    except Exception as e:
        log(f"Could not open settings: {e}", "ERROR")


def quit_app(icon, query):
    """Shut down Vapor gracefully."""
    log("Quit requested - shutting down...", "SHUTDOWN")
    stop_event.set()

    # Close any open popup windows to release file handles
    close_all_popups()

    try:
        keyboard.unhook_all()
    except:
        pass
    # Free debug console if it exists
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.kernel32.FreeConsole()
    except:
        pass

    # Brief delay to allow background threads to clean up
    time.sleep(0.5)

    icon.stop()


def manual_check_updates(icon, query):
    """Trigger manual update check from tray menu."""
    log("Manual update check requested", "UPDATE")

    def check_thread():
        try:
            # Use the same proxy and headers as the auto-updater
            from updater import PROXY_BASE_URL, GITHUB_OWNER, GITHUB_REPO, HEADERS
            proxy_url = f"{PROXY_BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

            response = requests.get(
                proxy_url,
                headers=HEADERS,
                timeout=10
            )

            if response.status_code != 200:
                show_notification("Failed to check for updates. Please try again later.")
                return

            release_data = response.json()
            latest_version = release_data.get("tag_name", "").lstrip('v')

            from updater import compare_versions
            comparison = compare_versions(latest_version, CURRENT_VERSION)

            if comparison > 0:
                show_notification(f"Update available: v{latest_version}. Will download automatically.")
                check_for_updates(get_running_steam_app_id(), show_notification)
            else:
                show_notification(f"Vapor is running the latest version (v{CURRENT_VERSION}).")
                log(f"Already on latest version: v{CURRENT_VERSION}", "UPDATE")

        except Exception as e:
            log(f"Manual update check failed: {e}", "ERROR")
            show_notification("Failed to check for updates. Please try again later.")

    threading.Thread(target=check_thread, daemon=True).start()


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--ui':
        # === UI MODE ===
        # Launch settings interface
        pid = int(sys.argv[2]) if len(sys.argv) > 2 else None
        os.chdir(base_dir)
        sys.path.insert(0, base_dir)

        # Pass parent PID to UI for process monitoring
        if pid:
            os.environ['VAPOR_MAIN_PID'] = str(pid)

        # Pass the actual Vapor executable path for restart functionality
        if getattr(sys, 'frozen', False):
            # When frozen, sys.executable is the actual Vapor.exe path
            os.environ['VAPOR_EXE_PATH'] = sys.executable
        else:
            # When running from source, pass the script path
            os.environ['VAPOR_EXE_PATH'] = os.path.abspath(__file__)

        import vapor_settings_ui

    else:
        # === NORMAL TRAY MODE ===
        try:
            killed_notification = {}
            killed_resource = {}
            stop_event = threading.Event()

            # Check if this is the first run (no settings file exists)
            is_first_run = not os.path.exists(SETTINGS_FILE)
            if is_first_run:
                log("First run detected - creating default settings file", "INIT")
                create_default_settings()

            # Check if CPU thermal monitoring is enabled and we need admin privileges
            if os.path.exists(SETTINGS_FILE):
                try:
                    with open(SETTINGS_FILE, 'r') as f:
                        startup_settings = json.load(f)
                    if startup_settings.get('enable_cpu_thermal', False) and not is_admin():
                        log("CPU thermal monitoring enabled but not running as admin - requesting elevation", "INIT")
                        if request_admin_restart():
                            # Release mutex before exiting so elevated instance can acquire it
                            if VAPOR_MUTEX:
                                try:
                                    win32api.CloseHandle(VAPOR_MUTEX)
                                except Exception:
                                    pass
                            sys.exit(0)  # Exit current instance, elevated one will start
                except Exception as e:
                    log(f"Error checking thermal settings: {e}", "ERROR")

            # Log temperature monitoring library availability
            log(f"Temperature libraries - NVIDIA: {NVML_AVAILABLE}, AMD: {PYADL_AVAILABLE}, "
                f"LHM DLL: {LHM_AVAILABLE}, WMI: {WMI_AVAILABLE}", "TEMP")
            log(f"Admin privileges: {is_admin()}", "INIT")

            # Check Windows notification settings and warn if disabled
            check_and_warn_notifications()

            # Start the main monitoring thread
            thread = threading.Thread(target=monitor_steam_games,
                                      args=(stop_event, killed_notification, killed_resource, is_first_run),
                                      daemon=True)
            thread.start()

            # Start periodic update checking
            from updater import periodic_update_check

            current_app_id_holder = [0]


            def get_current_app_id():
                return current_app_id_holder[0]


            update_thread = threading.Thread(
                target=periodic_update_check,
                args=(stop_event, get_running_steam_app_id, show_notification, 3600),
                daemon=True
            )
            update_thread.start()

            menu = pystray.Menu(
                item('Launch Settings', open_settings),
                item('Check Updates', manual_check_updates),
                pystray.Menu.SEPARATOR,
                item('Quit', quit_app)
            )

            icon_image = Image.open(TRAY_ICON_PATH) if os.path.exists(TRAY_ICON_PATH) else None
            icon = pystray.Icon("Vapor", icon_image, "Vapor - Streamline Gaming", menu)
            log("System tray icon created", "INIT")
            icon.run()

            thread.join()
            log("Vapor has stopped.", "SHUTDOWN")

        except Exception as e:
            # Log the error if possible
            try:
                log(f"Fatal error: {e}", "ERROR")
            except:
                pass
            raise

        finally:
            # Ensure console is always cleaned up, even on crash
            _cleanup_console()