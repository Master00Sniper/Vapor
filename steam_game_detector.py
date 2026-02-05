# steam_game_detector.py
# Main Vapor application - monitors Steam games and manages system resources during gameplay.

# =============================================================================
# Single Instance Check (runs before anything else)
# =============================================================================

import sys
import os

# Detect Nuitka compilation and set sys.frozen for compatibility
# Nuitka sets __compiled__ but not sys.frozen, which breaks frozen detection
try:
    if __compiled__:
        sys.frozen = True
except NameError:
    pass

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
# Splash Screen with Background Initialization
# =============================================================================

import threading

# Event to signal when splash screen has finished displaying
_splash_complete = threading.Event()
# Event to signal when background imports are done
_imports_complete = threading.Event()


def _do_background_imports():
    """Import heavy modules in background while splash is showing."""
    try:
        # These imports take time - do them while splash is visible
        global win32gui, customtkinter, winreg, requests, time, psutil, subprocess
        global json, win32api, win32con, win32event, winerror, keyboard, pystray, item
        global Image, ctypes, re, comtypes, CLSCTX_ALL, COINIT_MULTITHREADED
        global AudioUtilities, IAudioEndpointVolume, CLSID_MMDeviceEnumerator
        global EDataFlow, ERole, IMMDeviceEnumerator, Observer, FileSystemEventHandler
        global win11toast, atexit, signal

        import win32gui
        import customtkinter
        import winreg
        import requests
        import time
        import psutil
        import subprocess
        import json
        import win32api, win32con, win32event, winerror
        import keyboard
        import pystray
        from pystray import MenuItem as item
        from PIL import Image
        import ctypes
        import re
        import comtypes
        from comtypes import CLSCTX_ALL, COINIT_MULTITHREADED
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from pycaw.constants import CLSID_MMDeviceEnumerator, EDataFlow, ERole
        from pycaw.pycaw import IMMDeviceEnumerator
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        import win11toast
        import atexit
        import signal
    except Exception:
        pass
    finally:
        _imports_complete.set()


def show_splash_screen():
    """Display splash screen while doing initialization in background."""
    try:
        import tkinter as tk
        from PIL import Image, ImageTk

        # Determine base directory
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                base_dir = sys._MEIPASS
            else:
                base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        splash_path = os.path.join(base_dir, 'Images', 'splash_screen.png')

        if not os.path.exists(splash_path):
            # No splash image - just do imports and signal completion
            _do_background_imports()
            _imports_complete.wait()
            _splash_complete.set()
            return

        # Start background imports before showing splash
        import_thread = threading.Thread(target=_do_background_imports, daemon=True)
        import_thread.start()

        # Create splash window
        splash = tk.Tk()
        splash.overrideredirect(True)  # Remove window decorations
        splash.attributes('-topmost', True)  # Keep on top of other windows

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

        # Track minimum display time
        min_time_reached = [False]

        def on_min_time():
            min_time_reached[0] = True
            # If imports are also done, close splash
            if _imports_complete.is_set():
                splash.destroy()

        def check_imports():
            # If minimum time reached and imports done, close
            if min_time_reached[0] and _imports_complete.is_set():
                splash.destroy()
            else:
                # Check again in 50ms
                splash.after(50, check_imports)

        # Close after minimum 2 seconds AND imports complete
        splash.after(2000, on_min_time)
        splash.after(100, check_imports)  # Start checking for import completion

        splash.mainloop()
    except Exception:
        # On any error, ensure imports still happen
        if not _imports_complete.is_set():
            _do_background_imports()
            _imports_complete.wait()
    finally:
        _splash_complete.set()


def wait_for_splash_complete():
    """Wait for splash screen to finish before proceeding. Used by settings window launch."""
    _splash_complete.wait()


# Only show splash for main app, not settings UI, and not when restarting elevated
if '--ui' not in sys.argv and '--elevated' not in sys.argv:
    show_splash_screen()
else:
    # For settings UI or elevated restart, mark splash as complete immediately
    _splash_complete.set()
    _imports_complete.set()

# Ensure background imports completed before proceeding
_imports_complete.wait()

# =============================================================================
# Imports (fast since most are already loaded by background thread)
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

# Core modules
from core import (
    # Temperature monitoring
    NVML_AVAILABLE, PYADL_AVAILABLE, WMI_AVAILABLE, HWMON_AVAILABLE, LHM_AVAILABLE,
    get_gpu_temperature, get_cpu_temperature, show_temperature_alert,
    TemperatureTracker, temperature_tracker,
    TEMP_HISTORY_DIR, get_temp_history_path, load_temp_history, save_temp_history, get_lifetime_max_temps,
    # Audio control
    set_system_volume, find_game_pids, set_game_volume,
    # Steam API
    get_running_steam_app_id, get_game_name, get_game_header_image, get_game_store_details,
    preload_game_details, get_preloaded_game_details,
    HEADER_IMAGE_CACHE_DIR, get_cached_header_image_path, cache_game_header_image,
    preload_header_image, get_preloaded_header_image,
    warmup_customtkinter, prepare_session_popup,
    # Steam filesystem
    DEFAULT_STEAM_PATH, get_steam_path, get_library_folders, get_game_folder,
    # Notifications
    register_popup, unregister_popup, close_all_popups,
    check_and_warn_notifications,
    show_notification, show_brief_summary, show_detailed_summary,
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
            # PyInstaller: sys.executable is Vapor.exe
            # Nuitka: sys.executable is python.exe in temp, use sys.argv[0] instead
            if hasattr(sys, '_MEIPASS'):
                executable = sys.executable
                work_dir = os.path.dirname(sys.executable)
            else:
                executable = sys.argv[0]
                work_dir = os.path.dirname(sys.argv[0])
            # Add --elevated flag to skip splash screen on restart
            existing_params = ' '.join(sys.argv[1:])
            params = f'{existing_params} --elevated'.strip()
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


# Global shutdown flag for graceful termination
_shutdown_requested = threading.Event()
_tray_icon = None  # Will hold reference to tray icon for shutdown
_child_processes = []  # Track child processes (e.g., settings window)
_stop_event = None  # Will hold reference to stop_event for signal handler


def _terminate_child_processes():
    """Terminate any child processes we spawned."""
    for proc in _child_processes:
        try:
            if proc.poll() is None:  # Still running
                proc.terminate()
        except Exception:
            pass
    _child_processes.clear()


def _signal_handler(signum, frame):
    """Handle termination signals with proper cleanup before exit."""
    _shutdown_requested.set()

    # Signal monitoring thread to stop
    if _stop_event is not None:
        _stop_event.set()

    # Close any open popup windows
    try:
        close_all_popups()
    except Exception:
        pass

    # Unhook keyboard hotkeys
    try:
        keyboard.unhook_all()
    except Exception:
        pass

    # Terminate child processes (settings window, etc.)
    _terminate_child_processes()

    # Clean up console
    _cleanup_console()

    # Stop the tray icon if it exists
    if _tray_icon is not None:
        try:
            _tray_icon.stop()
        except Exception:
            pass

    # Brief delay to allow cleanup to complete (matches tray Quit)
    time.sleep(0.5)

    # Force immediate exit - pystray's event loop doesn't always respond to stop()
    os._exit(0)


atexit.register(_cleanup_console)
atexit.register(_terminate_child_processes)

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
    if hasattr(sys, '_MEIPASS'):
        application_path = sys._MEIPASS
    else:
        application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(application_path)
sys.path.append(application_path)

# Import shared utilities (logging, constants, paths, settings)
from utils import (
    base_dir, appdata_dir, SETTINGS_FILE, DEBUG_LOG_FILE,
    MAX_LOG_SIZE, TRAY_ICON_PATH, PROTECTED_PROCESSES, log,
    load_settings as load_settings_dict, save_settings as save_settings_dict,
    create_default_settings as create_default_settings_shared, DEFAULT_SETTINGS,
    GAME_STARTED_SIGNAL_FILE
)

# Import platform utilities (admin checks, PawnIO driver)
from platform_utils import (
    is_admin, is_pawnio_installed, run_pawnio_installer,
    clear_pawnio_cache
)

# Additional paths specific to main application
UI_SCRIPT_PATH = os.path.join(base_dir, 'vapor_settings_ui.py')

from updater import check_for_updates, CURRENT_VERSION, send_telemetry


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
# Process Management
# =============================================================================

def send_close_signal(proc):
    """
    Send WM_CLOSE to all windows belonging to a process.
    Returns the number of windows that received the close signal.
    """
    pid = proc.pid

    def enum_windows_callback(hwnd, windows):
        """Callback to collect windows belonging to the process."""
        try:
            _, window_pid = win32gui.GetWindowThreadProcessId(hwnd)
            if window_pid == pid:
                windows.append(hwnd)
        except Exception:
            pass
        return True

    # Find all windows belonging to this process
    windows = []
    try:
        win32gui.EnumWindows(enum_windows_callback, windows)
    except Exception:
        return 0

    # Send WM_CLOSE to all windows
    WM_CLOSE = 0x0010
    closed_count = 0
    for hwnd in windows:
        try:
            win32gui.PostMessage(hwnd, WM_CLOSE, 0, 0)
            closed_count += 1
        except Exception:
            pass

    return closed_count


def kill_processes(process_names, killed_processes, purpose="", graceful_timeout=5):
    """
    Terminate processes from the given list.
    Attempts graceful close first (WM_CLOSE), then force terminates if needed.
    Stores process info in killed_processes dict for potential relaunch.
    """
    purpose_str = f" ({purpose})" if purpose else ""
    log(f"Attempting to close {len(process_names)} {purpose} process type(s)...", "PROCESS")

    # Phase 1: Collect all target processes and send close signals
    target_processes = []  # List of (proc, name, path) tuples
    paths_by_name = {}  # Store first path found for each process name

    for name in process_names:
        # Skip protected system processes
        if name.lower() in PROTECTED_PROCESSES:
            log(f"Skipping protected process: {name}", "PROCESS")
            continue

        for proc in psutil.process_iter(['name', 'exe', 'pid']):
            try:
                if proc.info['name'].lower() == name.lower():
                    path = proc.info['exe']
                    if path and os.path.exists(path):
                        target_processes.append((proc, name, path))
                        if name not in paths_by_name:
                            paths_by_name[name] = path
                        # Send WM_CLOSE to any windows this process has
                        window_count = send_close_signal(proc)
                        if window_count > 0:
                            log(f"Sent close signal to {name} (PID: {proc.pid}, {window_count} windows)", "PROCESS")
                        else:
                            log(f"Closing{purpose_str}: {name} (PID: {proc.pid}, no windows)", "PROCESS")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            except Exception as e:
                log(f"Error finding {name}: {e}", "ERROR")

    if not target_processes:
        return

    # Phase 2: Wait for graceful exit
    log(f"Waiting {graceful_timeout}s for {len(target_processes)} process(es) to close gracefully...", "PROCESS")
    time.sleep(graceful_timeout)

    # Phase 3: Check which processes exited and force-terminate the rest
    closed_counts = {}  # Count closed processes per name

    for proc, name, path in target_processes:
        try:
            if not proc.is_running():
                # Process exited gracefully
                log(f"Gracefully closed: {name} (PID: {proc.pid})", "PROCESS")
                closed_counts[name] = closed_counts.get(name, 0) + 1
            else:
                # Still running, force terminate
                log(f"Force terminating: {name} (PID: {proc.pid})", "PROCESS")
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except psutil.TimeoutExpired:
                    proc.kill()
                closed_counts[name] = closed_counts.get(name, 0) + 1
        except psutil.NoSuchProcess:
            # Already exited
            closed_counts[name] = closed_counts.get(name, 0) + 1
        except Exception as e:
            log(f"Error closing {name}: {e}", "ERROR")

    # Record results
    for name, count in closed_counts.items():
        if count > 0:
            killed_processes[name] = paths_by_name.get(name)
            log(f"Closed {count} instance(s) of {name}{purpose_str}", "PROCESS")


def kill_processes_async(process_names, killed_processes, purpose=""):
    """
    Run kill_processes in a background thread so it doesn't block other operations.
    """
    thread = threading.Thread(
        target=kill_processes,
        args=(process_names, killed_processes, purpose),
        daemon=True
    )
    thread.start()


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

    # Check if we need to reopen settings after an admin restart
    # Also check if CPU thermal is enabled but driver is missing
    pending_settings_reopen = False
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                startup_settings = json.load(f)
            settings_modified = False

            if startup_settings.get('pending_settings_reopen', False):
                pending_settings_reopen = True
                startup_settings['pending_settings_reopen'] = False
                settings_modified = True
                log("Pending settings reopen flag detected and cleared", "INIT")

            # If CPU thermal is enabled but PawnIO driver is not installed, disable it
            if startup_settings.get('enable_cpu_thermal', False) and not is_pawnio_installed():
                log("CPU thermal enabled but PawnIO driver not installed - disabling setting", "INIT")
                startup_settings['enable_cpu_thermal'] = False
                settings_modified = True

            if settings_modified:
                with open(SETTINGS_FILE, 'w') as f:
                    json.dump(startup_settings, f, indent=4)
        except Exception as e:
            log(f"Error checking startup settings: {e}", "ERROR")

    # Launch settings on start if enabled, if first run, or if pending reopen
    if is_first_run or launch_settings_on_start or pending_settings_reopen:
        # Wait for splash screen to finish before showing settings window
        wait_for_splash_complete()
        log("Launching settings window on startup...", "INIT")
        try:
            if getattr(sys, 'frozen', False):
                # PyInstaller uses sys.executable, Nuitka uses sys.argv[0]
                exe_path = sys.executable if hasattr(sys, '_MEIPASS') else sys.argv[0]
                subprocess.Popen([exe_path, '--ui', str(os.getpid())])
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
            kill_processes_async(notification_processes, killed_notification, "notification")
        if resource_close_on_startup:
            kill_processes_async(resource_processes, killed_resource, "resource")
        if enable_system_audio:
            set_system_volume(system_audio_level)
        if enable_game_audio:
            game_folder = get_game_folder(previous_app_id)
            game_pids = find_game_pids(game_folder)
            is_game_running = lambda app_id=previous_app_id: get_running_steam_app_id() == app_id
            set_game_volume(game_pids, game_audio_level, game_folder, current_game_name, is_game_running)
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
    # Don't show notification if settings window is open (user can already see Vapor is running)
    if not (is_first_run or launch_settings_on_start or pending_settings_reopen):
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

            # Log polling status periodically
            if current_app_id == 0:
                # Log "No game detected" only once per hour (3600 polls at 1 poll/second)
                if poll_count % 3600 == 0:
                    log("Polling... No game detected", "MONITOR")
            else:
                # Log "Game running" every 20 polls (~20 seconds)
                if poll_count % 20 == 0:
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
                                # Ensure session popup data is ready (in case game ended before delayed prep)
                                prepare_session_popup(previous_app_id)
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

                    # Signal settings UI to close (if open)
                    try:
                        with open(GAME_STARTED_SIGNAL_FILE, 'w') as f:
                            f.write(str(current_app_id))
                        log("Created game started signal for settings UI", "GAME")
                    except Exception as e:
                        log(f"Failed to create game started signal: {e}", "GAME")

                    if previous_app_id == 0:
                        start_time = time.time()
                        current_game_name = game_name

                        # VERY LOW PRIORITY: Pre-cache session popup after 60 second delay
                        # Start this FIRST so the 60s timer begins immediately when game is detected
                        def delayed_prepare_popup(app_id):
                            time.sleep(60)
                            # Only run if the game is still running (skip if game ended early)
                            if get_running_steam_app_id() == app_id:
                                prepare_session_popup(app_id)
                        threading.Thread(target=delayed_prepare_popup, args=(current_app_id,), daemon=True).start()

                        # HIGH PRIORITY: Audio settings first (most time-sensitive for player experience)
                        if enable_system_audio:
                            set_system_volume(system_audio_level)
                        if enable_game_audio:
                            log("Configuring game audio...", "GAME")
                            game_folder = get_game_folder(current_app_id)
                            game_pids = find_game_pids(game_folder)
                            # Pass a function to check if game is still running (stops monitoring if game ends)
                            is_game_running = lambda app_id=current_app_id: get_running_steam_app_id() == app_id
                            set_game_volume(game_pids, game_audio_level, game_folder, game_name, is_game_running)

                        # MEDIUM PRIORITY: Close apps (async, won't block game loading)
                        if notification_close_on_startup:
                            log("Closing notification apps...", "GAME")
                            kill_processes_async(notification_processes, killed_notification, "notification")
                        if resource_close_on_startup:
                            log("Closing resource apps...", "GAME")
                            kill_processes_async(resource_processes, killed_resource, "resource")

                        # LOW PRIORITY: System optimizations
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
            # PyInstaller uses sys.executable, Nuitka uses sys.argv[0]
            exe_path = sys.executable if hasattr(sys, '_MEIPASS') else sys.argv[0]
            proc = subprocess.Popen([exe_path, '--ui', str(os.getpid())])
        else:
            proc = subprocess.Popen([sys.executable, __file__, '--ui', str(os.getpid())])
        _child_processes.append(proc)
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
            # PyInstaller: sys.executable is Vapor.exe
            # Nuitka: sys.executable is python.exe in temp, use sys.argv[0] instead
            if hasattr(sys, '_MEIPASS'):
                os.environ['VAPOR_EXE_PATH'] = sys.executable
            else:
                os.environ['VAPOR_EXE_PATH'] = sys.argv[0]
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
            _stop_event = stop_event  # Make accessible to signal handler (module-level var)

            # Log PyInstaller details for debugging restart issues
            log(f"=== Vapor Startup ===", "INIT")
            log(f"PID: {os.getpid()}", "INIT")
            log(f"sys.executable: {sys.executable}", "INIT")
            log(f"sys.frozen: {getattr(sys, 'frozen', False)}", "INIT")
            log(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}", "INIT")
            log(f"ENV _MEIPASS: {os.environ.get('_MEIPASS', 'N/A')}", "INIT")
            log(f"ENV _MEIPASS2: {os.environ.get('_MEIPASS2', 'N/A')}", "INIT")
            log(f"ENV VAPOR_EXE_PATH: {os.environ.get('VAPOR_EXE_PATH', 'N/A')}", "INIT")
            log(f"TEMP: {os.environ.get('TEMP', 'N/A')}", "INIT")
            log(f"Working dir: {os.getcwd()}", "INIT")

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

            # Send anonymous telemetry (startup ping)
            send_telemetry("app_start")

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

            # Store reference for signal handler to use during shutdown
            _tray_icon = icon

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