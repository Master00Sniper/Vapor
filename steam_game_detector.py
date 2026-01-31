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

# =============================================================================
# Temperature Monitoring (Optional - graceful fallback if unavailable)
# =============================================================================

# NVIDIA GPU temperature via nvidia-ml-py
try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False

# AMD GPU temperature via pyadl
try:
    from pyadl import ADLManager
    PYADL_AVAILABLE = True
except Exception:
    # pyadl raises ADLError if no AMD GPU/driver found, not just ImportError
    PYADL_AVAILABLE = False

# CPU temperature via WMI (requires LibreHardwareMonitor or OpenHardwareMonitor running)
try:
    import wmi
    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False

# HardwareMonitor package (PyPI) - handles LibreHardwareMonitor + PawnIO driver
# Note: This may fail in PyInstaller builds if DLLs aren't bundled, falls back to manual DLL loading
HWMON_AVAILABLE = False
HWMON_COMPUTER = None
CPU_TEMP_ERRORS_LOGGED = False  # Only log WMI/fallback errors once
try:
    from HardwareMonitor.Hardware import Computer, IVisitor, IComputer, IHardware, IParameter, ISensor
    from HardwareMonitor.Hardware import HardwareType, SensorType
    HWMON_AVAILABLE = True
except Exception:
    # Catches ImportError, FileNotFoundException, and any .NET exceptions
    pass

# Fallback: LibreHardwareMonitorLib via pythonnet (bundled DLL approach)
LHM_AVAILABLE = False
LHM_COMPUTER = None
if not HWMON_AVAILABLE:
    try:
        import clr
        import System
        from System.Reflection import Assembly

        # Determine lib folder path
        if getattr(sys, 'frozen', False):
            lib_dir = os.path.join(sys._MEIPASS, 'lib')
        else:
            lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib')

        lhm_dll_path = os.path.join(lib_dir, 'LibreHardwareMonitorLib.dll')

        # Fallback to root directory for backwards compatibility
        if not os.path.exists(lhm_dll_path):
            if getattr(sys, 'frozen', False):
                lhm_dll_path = os.path.join(sys._MEIPASS, 'LibreHardwareMonitorLib.dll')
                lib_dir = sys._MEIPASS
            else:
                lhm_dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'LibreHardwareMonitorLib.dll')
                lib_dir = os.path.dirname(os.path.abspath(__file__))

        if os.path.exists(lhm_dll_path):
            # Add lib directory to assembly search path for dependencies
            System.AppDomain.CurrentDomain.AppendPrivatePath(lib_dir)

            # Pre-load dependencies that LibreHardwareMonitorLib needs
            for dep_dll in ['System.Memory.dll', 'System.Buffers.dll', 'HidSharp.dll']:
                dep_path = os.path.join(lib_dir, dep_dll)
                if os.path.exists(dep_path):
                    try:
                        Assembly.LoadFrom(dep_path)
                    except:
                        pass

            clr.AddReference(lhm_dll_path)
            from LibreHardwareMonitor.Hardware import Computer, HardwareType, SensorType
            LHM_AVAILABLE = True
    except Exception:
        pass


# Visitor class for HardwareMonitor package (only defined if package available)
HardwareUpdateVisitor = None
if HWMON_AVAILABLE:
    class HardwareUpdateVisitor(IVisitor):
        """Visitor to update all hardware sensors."""
        __namespace__ = "VaporMonitor"

        def VisitComputer(self, computer: IComputer):
            computer.Traverse(self)

        def VisitHardware(self, hardware: IHardware):
            hardware.Update()
            for subHardware in hardware.SubHardware:
                subHardware.Update()

        def VisitParameter(self, parameter: IParameter):
            pass

        def VisitSensor(self, sensor: ISensor):
            pass

import atexit
import signal


# =============================================================================
# Admin Privilege Functions
# =============================================================================

def is_admin():
    """Check if the current process has admin privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


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
# PawnIO Driver Functions (for CPU temperature monitoring)
# =============================================================================

PAWNIO_CHECKED = False
PAWNIO_INSTALLED = None

def is_pawnio_installed():
    """Check if PawnIO driver is installed."""
    global PAWNIO_CHECKED, PAWNIO_INSTALLED

    if PAWNIO_CHECKED:
        return PAWNIO_INSTALLED

    PAWNIO_CHECKED = True
    try:
        # Check via winget list
        result = subprocess.run(
            ['winget', 'list', '--id', 'PawnIO.PawnIO'],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        PAWNIO_INSTALLED = 'PawnIO' in result.stdout
        return PAWNIO_INSTALLED
    except Exception:
        # If winget check fails, assume not installed
        PAWNIO_INSTALLED = False
        return False


def get_pawnio_installer_path():
    """Get the path to the PawnIO installer script."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.join(sys._MEIPASS, 'install_pawnio.ps1')
    else:
        # Running as script
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'install_pawnio.ps1')


def run_pawnio_installer():
    """Run the PawnIO installer script with admin privileges."""
    script_path = get_pawnio_installer_path()

    if not os.path.exists(script_path):
        log(f"PawnIO installer not found: {script_path}", "TEMP")
        return False

    try:
        # Run PowerShell script elevated
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            "powershell.exe",
            f'-ExecutionPolicy Bypass -File "{script_path}"',
            os.path.dirname(script_path),
            1  # SW_SHOWNORMAL
        )

        # ShellExecuteW returns > 32 on success
        if result > 32:
            log("PawnIO installer launched successfully", "TEMP")
            # Reset the check so next temp read will re-check
            global PAWNIO_CHECKED
            PAWNIO_CHECKED = False
            return True
        else:
            log(f"Failed to launch PawnIO installer: {result}", "TEMP")
            return False
    except Exception as e:
        log(f"Error launching PawnIO installer: {e}", "TEMP")
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

base_dir = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))

# Settings stored in %APPDATA%/Vapor for persistence across updates
appdata_dir = os.path.join(os.getenv('APPDATA'), 'Vapor')
os.makedirs(appdata_dir, exist_ok=True)
SETTINGS_FILE = os.path.join(appdata_dir, 'vapor_settings.json')
NOTIFICATION_WARNING_DISMISSED_FILE = os.path.join(appdata_dir, 'notification_warning_dismissed')

TRAY_ICON_PATH = os.path.join(base_dir, 'Images', 'tray_icon.png')
UI_SCRIPT_PATH = os.path.join(base_dir, 'vapor_settings_ui.py')
STEAM_PATH = r"C:\Program Files (x86)\Steam\steamapps"

# System processes that should never be terminated (safety protection)
PROTECTED_PROCESSES = {
    # Windows core
    'explorer.exe', 'svchost.exe', 'csrss.exe', 'wininit.exe', 'winlogon.exe',
    'services.exe', 'lsass.exe', 'smss.exe', 'dwm.exe', 'taskhostw.exe',
    'sihost.exe', 'fontdrvhost.exe', 'ctfmon.exe', 'conhost.exe', 'dllhost.exe',
    'runtimebroker.exe', 'searchhost.exe', 'startmenuexperiencehost.exe',
    'shellexperiencehost.exe', 'textinputhost.exe', 'applicationframehost.exe',
    'systemsettings.exe', 'securityhealthservice.exe', 'securityhealthsystray.exe',
    # System utilities
    'taskmgr.exe', 'cmd.exe', 'powershell.exe', 'regedit.exe', 'mmc.exe',
    # Windows Defender / Security
    'msmpeng.exe', 'mssense.exe', 'nissrv.exe', 'securityhealthhost.exe',
    # Critical services
    'spoolsv.exe', 'wuauserv.exe', 'audiodg.exe',
    # Vapor itself
    'vapor.exe',
}

from updater import check_for_updates, CURRENT_VERSION


# =============================================================================
# Logging
# =============================================================================

# Log file for debugging (stored in %APPDATA%/Vapor)
DEBUG_LOG_FILE = os.path.join(appdata_dir, 'vapor_logs.log')

# Maximum log file size (5 MB) - will be truncated when exceeded
MAX_LOG_SIZE = 5 * 1024 * 1024


def log(message, category="INFO"):
    """Print timestamped log message with category and write to log file."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [{category}] {message}"

    # Print to console (if available)
    try:
        print(formatted)
    except (OSError, ValueError):
        # Handle case where console has been freed
        pass

    # Also write to log file
    try:
        # Check if log file is too large and truncate if needed
        if os.path.exists(DEBUG_LOG_FILE):
            if os.path.getsize(DEBUG_LOG_FILE) > MAX_LOG_SIZE:
                # Keep last 1000 lines
                with open(DEBUG_LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[-1000:]
                with open(DEBUG_LOG_FILE, 'w', encoding='utf-8') as f:
                    f.writelines(lines)

        with open(DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{formatted}\n")
    except Exception:
        pass


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
        popup.destroy()

    def on_dont_show_again():
        mark_notification_warning_dismissed()
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
    """Create default settings file on first run."""
    log("Creating default settings file...", "SETTINGS")
    default_settings = {
        'notification_processes': ['WhatsApp.Root.exe', 'Telegram.exe', 'ms-teams.exe', 'Messenger.exe', 'slack.exe',
                                   'Signal.exe', 'WeChat.exe'],
        'selected_notification_apps': ['WhatsApp', 'Telegram', 'Microsoft Teams', 'Facebook Messenger', 'Slack',
                                       'Signal', 'WeChat'],
        'custom_processes': [],
        'resource_processes': ['spotify.exe', 'OneDrive.exe', 'GoogleDriveFS.exe', 'Dropbox.exe', 'wallpaper64.exe'],
        'selected_resource_apps': ['Spotify', 'OneDrive', 'Google Drive', 'Dropbox', 'Wallpaper Engine',
                                   'iCUE', 'Razer Synapse', 'NZXT CAM'],
        'custom_resource_processes': [],
        'launch_at_startup': False,
        'launch_settings_on_start': True,
        'close_on_startup': True,
        'close_on_hotkey': True,
        'relaunch_on_exit': True,
        'resource_close_on_startup': True,
        'resource_close_on_hotkey': True,
        'resource_relaunch_on_exit': False,
        'enable_playtime_summary': True,
        'playtime_summary_mode': 'brief',
        'enable_debug_mode': False,
        'system_audio_level': 33,
        'enable_system_audio': False,
        'game_audio_level': 100,
        'enable_game_audio': False,
        'enable_during_power': False,
        'during_power_plan': 'High Performance',
        'enable_after_power': False,
        'after_power_plan': 'Balanced',
        'enable_game_mode_start': True,
        'enable_game_mode_end': False,
        'enable_cpu_thermal': False,
        'enable_gpu_thermal': True
    }
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(default_settings, f)
    log("Default settings file created", "SETTINGS")


def load_process_names_and_startup():
    """Load all settings from JSON file and return as tuple."""
    log("Loading settings from file...", "SETTINGS")
    if os.path.exists(SETTINGS_FILE):
        log(f"Settings file found: {SETTINGS_FILE}", "SETTINGS")
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            notification_processes = settings.get('notification_processes', [])
            resource_processes = settings.get('resource_processes', [])
            startup = settings.get('launch_at_startup', False)
            launch_settings_on_start = settings.get('launch_settings_on_start', True)
            notification_close_on_startup = settings.get('close_on_startup', True)
            resource_close_on_startup = settings.get('resource_close_on_startup', True)
            notification_close_on_hotkey = settings.get('close_on_hotkey', False)
            resource_close_on_hotkey = settings.get('resource_close_on_hotkey', False)
            notification_relaunch_on_exit = settings.get('relaunch_on_exit', True)
            resource_relaunch_on_exit = settings.get('resource_relaunch_on_exit', True)
            enable_playtime_summary = settings.get('enable_playtime_summary', True)
            playtime_summary_mode = settings.get('playtime_summary_mode', 'brief')
            enable_system_audio = settings.get('enable_system_audio', False)
            system_audio_level = settings.get('system_audio_level', 50)
            enable_game_audio = settings.get('enable_game_audio', False)
            game_audio_level = settings.get('game_audio_level', 50)
            enable_during_power = settings.get('enable_during_power', False)
            during_power_plan = settings.get('during_power_plan', 'High Performance')
            enable_after_power = settings.get('enable_after_power', False)
            after_power_plan = settings.get('after_power_plan', 'Balanced')
            enable_game_mode_start = settings.get('enable_game_mode_start', False)
            enable_game_mode_end = settings.get('enable_game_mode_end', False)
            enable_debug_mode = settings.get('enable_debug_mode', False)
            enable_cpu_thermal = settings.get('enable_cpu_thermal', False)
            enable_gpu_thermal = settings.get('enable_gpu_thermal', True)
            enable_cpu_temp_alert = settings.get('enable_cpu_temp_alert', False)
            cpu_temp_warning_threshold = settings.get('cpu_temp_warning_threshold', 85)
            cpu_temp_critical_threshold = settings.get('cpu_temp_critical_threshold', 95)
            enable_gpu_temp_alert = settings.get('enable_gpu_temp_alert', False)
            gpu_temp_warning_threshold = settings.get('gpu_temp_warning_threshold', 80)
            gpu_temp_critical_threshold = settings.get('gpu_temp_critical_threshold', 90)
            log("Settings loaded successfully", "SETTINGS")
            return (notification_processes, resource_processes, startup, launch_settings_on_start,
                    notification_close_on_startup, resource_close_on_startup, notification_close_on_hotkey,
                    resource_close_on_hotkey, notification_relaunch_on_exit, resource_relaunch_on_exit,
                    enable_playtime_summary, playtime_summary_mode, enable_system_audio, system_audio_level,
                    enable_game_audio, game_audio_level, enable_during_power, during_power_plan, enable_after_power,
                    after_power_plan, enable_game_mode_start, enable_game_mode_end, enable_debug_mode,
                    enable_cpu_thermal, enable_gpu_thermal, enable_cpu_temp_alert, cpu_temp_warning_threshold,
                    cpu_temp_critical_threshold, enable_gpu_temp_alert, gpu_temp_warning_threshold,
                    gpu_temp_critical_threshold)
    else:
        log("No settings file found - using defaults", "SETTINGS")
        default_notification = ['WhatsApp.Root.exe', 'Telegram.exe', 'ms-teams.exe', 'Messenger.exe', 'slack.exe',
                                'Signal.exe', 'WeChat.exe']
        default_resource = ['spotify.exe', 'OneDrive.exe', 'GoogleDriveFS.exe', 'Dropbox.exe', 'wallpaper64.exe']
        return (default_notification, default_resource, False, True, True, True, True, True, True, False,
                True, 'brief', False, 33, False, 100, False, 'High Performance', False, 'Balanced', True, False,
                False, False, True, False, 85, 95, False, 80, 90)


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


def show_temperature_alert(message):
    """Display a high-priority temperature alert notification that can bypass Do Not Disturb.

    Uses the 'alarm' scenario to ensure the notification appears even when
    Windows Focus Assist / Do Not Disturb is enabled during gameplay.
    """
    log(f"Showing temperature alert: {message}", "ALERT")
    icon_path = os.path.abspath(TRAY_ICON_PATH)
    win11toast.notify(body=message, app_id='Vapor - Streamline Gaming', scenario='alarm', icon=icon_path,
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

    # Fetch game header image URL
    header_image_url = get_game_header_image(app_id) if app_id else None

    # Run popup in a separate thread to avoid blocking
    def show_popup():
        popup = ctk.CTk()
        popup.title("Vapor - Game Session Details")

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
            command=popup.destroy,
            width=150,
            height=35,
            corner_radius=10,
            fg_color="green",
            hover_color="#228B22",
            font=("Calibri", 15)
        )
        ok_button.pack()

        # Scrollable content frame (fills remaining space above bottom bar)
        content_frame = ctk.CTkScrollableFrame(master=popup, fg_color="transparent")
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

        # Game header image from Steam
        if header_image_url:
            try:
                response = requests.get(header_image_url, timeout=5)
                if response.status_code == 200:
                    img_data = BytesIO(response.content)
                    pil_image = Image.open(img_data)
                    # Resize to fit nicely (Steam headers are 460x215)
                    # Scale to 400px wide while maintaining aspect ratio
                    aspect_ratio = pil_image.height / pil_image.width
                    new_width = 400
                    new_height = int(new_width * aspect_ratio)
                    pil_image = pil_image.resize((new_width, new_height), Image.LANCZOS)

                    ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image,
                                             size=(new_width, new_height))
                    image_label = ctk.CTkLabel(master=content_frame, image=ctk_image, text="")
                    image_label.pack(pady=(5, 10))
            except Exception as e:
                log(f"Failed to load game header image: {e}", "NOTIFY")

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
# Audio Control
# =============================================================================

def set_system_volume(level):
    """Set system master volume (0-100)."""
    log(f"Setting system volume to {level}%...", "AUDIO")
    comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    try:
        level = max(0, min(100, level)) / 100.0

        device_enumerator = comtypes.CoCreateInstance(
            CLSID_MMDeviceEnumerator,
            IMMDeviceEnumerator,
            comtypes.CLSCTX_ALL
        )

        default_device = device_enumerator.GetDefaultAudioEndpoint(
            EDataFlow.eRender.value,
            ERole.eMultimedia.value
        )

        interface = default_device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)

        volume.SetMasterVolumeLevelScalar(level, None)
        log(f"System volume set to {int(level * 100)}%", "AUDIO")
    except Exception as e:
        log(f"Failed to set system volume: {e}", "ERROR")
    finally:
        comtypes.CoUninitialize()


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
# Temperature Monitoring Functions
# =============================================================================

def get_gpu_temperature():
    """
    Get current GPU temperature in Celsius.
    Tries multiple methods: NVIDIA pynvml, AMD pyadl, nvidia-smi CLI, and WMI fallbacks.
    Returns None if temperature cannot be read.
    """
    # Try NVIDIA GPU first (pynvml library)
    if NVML_AVAILABLE:
        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                # Get temperature of first GPU (primary gaming GPU)
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                pynvml.nvmlShutdown()
                return temp
        except Exception as e:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
            # Don't log - will try fallbacks

    # Try AMD GPU (pyadl library)
    if PYADL_AVAILABLE:
        try:
            devices = ADLManager.getInstance().getDevices()
            if devices:
                # Get temperature of first GPU
                temp = devices[0].getCurrentTemperature()
                if temp is not None:
                    return int(temp)
        except Exception:
            pass  # Don't log - will try fallbacks

    # Fallback: Try nvidia-smi command line (works even if pynvml fails)
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            temp = int(result.stdout.strip().split('\n')[0])
            if 0 < temp < 150:
                return temp
    except Exception:
        pass  # nvidia-smi not available or failed

    # Fallback: Try WMI with LibreHardwareMonitor/OpenHardwareMonitor for GPU
    if WMI_AVAILABLE:
        for namespace in ["root\\LibreHardwareMonitor", "root\\OpenHardwareMonitor"]:
            try:
                w = wmi.WMI(namespace=namespace)
                sensors = w.Sensor()
                for sensor in sensors:
                    if sensor.SensorType == "Temperature" and "GPU" in sensor.Name:
                        if sensor.Value and sensor.Value > 0:
                            return int(sensor.Value)
            except Exception:
                pass  # Namespace not available

    return None


def get_cpu_temperature():
    """
    Get current CPU temperature in Celsius.
    Tries HardwareMonitor package, LibreHardwareMonitor (bundled), and WMI fallbacks.
    Returns None if temperature cannot be read.
    """
    global HWMON_COMPUTER, LHM_COMPUTER

    # Try HardwareMonitor package first (handles PawnIO driver automatically)
    if HWMON_AVAILABLE and is_admin():
        try:
            from HardwareMonitor.Hardware import Computer, HardwareType, SensorType

            if HWMON_COMPUTER is None:
                log("Initializing HardwareMonitor Computer object...", "TEMP")
                HWMON_COMPUTER = Computer()
                HWMON_COMPUTER.IsCpuEnabled = True
                HWMON_COMPUTER.Open()
                # Use visitor pattern to update all hardware
                HWMON_COMPUTER.Accept(HardwareUpdateVisitor())
                log("HardwareMonitor initialized successfully", "TEMP")

            # Update all hardware using visitor
            HWMON_COMPUTER.Accept(HardwareUpdateVisitor())

            # Look for CPU temperature
            for hardware in HWMON_COMPUTER.Hardware:
                if hardware.HardwareType == HardwareType.Cpu:
                    # Check all temperature sensors
                    for sensor in hardware.Sensors:
                        if sensor.SensorType == SensorType.Temperature:
                            try:
                                value = sensor.Value
                                if value is not None and float(value) > 0:
                                    return int(float(value))
                            except Exception:
                                pass
                    # Check subhardware
                    for subhardware in hardware.SubHardware:
                        for sensor in subhardware.Sensors:
                            if sensor.SensorType == SensorType.Temperature:
                                try:
                                    value = sensor.Value
                                    if value is not None and float(value) > 0:
                                        return int(float(value))
                                except Exception:
                                    pass
        except Exception as e:
            log(f"HardwareMonitor read failed: {e}", "TEMP")

    # Fallback: Try bundled LibreHardwareMonitorLib (requires admin privileges)
    if LHM_AVAILABLE and is_admin():
        try:
            from LibreHardwareMonitor.Hardware import Computer, HardwareType, SensorType

            if LHM_COMPUTER is None:
                log("Initializing LibreHardwareMonitor Computer object...", "TEMP")
                LHM_COMPUTER = Computer()
                LHM_COMPUTER.IsCpuEnabled = True
                LHM_COMPUTER.Open()
                # Single update cycle with brief delay
                for hardware in LHM_COMPUTER.Hardware:
                    hardware.Update()
                    for subhardware in hardware.SubHardware:
                        subhardware.Update()
                time.sleep(0.2)
                log("LibreHardwareMonitor initialized successfully", "TEMP")

            # Update all hardware
            for hardware in LHM_COMPUTER.Hardware:
                hardware.Update()
                for subhardware in hardware.SubHardware:
                    subhardware.Update()

            # Look for CPU temperature
            for hardware in LHM_COMPUTER.Hardware:
                if hardware.HardwareType == HardwareType.Cpu:
                    # Check all temperature sensors
                    for sensor in hardware.Sensors:
                        if sensor.SensorType == SensorType.Temperature:
                            # Try multiple ways to get the value (pythonnet nullable handling)
                            try:
                                value = sensor.Value
                                # Handle .NET nullable - try GetValueOrDefault if available
                                if hasattr(value, 'GetValueOrDefault'):
                                    value = value.GetValueOrDefault()
                                elif hasattr(value, 'Value'):
                                    value = value.Value
                                if value is not None and float(value) > 0:
                                    return int(float(value))
                            except Exception:
                                pass
                    # Check subhardware
                    for subhardware in hardware.SubHardware:
                        for sensor in subhardware.Sensors:
                            if sensor.SensorType == SensorType.Temperature:
                                try:
                                    value = sensor.Value
                                    if hasattr(value, 'GetValueOrDefault'):
                                        value = value.GetValueOrDefault()
                                    elif hasattr(value, 'Value'):
                                        value = value.Value
                                    if value is not None and float(value) > 0:
                                        return int(float(value))
                                except Exception:
                                    pass
        except Exception as e:
            log(f"LibreHardwareMonitorLib read failed: {e}", "TEMP")

    # Fallback: Try WMI with external LibreHardwareMonitor/OpenHardwareMonitor
    global CPU_TEMP_ERRORS_LOGGED
    if WMI_AVAILABLE:
        # Try LibreHardwareMonitor WMI
        try:
            w = wmi.WMI(namespace="root\\LibreHardwareMonitor")
            sensors = w.Sensor()
            for sensor in sensors:
                if sensor.SensorType == "Temperature" and "CPU" in sensor.Name:
                    if "Package" in sensor.Name or "Core" in sensor.Name:
                        return int(sensor.Value)
            for sensor in sensors:
                if sensor.SensorType == "Temperature" and "CPU" in sensor.Name:
                    return int(sensor.Value)
        except Exception:
            pass  # WMI namespace not available

        # Try OpenHardwareMonitor WMI
        try:
            w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            sensors = w.Sensor()
            for sensor in sensors:
                if sensor.SensorType == "Temperature" and "CPU" in sensor.Name:
                    if "Package" in sensor.Name or "Core" in sensor.Name:
                        return int(sensor.Value)
            for sensor in sensors:
                if sensor.SensorType == "Temperature" and "CPU" in sensor.Name:
                    return int(sensor.Value)
        except Exception:
            pass  # WMI namespace not available

        # Fallback: Try Windows native thermal zone (requires admin)
        if is_admin():
            try:
                w = wmi.WMI(namespace="root\\wmi")
                temps = w.MSAcpi_ThermalZoneTemperature()
                if temps:
                    # Convert from decikelvin to Celsius: (temp / 10) - 273.15
                    for temp in temps:
                        if hasattr(temp, 'CurrentTemperature') and temp.CurrentTemperature:
                            celsius = (temp.CurrentTemperature / 10.0) - 273.15
                            if 0 < celsius < 150:  # Sanity check for valid temp range
                                return int(celsius)
            except Exception:
                pass  # Thermal zone not available

    # Fallback: Try PowerShell Get-CimInstance for thermal zone
    if is_admin():
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 'Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature | '
                 'Select-Object -ExpandProperty CurrentTemperature | Select-Object -First 1'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                # Convert from decikelvin to Celsius
                decikelvin = float(result.stdout.strip())
                celsius = (decikelvin / 10.0) - 273.15
                if 0 < celsius < 150:
                    return int(celsius)
        except Exception:
            pass  # PowerShell method failed

    # Fallback: Try wmic command for thermal zone
    if is_admin():
        try:
            result = subprocess.run(
                ['wmic', '/namespace:\\\\root\\wmi', 'path', 'MSAcpi_ThermalZoneTemperature',
                 'get', 'CurrentTemperature', '/value'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and 'CurrentTemperature=' in result.stdout:
                # Parse "CurrentTemperature=XXXXX" format
                for line in result.stdout.split('\n'):
                    if 'CurrentTemperature=' in line:
                        decikelvin = float(line.split('=')[1].strip())
                        celsius = (decikelvin / 10.0) - 273.15
                        if 0 < celsius < 150:
                            return int(celsius)
        except Exception:
            pass  # wmic method failed

    # Log once that CPU temp is unavailable
    if not CPU_TEMP_ERRORS_LOGGED:
        log("CPU temperature monitoring unavailable on this system", "TEMP")
        CPU_TEMP_ERRORS_LOGGED = True

    return None


class TemperatureTracker:
    """
    Tracks CPU and GPU temperatures during a gaming session.
    Records starting temperatures and maximum temperatures reached.
    Supports temperature alerts when thresholds are exceeded (warning and critical levels).
    """

    def __init__(self):
        self.start_cpu_temp = None
        self.start_gpu_temp = None
        self.max_cpu_temp = None
        self.max_gpu_temp = None
        self._stop_event = None
        self._thread = None
        self._monitoring = False
        self._enable_cpu = False
        self._enable_gpu = True
        # Alert settings (warning and critical thresholds)
        self._enable_cpu_alert = False
        self._cpu_warning_threshold = 85
        self._cpu_critical_threshold = 95
        self._enable_gpu_alert = False
        self._gpu_warning_threshold = 80
        self._gpu_critical_threshold = 90
        # Track which alerts have been triggered this session
        self._cpu_warning_triggered = False
        self._cpu_critical_triggered = False
        self._gpu_warning_triggered = False
        self._gpu_critical_triggered = False
        self._game_name = None

    def start_monitoring(self, stop_event, enable_cpu=False, enable_gpu=True,
                         enable_cpu_alert=False, cpu_warning_threshold=85, cpu_critical_threshold=95,
                         enable_gpu_alert=False, gpu_warning_threshold=80, gpu_critical_threshold=90,
                         game_name=None):
        """Start temperature monitoring in a background thread."""
        if self._monitoring:
            return

        self.start_cpu_temp = None
        self.start_gpu_temp = None
        self.max_cpu_temp = None
        self.max_gpu_temp = None
        self._stop_event = stop_event
        self._monitoring = True
        self._enable_cpu = enable_cpu
        self._enable_gpu = enable_gpu
        # Alert settings (warning and critical thresholds)
        self._enable_cpu_alert = enable_cpu_alert
        self._cpu_warning_threshold = cpu_warning_threshold
        self._cpu_critical_threshold = cpu_critical_threshold
        self._enable_gpu_alert = enable_gpu_alert
        self._gpu_warning_threshold = gpu_warning_threshold
        self._gpu_critical_threshold = gpu_critical_threshold
        # Reset alert triggers for new session
        self._cpu_warning_triggered = False
        self._cpu_critical_triggered = False
        self._gpu_warning_triggered = False
        self._gpu_critical_triggered = False
        self._game_name = game_name

        # Only start monitoring if at least one thermal type is enabled
        if not enable_cpu and not enable_gpu:
            log("Temperature monitoring disabled (both CPU and GPU disabled)", "TEMP")
            self._monitoring = False
            return

        # Capture starting temperatures immediately
        if enable_cpu:
            self.start_cpu_temp = get_cpu_temperature()
            self.max_cpu_temp = self.start_cpu_temp
            if self.start_cpu_temp is not None:
                log(f"Starting CPU temp: {self.start_cpu_temp}°C", "TEMP")

        if enable_gpu:
            self.start_gpu_temp = get_gpu_temperature()
            self.max_gpu_temp = self.start_gpu_temp
            if self.start_gpu_temp is not None:
                log(f"Starting GPU temp: {self.start_gpu_temp}°C", "TEMP")

        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        enabled_types = []
        if enable_cpu:
            enabled_types.append("CPU")
        if enable_gpu:
            enabled_types.append("GPU")
        log(f"Temperature monitoring started ({', '.join(enabled_types)})", "TEMP")

    def stop_monitoring(self):
        """Stop temperature monitoring and return temperature data."""
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

        # Capture ending temperatures
        end_cpu_temp = get_cpu_temperature() if self._enable_cpu else None
        end_gpu_temp = get_gpu_temperature() if self._enable_gpu else None

        log(f"Temperature monitoring stopped. Start CPU: {self.start_cpu_temp}°C, End CPU: {end_cpu_temp}°C, "
            f"Start GPU: {self.start_gpu_temp}°C, End GPU: {end_gpu_temp}°C", "TEMP")
        return {
            'start_cpu': self.start_cpu_temp,
            'start_gpu': self.start_gpu_temp,
            'end_cpu': end_cpu_temp,
            'end_gpu': end_gpu_temp,
            'max_cpu': self.max_cpu_temp,
            'max_gpu': self.max_gpu_temp
        }

    def _play_critical_alert_sound(self):
        """Play the critical alert sound if available."""
        try:
            import winsound
            # Look for sound file in several locations
            sound_locations = [
                os.path.join(base_dir, 'sounds', 'critical_alert.wav'),
                os.path.join(os.path.dirname(base_dir), 'sounds', 'critical_alert.wav'),
                os.path.join(appdata_dir, 'sounds', 'critical_alert.wav')
            ]
            for sound_path in sound_locations:
                if os.path.exists(sound_path):
                    log(f"Playing critical alert sound: {sound_path}", "ALERT")
                    winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    return
            # Fallback to system beep if no custom sound found
            log("Critical alert sound file not found (sounds/critical_alert.wav), using system beep", "ALERT")
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception as e:
            log(f"Error playing critical alert sound: {e}", "ALERT")

    def _monitor_loop(self):
        """Background loop that polls temperatures every 10 seconds."""
        poll_interval = 10  # seconds

        while self._monitoring:
            # Get current temperatures (only if enabled)
            cpu_temp = get_cpu_temperature() if self._enable_cpu else None
            gpu_temp = get_gpu_temperature() if self._enable_gpu else None

            # Update max values
            if cpu_temp is not None:
                if self.max_cpu_temp is None or cpu_temp > self.max_cpu_temp:
                    self.max_cpu_temp = cpu_temp
                    log(f"New max CPU temp: {cpu_temp}°C", "TEMP")

            if gpu_temp is not None:
                if self.max_gpu_temp is None or gpu_temp > self.max_gpu_temp:
                    self.max_gpu_temp = gpu_temp
                    log(f"New max GPU temp: {gpu_temp}°C", "TEMP")

            # Check CPU temperature alerts (warning and critical levels)
            if self._enable_cpu_alert and cpu_temp is not None:
                game_info = f" while playing {self._game_name}" if self._game_name else ""
                # Check critical first (higher priority)
                if not self._cpu_critical_triggered and cpu_temp >= self._cpu_critical_threshold:
                    self._cpu_critical_triggered = True
                    self._cpu_warning_triggered = True  # Also mark warning as triggered
                    log(f"CPU CRITICAL alert: {cpu_temp}°C exceeds critical threshold of {self._cpu_critical_threshold}°C", "ALERT")
                    show_temperature_alert(f"⚠️ CRITICAL ALERT - CPU Temperature: {cpu_temp}°C{game_info}. "
                                           f"Critical threshold of {self._cpu_critical_threshold}°C exceeded!")
                    self._play_critical_alert_sound()
                # Check warning level
                elif not self._cpu_warning_triggered and cpu_temp >= self._cpu_warning_threshold:
                    self._cpu_warning_triggered = True
                    log(f"CPU warning alert: {cpu_temp}°C exceeds warning threshold of {self._cpu_warning_threshold}°C", "ALERT")
                    show_temperature_alert(f"CPU Temperature Warning: {cpu_temp}°C{game_info}. "
                                           f"Warning threshold of {self._cpu_warning_threshold}°C exceeded.")

            # Check GPU temperature alerts (warning and critical levels)
            if self._enable_gpu_alert and gpu_temp is not None:
                game_info = f" while playing {self._game_name}" if self._game_name else ""
                # Check critical first (higher priority)
                if not self._gpu_critical_triggered and gpu_temp >= self._gpu_critical_threshold:
                    self._gpu_critical_triggered = True
                    self._gpu_warning_triggered = True  # Also mark warning as triggered
                    log(f"GPU CRITICAL alert: {gpu_temp}°C exceeds critical threshold of {self._gpu_critical_threshold}°C", "ALERT")
                    show_temperature_alert(f"⚠️ CRITICAL ALERT - GPU Temperature: {gpu_temp}°C{game_info}. "
                                           f"Critical threshold of {self._gpu_critical_threshold}°C exceeded!")
                    self._play_critical_alert_sound()
                # Check warning level
                elif not self._gpu_warning_triggered and gpu_temp >= self._gpu_warning_threshold:
                    self._gpu_warning_triggered = True
                    log(f"GPU warning alert: {gpu_temp}°C exceeds warning threshold of {self._gpu_warning_threshold}°C", "ALERT")
                    show_temperature_alert(f"GPU Temperature Warning: {gpu_temp}°C{game_info}. "
                                           f"Warning threshold of {self._gpu_warning_threshold}°C exceeded.")

            # Wait for next poll or stop event
            if self._stop_event:
                if self._stop_event.wait(poll_interval):
                    break
            else:
                time.sleep(poll_interval)


# Global temperature tracker instance
temperature_tracker = TemperatureTracker()


# =============================================================================
# Temperature History Logging
# =============================================================================

# Directory for temperature history logs
TEMP_HISTORY_DIR = os.path.join(appdata_dir, 'temp_history')
os.makedirs(TEMP_HISTORY_DIR, exist_ok=True)


def get_temp_history_path(app_id):
    """Get the path to the temperature history file for a specific game."""
    return os.path.join(TEMP_HISTORY_DIR, f'{app_id}_temp_history.json')


def load_temp_history(app_id):
    """Load temperature history for a specific game. Returns dict with lifetime max temps."""
    history_path = get_temp_history_path(app_id)
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading temp history for app {app_id}: {e}", "TEMP")
    return {
        'app_id': app_id,
        'game_name': None,
        'lifetime_max_cpu': None,
        'lifetime_max_gpu': None,
        'sessions': []
    }


def save_temp_history(app_id, game_name, max_cpu, max_gpu):
    """Save temperature data for a game session and update lifetime maximums."""
    history = load_temp_history(app_id)

    # Update game name if we have it
    if game_name:
        history['game_name'] = game_name

    # Update lifetime maximums
    if max_cpu is not None:
        if history['lifetime_max_cpu'] is None or max_cpu > history['lifetime_max_cpu']:
            history['lifetime_max_cpu'] = max_cpu
            log(f"New lifetime max CPU temp for {game_name}: {max_cpu}°C", "TEMP")

    if max_gpu is not None:
        if history['lifetime_max_gpu'] is None or max_gpu > history['lifetime_max_gpu']:
            history['lifetime_max_gpu'] = max_gpu
            log(f"New lifetime max GPU temp for {game_name}: {max_gpu}°C", "TEMP")

    # Add session record
    session_record = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'max_cpu': max_cpu,
        'max_gpu': max_gpu
    }
    history['sessions'].append(session_record)

    # Keep only last 100 sessions to prevent file from growing too large
    if len(history['sessions']) > 100:
        history['sessions'] = history['sessions'][-100:]

    # Save to file
    history_path = get_temp_history_path(app_id)
    try:
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=2)
        log(f"Saved temp history for {game_name} (AppID: {app_id})", "TEMP")
    except Exception as e:
        log(f"Error saving temp history: {e}", "TEMP")

    return history


def get_lifetime_max_temps(app_id):
    """Get lifetime maximum temperatures for a specific game."""
    history = load_temp_history(app_id)
    return {
        'lifetime_max_cpu': history.get('lifetime_max_cpu'),
        'lifetime_max_gpu': history.get('lifetime_max_gpu')
    }


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
# Game Audio Control
# =============================================================================

def find_game_pids(game_folder):
    """Find process IDs for executables running from the game folder."""
    if not game_folder:
        return []
    log(f"Scanning for game processes in: {game_folder}", "PROCESS")
    pids = []
    base_procs = []
    for attempt in range(10):
        for proc in psutil.process_iter(['pid', 'exe']):
            try:
                exe = proc.info['exe']
                if exe and os.path.exists(exe):
                    try:
                        if os.path.commonpath([exe, game_folder]) == game_folder:
                            base_procs.append(proc)
                    except ValueError:
                        pass
            except Exception:
                pass
        if base_procs:
            break
        log(f"No game processes found yet (attempt {attempt + 1}/10)...", "PROCESS")
        time.sleep(1)

    for proc in base_procs:
        pids.append(proc.pid)
        try:
            children = proc.children(recursive=True)
            for child in children:
                pids.append(child.pid)
        except Exception:
            pass

    pids = list(set(pids))
    if pids:
        log(f"Found {len(pids)} game process(es)", "PROCESS")
    else:
        log("No game processes found", "PROCESS")
    return pids


def set_game_volume(game_pids, level):
    """Set volume for game processes (0-100) with retry logic."""
    if not game_pids:
        return
    log(f"Setting game volume to {level}% for {len(game_pids)} PID(s)...", "AUDIO")
    comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    try:
        level = max(0, min(100, level)) / 100.0
        max_attempts = 240  # 240 attempts × 0.5s = 120 seconds (2 min) max wait
        retry_delay = 0.5

        for attempt in range(max_attempts):
            sessions = AudioUtilities.GetAllSessions()
            set_count = 0
            for session in sessions:
                if session.ProcessId in game_pids:
                    if hasattr(session, 'SimpleAudioVolume'):
                        volume = session.SimpleAudioVolume
                        volume.SetMasterVolume(level, None)
                        set_count += 1

            if set_count > 0:
                log(f"Game volume set for {set_count} audio session(s)", "AUDIO")
                break
            else:
                if attempt < max_attempts - 1:
                    log(f"No audio sessions found (attempt {attempt + 1}/{max_attempts})...", "AUDIO")
                    time.sleep(retry_delay)
                else:
                    log("No audio sessions found after all attempts", "AUDIO")
    except Exception as e:
        log(f"Failed to set game volume: {e}", "ERROR")
    finally:
        comtypes.CoUninitialize()


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
            set_game_volume(game_pids, game_audio_level)
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
                            set_game_volume(game_pids, game_audio_level)
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