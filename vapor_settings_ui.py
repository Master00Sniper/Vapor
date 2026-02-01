# vapor_settings_ui.py
# Settings interface for Vapor - allows users to configure app management, audio, power, and more.

import os
import sys

# =============================================================================
# Single Instance Check
# =============================================================================

import win32event
import win32api
import winerror

# Prevent multiple settings windows from opening
mutex = win32event.CreateMutex(None, True, "Vapor_Settings_SingleInstance_Mutex")
if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
    print("Settings window is already open. Exiting.")
    sys.exit(0)

# =============================================================================
# Path Configuration
# =============================================================================

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(application_path)
sys.path.append(application_path)

# Import shared utilities (logging, constants, paths, settings)
from utils import (
    base_dir, appdata_dir, SETTINGS_FILE,
    TRAY_ICON_PATH, PROTECTED_PROCESSES, log,
    load_settings as load_settings_dict, save_settings as save_settings_dict,
    DEFAULT_SETTINGS, set_setting
)

# Import platform utilities (admin checks, PawnIO driver)
from platform_utils import (
    is_admin, is_winget_available, is_pawnio_installed,
    clear_pawnio_cache, install_pawnio_silent, install_pawnio_with_elevation
)

# Alias for backward compatibility with existing code
debug_log = log

# =============================================================================
# Imports
# =============================================================================

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import json
from PIL import Image, ImageTk
import psutil
import win32gui
import win32con
import win11toast
import ctypes
import subprocess
import tempfile
import shutil
import time

try:
    from updater import CURRENT_VERSION
except ImportError:
    CURRENT_VERSION = "Unknown"


# =============================================================================
# Vapor Restart Functions
# =============================================================================

def restart_vapor(main_pid, require_admin=False):
    """
    Restart the main Vapor process.

    Args:
        main_pid: PID of the main Vapor process to terminate before restart
        require_admin: If True and not already admin, will request elevation.
                      If False, restarts without elevation prompt.

    Uses a delayed start via PowerShell to avoid MEI folder cleanup errors.
    """
    debug_log(f"Restarting Vapor (main_pid={main_pid}, require_admin={require_admin})", "Restart")

    # Terminate current main process if running
    if main_pid:
        try:
            debug_log(f"Terminating main process {main_pid}", "Restart")
            main_process = psutil.Process(main_pid)
            main_process.terminate()
            main_process.wait(timeout=5)  # Wait for process to terminate
            debug_log("Main process terminated", "Restart")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
            debug_log(f"Could not terminate main process: {e}", "Restart")

    # Determine the executable path
    # Use VAPOR_EXE_PATH if available (passed from main process)
    vapor_exe_from_env = os.environ.get('VAPOR_EXE_PATH', '')
    executable = None
    args_part = ""
    working_dir = None

    if vapor_exe_from_env and os.path.exists(vapor_exe_from_env):
        # Use the path passed from the main Vapor process
        executable = vapor_exe_from_env
        working_dir = os.path.dirname(executable)
        debug_log(f"Using VAPOR_EXE_PATH: {executable}", "Restart")
    elif getattr(sys, 'frozen', False):
        # Fallback: try to find Vapor.exe in common locations
        # Note: sys.executable here is the settings UI exe in temp folder, not what we want
        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(sys.executable)), 'Vapor.exe'),
            os.path.join(os.getcwd(), 'Vapor.exe'),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                executable = path
                working_dir = os.path.dirname(executable)
                break
        if not executable:
            debug_log("ERROR: Could not find Vapor.exe for restart", "Restart")
            return False
    else:
        # Running from Python - use pythonw.exe to avoid console window
        python_dir = os.path.dirname(sys.executable)
        pythonw_exe = os.path.join(python_dir, 'pythonw.exe')
        if os.path.exists(pythonw_exe):
            executable = pythonw_exe
        else:
            executable = sys.executable
        # For Python mode, use the actual source directory (not temp MEI folder)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        main_script = os.path.join(script_dir, 'steam_game_detector.py')
        args_part = f' -ArgumentList \\"{main_script}\\"'
        working_dir = script_dir

    debug_log(f"Executable: {executable}", "Restart")
    debug_log(f"Working dir: {working_dir}", "Restart")
    debug_log(f"Already admin: {is_admin()}", "Restart")

    # Use PowerShell with a delay to start the new process
    # This ensures the old process (settings UI) has fully exited before new Vapor starts
    # The delay prevents "Failed to remove temporary directory" MEI folder errors
    ps_command = f'Start-Sleep -Seconds 2; Start-Process -FilePath \\"{executable}\\"{args_part}'

    try:
        # Only use "runas" if elevation is required AND we're not already admin
        # This avoids unnecessary UAC prompts
        need_elevation = require_admin and not is_admin()
        verb = "runas" if need_elevation else "open"
        debug_log(f"Using verb: {verb} (need_elevation={need_elevation})", "Restart")

        # Launch PowerShell hidden - it will wait 2 seconds then start Vapor
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            verb,
            "powershell.exe",
            f'-WindowStyle Hidden -Command "{ps_command}"',
            working_dir,
            0  # SW_HIDE
        )
        debug_log(f"ShellExecuteW result: {result}", "Restart")
        return result > 32  # ShellExecuteW returns > 32 on success
    except Exception as e:
        debug_log(f"Restart failed: {e}", "Restart")
        return False


# Backwards-compatible alias
def restart_vapor_as_admin(main_pid):
    """Restart Vapor with admin privileges. Use restart_vapor() for more control."""
    return restart_vapor(main_pid, require_admin=True)


# =============================================================================
# Icon Handling
# =============================================================================

def set_vapor_icon(window):
    """Set the Vapor icon on a window. Call this after window is created."""
    icon_path = os.path.join(base_dir, 'Images', 'exe_icon.ico')
    if not os.path.exists(icon_path):
        debug_log(f"Icon file not found: {icon_path}", "Icon")
        return

    def apply_icon():
        try:
            if window.winfo_exists():
                window.iconbitmap(icon_path)
        except Exception:
            pass

    # Try setting icon immediately
    try:
        window.iconbitmap(icon_path)
    except Exception:
        pass

    # CTkToplevel windows often need the icon set after they're fully rendered
    # Schedule multiple attempts to ensure it sticks
    try:
        window.after(10, apply_icon)
        window.after(50, apply_icon)
        window.after(100, apply_icon)
        window.after(200, apply_icon)
    except Exception:
        pass


# =============================================================================
# Vapor Styled Dialog
# =============================================================================

def show_vapor_dialog(title, message, dialog_type="info", buttons=None, parent=None):
    """
    Show a Vapor-themed dialog popup that matches the app's style.

    Args:
        title: Dialog window title
        message: Message text to display
        dialog_type: "info", "warning", "error", or "question"
        buttons: List of button configs, e.g. [{"text": "Yes", "value": True, "color": "green"}, ...]
                 If None, defaults to a single "OK" button
        parent: Parent window (optional)

    Returns:
        The value associated with the clicked button, or None if closed
    """
    result = [None]  # Use list to allow modification in nested function

    # Create popup window
    dialog = ctk.CTkToplevel(parent) if parent else ctk.CTk()
    dialog.withdraw()  # Hide while setting up
    dialog.title(f"Vapor - {title}")
    dialog.resizable(False, False)

    # Calculate size based on message length
    width = 500
    height = 320 + (message.count('\n') * 12)
    height = min(height, 500)  # Cap max height

    # Center on screen
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    dialog.geometry(f"{width}x{height}+{x}+{y}")

    # Make dialog modal
    if parent:
        dialog.transient(parent)
    dialog.grab_set()

    # Main content frame (expandable)
    content_frame = ctk.CTkFrame(master=dialog, fg_color="transparent")
    content_frame.pack(fill="both", expand=True, padx=25, pady=(25, 10))

    # Title label with appropriate color based on type
    title_colors = {
        "info": ("white", None),
        "warning": ("orange", None),
        "error": ("#ff6b6b", None),
        "question": ("white", None)
    }
    title_color = title_colors.get(dialog_type, ("white", None))[0]

    title_label = ctk.CTkLabel(
        master=content_frame,
        text=title,
        font=("Calibri", 21, "bold"),
        text_color=title_color
    )
    title_label.pack(pady=(0, 15))

    # Message label
    message_label = ctk.CTkLabel(
        master=content_frame,
        text=message,
        font=("Calibri", 13),
        justify="left",
        wraplength=450
    )
    message_label.pack(pady=(0, 10))

    # Separator line above buttons (matching settings UI style)
    separator = ctk.CTkFrame(master=dialog, height=2, fg_color="gray50")
    separator.pack(fill="x", padx=40, pady=(10, 0))

    # Button frame at bottom (matching settings UI style)
    button_frame = ctk.CTkFrame(master=dialog, fg_color="transparent")
    button_frame.pack(pady=20, fill='x', padx=40)

    # Default buttons if none specified
    if buttons is None:
        buttons = [{"text": "OK", "value": True, "color": "green"}]

    def make_button_callback(value):
        def callback():
            result[0] = value
            dialog.destroy()
        return callback

    # Create buttons centered in frame
    buttons_container = ctk.CTkFrame(master=button_frame, fg_color="transparent")
    buttons_container.pack(anchor="center")

    for btn_config in buttons:
        btn_text = btn_config.get("text", "OK")
        btn_value = btn_config.get("value", None)
        btn_color = btn_config.get("color", "gray")

        # Map color names to actual colors (matching Vapor settings UI style)
        color_map = {
            "green": ("green", "#228B22"),      # Match Save & Close button
            "red": ("#c9302c", "#a02622"),      # Match Stop Vapor button
            "gray": ("gray", "#555555"),
            "blue": ("#3498db", "#2980b9"),
            "orange": ("#f39c12", "#d68910")
        }
        fg_color, hover_color = color_map.get(btn_color, ("gray", "#555555"))

        btn = ctk.CTkButton(
            master=buttons_container,
            text=btn_text,
            command=make_button_callback(btn_value),
            width=150,
            height=35,
            corner_radius=10,
            fg_color=fg_color,
            hover_color=hover_color,
            font=("Calibri", 15)
        )
        btn.pack(side="left", padx=15)

    # Handle window close button (X)
    dialog.protocol("WM_DELETE_WINDOW", lambda: (result.__setitem__(0, None), dialog.destroy()))

    # Set icon before showing the dialog to avoid flash of default icon
    set_vapor_icon(dialog)
    dialog.update()

    # Show window and bring to front
    dialog.deiconify()
    dialog.lift()
    dialog.attributes('-topmost', True)
    dialog.after(100, lambda: dialog.attributes('-topmost', False))
    dialog.focus_force()

    # Wait for dialog to close
    if parent:
        dialog.wait_window()
    else:
        dialog.mainloop()

    return result[0]


# =============================================================================
# Built-in App Definitions
# =============================================================================

# Notification/messaging apps that can be closed during gaming
BUILT_IN_APPS = [
    {'display_name': 'WhatsApp', 'processes': ['WhatsApp.Root.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'whatsapp_icon.png')},
    {'display_name': 'Discord', 'processes': ['Discord.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'discord_icon.png')},
    {'display_name': 'Telegram', 'processes': ['Telegram.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'telegram_icon.png')},
    {'display_name': 'Microsoft Teams', 'processes': ['ms-teams.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'teams_icon.png')},
    {'display_name': 'Facebook Messenger', 'processes': ['Messenger.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'messenger_icon.png')},
    {'display_name': 'Slack', 'processes': ['slack.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'slack_icon.png')},
    {'display_name': 'Signal', 'processes': ['Signal.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'signal_icon.png')},
    {'display_name': 'WeChat', 'processes': ['WeChat.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'wechat_icon.png')}
]

# Resource-heavy apps organized by category
BUILT_IN_RESOURCE_APPS = [
    # Browsers (indices 0-3)
    {'display_name': 'Chrome', 'processes': ['chrome.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'chrome_icon.png')},
    {'display_name': 'Firefox', 'processes': ['firefox.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'firefox_icon.png')},
    {'display_name': 'Edge', 'processes': ['msedge.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'edge_icon.png')},
    {'display_name': 'Opera', 'processes': ['opera.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'opera_icon.png')},
    # Cloud/Media (indices 4-7)
    {'display_name': 'Spotify', 'processes': ['spotify.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'spotify_icon.png')},
    {'display_name': 'OneDrive', 'processes': ['OneDrive.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'onedrive_icon.png')},
    {'display_name': 'Google Drive', 'processes': ['GoogleDriveFS.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'googledrive_icon.png')},
    {'display_name': 'Dropbox', 'processes': ['Dropbox.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'dropbox_icon.png')},
    # Gaming Utilities (indices 8-11)
    {'display_name': 'Wallpaper Engine', 'processes': ['wallpaper64.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'wallpaperengine_icon.png')},
    {'display_name': 'iCUE', 'processes': ['iCUE.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'icue_icon.png')},
    {'display_name': 'Razer Synapse', 'processes': ['RazerCentralService.exe', 'Razer Synapse 3.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'razer_icon.png')},
    {'display_name': 'NZXT CAM', 'processes': ['NZXT CAM.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'nzxtcam_icon.png')}
]


# =============================================================================
# Settings Management
# =============================================================================

def load_settings():
    """Load settings from file or return defaults. Uses shared settings module."""
    return load_settings_dict()


def save_settings(selected_notification_apps, customs, selected_resource_apps, resource_customs, launch_startup,
                  launch_settings_on_start, close_on_startup, close_on_hotkey, relaunch_on_exit,
                  resource_close_on_startup, resource_close_on_hotkey, resource_relaunch_on_exit,
                  enable_playtime_summary, playtime_summary_mode, enable_debug_mode, system_audio_level,
                  enable_system_audio, game_audio_level, enable_game_audio, enable_during_power, during_power_plan,
                  enable_after_power, after_power_plan, enable_game_mode_start, enable_game_mode_end,
                  enable_cpu_thermal, enable_gpu_thermal, enable_cpu_temp_alert, cpu_temp_warning_threshold,
                  cpu_temp_critical_threshold, enable_gpu_temp_alert, gpu_temp_warning_threshold,
                  gpu_temp_critical_threshold):
    """Save all settings to the JSON configuration file."""
    # Build process lists from selected apps (UI-specific logic)
    notification_processes = []
    for app in BUILT_IN_APPS:
        if app['display_name'] in selected_notification_apps:
            notification_processes.extend(app['processes'])
    notification_processes.extend(customs)

    resource_processes = []
    for app in BUILT_IN_RESOURCE_APPS:
        if app['display_name'] in selected_resource_apps:
            resource_processes.extend(app['processes'])
    resource_processes.extend(resource_customs)

    # Build settings dict and save using shared module
    settings = {
        'notification_processes': notification_processes,
        'selected_notification_apps': selected_notification_apps,
        'custom_processes': customs,
        'resource_processes': resource_processes,
        'selected_resource_apps': selected_resource_apps,
        'custom_resource_processes': resource_customs,
        'launch_at_startup': launch_startup,
        'launch_settings_on_start': launch_settings_on_start,
        'close_on_startup': close_on_startup,
        'close_on_hotkey': close_on_hotkey,
        'relaunch_on_exit': relaunch_on_exit,
        'resource_close_on_startup': resource_close_on_startup,
        'resource_close_on_hotkey': resource_close_on_hotkey,
        'resource_relaunch_on_exit': resource_relaunch_on_exit,
        'enable_playtime_summary': enable_playtime_summary,
        'playtime_summary_mode': playtime_summary_mode,
        'enable_debug_mode': enable_debug_mode,
        'system_audio_level': system_audio_level,
        'enable_system_audio': enable_system_audio,
        'game_audio_level': game_audio_level,
        'enable_game_audio': enable_game_audio,
        'enable_during_power': enable_during_power,
        'during_power_plan': during_power_plan,
        'enable_after_power': enable_after_power,
        'after_power_plan': after_power_plan,
        'enable_game_mode_start': enable_game_mode_start,
        'enable_game_mode_end': enable_game_mode_end,
        'enable_cpu_thermal': enable_cpu_thermal,
        'enable_gpu_thermal': enable_gpu_thermal,
        'enable_cpu_temp_alert': enable_cpu_temp_alert,
        'cpu_temp_warning_threshold': cpu_temp_warning_threshold,
        'cpu_temp_critical_threshold': cpu_temp_critical_threshold,
        'enable_gpu_temp_alert': enable_gpu_temp_alert,
        'gpu_temp_warning_threshold': gpu_temp_warning_threshold,
        'gpu_temp_critical_threshold': gpu_temp_critical_threshold
    }
    save_settings_dict(settings)


def set_pending_pawnio_check(value=True):
    """Set or clear the pending PawnIO check flag in settings.
    This flag triggers automatic PawnIO installation prompt after admin restart."""
    debug_log(f"Setting pending_pawnio_check to {value}", "Settings")
    set_setting('pending_pawnio_check', value)


# =============================================================================
# Window Setup with Dynamic Height
# =============================================================================

root = ctk.CTk()
root.withdraw()  # Hide while setting up
root.title("Vapor Settings")

# Get screen dimensions (accounts for Windows scaling automatically via tkinter)
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

# Calculate dynamic window height based on available screen space
# Use 85% of screen height, with min 600 and max 1000
window_width = 700
window_height = int(screen_height * 0.85)
window_height = max(600, min(window_height, 1000))  # Clamp between 600-1000

# Center the window on screen
x = (screen_width - window_width) // 2
y = (screen_height - window_height) // 2

root.geometry(f"{window_width}x{window_height}+{x}+{y}")
root.resizable(False, False)

# Set window icon BEFORE showing window
icon_path = os.path.join(base_dir, 'Images', 'exe_icon.ico')
if os.path.exists(icon_path):
    try:
        root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Error setting icon: {e}")

root.deiconify()  # Show window
root.update()  # Process pending events to fully initialize window

# Bring window to front and give it focus
root.lift()
root.attributes('-topmost', True)
root.after(100, lambda: root.attributes('-topmost', False))
root.focus_force()

# =============================================================================
# Load Current Settings
# =============================================================================

current_settings = load_settings()
selected_notification_apps = current_settings.get('selected_notification_apps',
                                                  current_settings.get('selected_apps', []))
custom_processes = current_settings.get('custom_processes', [])
selected_resource_apps = current_settings.get('selected_resource_apps', [])
custom_resource_processes = current_settings.get('custom_resource_processes', [])
launch_at_startup = current_settings.get('launch_at_startup', False)
launch_settings_on_start = current_settings.get('launch_settings_on_start', True)
close_on_startup = current_settings.get('close_on_startup', True)
close_on_hotkey = current_settings.get('close_on_hotkey', False)
relaunch_on_exit = current_settings.get('relaunch_on_exit', True)
resource_close_on_startup = current_settings.get('resource_close_on_startup', True)
resource_close_on_hotkey = current_settings.get('resource_close_on_hotkey', False)
resource_relaunch_on_exit = current_settings.get('resource_relaunch_on_exit', True)
enable_playtime_summary = current_settings.get('enable_playtime_summary', True)
playtime_summary_mode = current_settings.get('playtime_summary_mode', 'brief')
enable_debug_mode = current_settings.get('enable_debug_mode', False)

# If debug mode is enabled, attach to parent's console (main Vapor process) instead of creating a new one
if enable_debug_mode:
    try:
        kernel32 = ctypes.windll.kernel32
        # ATTACH_PARENT_PROCESS = -1, attaches to the parent process's console
        ATTACH_PARENT_PROCESS = -1
        attached = kernel32.AttachConsole(ATTACH_PARENT_PROCESS)

        if attached:
            # Successfully attached to parent's console
            sys.stdout = open('CONOUT$', 'w')
            sys.stderr = open('CONOUT$', 'w')
            debug_log("Settings UI attached to main debug console", "Startup")
        else:
            # Parent doesn't have a console, just use log file
            debug_log("No parent console to attach to, using log file only", "Startup")

        debug_log(f"Settings UI started (main_pid from env: {os.environ.get('VAPOR_MAIN_PID', 'not set')})", "Startup")
        debug_log(f"Running as admin: {is_admin()}", "Startup")
        debug_log(f"Base directory: {base_dir}", "Startup")
        debug_log(f"Settings file: {SETTINGS_FILE}", "Startup")
    except Exception as e:
        pass  # Console attachment failed, continue without it

system_audio_level = current_settings.get('system_audio_level', 50)
enable_system_audio = current_settings.get('enable_system_audio', False)
game_audio_level = current_settings.get('game_audio_level', 50)
enable_game_audio = current_settings.get('enable_game_audio', False)
enable_during_power = current_settings.get('enable_during_power', False)
during_power_plan = current_settings.get('during_power_plan', 'High Performance')
enable_after_power = current_settings.get('enable_after_power', False)
after_power_plan = current_settings.get('after_power_plan', 'Balanced')
enable_game_mode_start = current_settings.get('enable_game_mode_start', False)
enable_game_mode_end = current_settings.get('enable_game_mode_end', False)
enable_cpu_thermal = current_settings.get('enable_cpu_thermal', False)
enable_gpu_thermal = current_settings.get('enable_gpu_thermal', True)
enable_cpu_temp_alert = current_settings.get('enable_cpu_temp_alert', False)
cpu_temp_warning_threshold = current_settings.get('cpu_temp_warning_threshold', 85)
cpu_temp_critical_threshold = current_settings.get('cpu_temp_critical_threshold', 95)
enable_gpu_temp_alert = current_settings.get('enable_gpu_temp_alert', False)
gpu_temp_warning_threshold = current_settings.get('gpu_temp_warning_threshold', 80)
gpu_temp_critical_threshold = current_settings.get('gpu_temp_critical_threshold', 90)

# Get main process PID for communication with main app
main_pid = None
if os.environ.get('VAPOR_MAIN_PID'):
    try:
        main_pid = int(os.environ.get('VAPOR_MAIN_PID'))
    except ValueError:
        pass
elif len(sys.argv) > 1:
    if sys.argv[1] == '--ui':
        if len(sys.argv) > 2:
            try:
                main_pid = int(sys.argv[2])
            except ValueError:
                pass
    else:
        try:
            main_pid = int(sys.argv[1])
        except ValueError:
            pass

# UI state tracking
switch_vars = {}
resource_switch_vars = {}

# =============================================================================
# Tab View Setup
# =============================================================================

tabview = ctk.CTkTabview(master=root)
tabview.pack(pady=10, padx=10, fill="both", expand=True)

notifications_tab = tabview.add("Notifications")
resources_tab = tabview.add(" Resources ")
thermal_tab = tabview.add("  Thermal  ")
preferences_tab = tabview.add("Preferences ")
help_tab = tabview.add("   Help   ")
about_tab = tabview.add("  About  ")

# =============================================================================
# Notifications Tab
# =============================================================================

notif_scroll_frame = ctk.CTkScrollableFrame(master=notifications_tab, fg_color="transparent")
notif_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

notification_title = ctk.CTkLabel(master=notif_scroll_frame, text="Notification Management",
                                  font=("Calibri", 25, "bold"))
notification_title.pack(pady=(10, 5), anchor='center')

notif_description = ctk.CTkLabel(master=notif_scroll_frame,
                                 text="Control which messaging and notification apps are closed when you start gaming.",
                                 font=("Calibri", 13), text_color="gray60")
notif_description.pack(pady=(0, 15), anchor='center')

notif_sep1 = ctk.CTkFrame(master=notif_scroll_frame, height=2, fg_color="gray50")
notif_sep1.pack(fill="x", padx=40, pady=10)

behavior_title = ctk.CTkLabel(master=notif_scroll_frame, text="Behavior Settings", font=("Calibri", 17, "bold"))
behavior_title.pack(pady=(10, 10), anchor='center')

options_frame = ctk.CTkFrame(master=notif_scroll_frame, fg_color="transparent")
options_frame.pack(pady=10, padx=20)

close_startup_label = ctk.CTkLabel(master=options_frame, text="Close Apps When Game Starts:",
                                   font=("Calibri", 14))
close_startup_label.grid(row=0, column=0, pady=8, padx=10, sticky='w')

close_startup_var = tk.StringVar(value="Enabled" if close_on_startup else "Disabled")
ctk.CTkRadioButton(master=options_frame, text="Enabled", variable=close_startup_var, value="Enabled",
                   font=("Calibri", 14)).grid(row=0, column=1, pady=8, padx=15)
ctk.CTkRadioButton(master=options_frame, text="Disabled", variable=close_startup_var, value="Disabled",
                   font=("Calibri", 14)).grid(row=0, column=2, pady=8, padx=15)

close_hotkey_label = ctk.CTkLabel(master=options_frame, text="Close Apps With Hotkey (Ctrl+Alt+K):",
                                  font=("Calibri", 14))
close_hotkey_label.grid(row=1, column=0, pady=8, padx=10, sticky='w')

close_hotkey_var = tk.StringVar(value="Enabled" if close_on_hotkey else "Disabled")
ctk.CTkRadioButton(master=options_frame, text="Enabled", variable=close_hotkey_var, value="Enabled",
                   font=("Calibri", 14)).grid(row=1, column=1, pady=8, padx=15)
ctk.CTkRadioButton(master=options_frame, text="Disabled", variable=close_hotkey_var, value="Disabled",
                   font=("Calibri", 14)).grid(row=1, column=2, pady=8, padx=15)

relaunch_exit_label = ctk.CTkLabel(master=options_frame, text="Relaunch Apps When Game Ends:",
                                   font=("Calibri", 14))
relaunch_exit_label.grid(row=2, column=0, pady=8, padx=10, sticky='w')

relaunch_exit_var = tk.StringVar(value="Enabled" if relaunch_on_exit else "Disabled")
ctk.CTkRadioButton(master=options_frame, text="Enabled", variable=relaunch_exit_var, value="Enabled",
                   font=("Calibri", 14)).grid(row=2, column=1, pady=8, padx=15)
ctk.CTkRadioButton(master=options_frame, text="Disabled", variable=relaunch_exit_var, value="Disabled",
                   font=("Calibri", 14)).grid(row=2, column=2, pady=8, padx=15)

notif_sep2 = ctk.CTkFrame(master=notif_scroll_frame, height=2, fg_color="gray50")
notif_sep2.pack(fill="x", padx=40, pady=15)

apps_subtitle = ctk.CTkLabel(master=notif_scroll_frame, text="Select Apps to Manage", font=("Calibri", 17, "bold"))
apps_subtitle.pack(pady=(10, 5), anchor='center')

apps_hint = ctk.CTkLabel(master=notif_scroll_frame,
                         text="Toggle the apps you want Vapor to close during gaming sessions.",
                         font=("Calibri", 12), text_color="gray60")
apps_hint.pack(pady=(0, 10), anchor='center')

app_frame = ctk.CTkFrame(master=notif_scroll_frame, fg_color="transparent")
app_frame.pack(pady=10, padx=10)

left_column = ctk.CTkFrame(master=app_frame, fg_color="transparent")
left_column.pack(side="left", padx=20)

right_column = ctk.CTkFrame(master=app_frame, fg_color="transparent")
right_column.pack(side="left", padx=20)

for i in range(4):
    app = BUILT_IN_APPS[i]
    display_name = app['display_name']
    icon_path = app['icon_path']

    row_frame = ctk.CTkFrame(master=left_column, fg_color="transparent")
    row_frame.pack(pady=6, anchor='w')

    if os.path.exists(icon_path):
        ctk_image = ctk.CTkImage(light_image=Image.open(icon_path), size=(26, 26))
        icon_label = ctk.CTkLabel(master=row_frame, image=ctk_image, text="")
        icon_label.pack(side="left", padx=5)
    else:
        ctk.CTkLabel(master=row_frame, text="*", font=("Calibri", 15)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_notification_apps)
    switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14))
    switch.pack(side="left")

for i in range(4, 8):
    app = BUILT_IN_APPS[i]
    display_name = app['display_name']
    icon_path = app['icon_path']

    row_frame = ctk.CTkFrame(master=right_column, fg_color="transparent")
    row_frame.pack(pady=6, anchor='w')

    if os.path.exists(icon_path):
        ctk_image = ctk.CTkImage(light_image=Image.open(icon_path), size=(26, 26))
        icon_label = ctk.CTkLabel(master=row_frame, image=ctk_image, text="")
        icon_label.pack(side="left", padx=5)
    else:
        ctk.CTkLabel(master=row_frame, text="*", font=("Calibri", 15)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_notification_apps)
    switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14))
    switch.pack(side="left")


def on_all_apps_toggle():
    """Toggle all notification apps on/off."""
    state = all_apps_var.get()
    for var in switch_vars.values():
        var.set(state)


all_apps_var = tk.BooleanVar(value=all(display_name in selected_notification_apps for display_name in
                                       [app['display_name'] for app in BUILT_IN_APPS]))

all_apps_switch = ctk.CTkSwitch(master=notif_scroll_frame, text="Toggle All Apps", variable=all_apps_var,
                                command=on_all_apps_toggle, font=("Calibri", 14))
all_apps_switch.pack(pady=10, anchor='center')

notif_sep3 = ctk.CTkFrame(master=notif_scroll_frame, height=2, fg_color="gray50")
notif_sep3.pack(fill="x", padx=40, pady=15)

custom_title = ctk.CTkLabel(master=notif_scroll_frame, text="Custom Processes", font=("Calibri", 17, "bold"))
custom_title.pack(pady=(10, 5), anchor='center')

custom_label = ctk.CTkLabel(master=notif_scroll_frame,
                            text="Add additional processes to close (comma-separated, e.g.: MyApp1.exe, MyApp2.exe)",
                            font=("Calibri", 12), text_color="gray60")
custom_label.pack(pady=(0, 10), anchor='center')

custom_entry = ctk.CTkEntry(master=notif_scroll_frame, width=550, font=("Calibri", 14),
                            placeholder_text="Enter custom process names...")
custom_entry.insert(0, ','.join(custom_processes))
custom_entry.pack(pady=(0, 20), anchor='center')

# =============================================================================
# Preferences Tab
# =============================================================================

pref_scroll_frame = ctk.CTkScrollableFrame(master=preferences_tab, fg_color="transparent")
pref_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

preferences_title = ctk.CTkLabel(master=pref_scroll_frame, text="Preferences", font=("Calibri", 25, "bold"))
preferences_title.pack(pady=(10, 5), anchor='center')

pref_description = ctk.CTkLabel(master=pref_scroll_frame,
                                text="Customize Vapor's behavior, audio settings, and power management options.",
                                font=("Calibri", 13), text_color="gray60")
pref_description.pack(pady=(0, 15), anchor='center')

pref_sep1 = ctk.CTkFrame(master=pref_scroll_frame, height=2, fg_color="gray50")
pref_sep1.pack(fill="x", padx=40, pady=10)

general_title = ctk.CTkLabel(master=pref_scroll_frame, text="General Settings", font=("Calibri", 17, "bold"))
general_title.pack(pady=(10, 10), anchor='center')

general_frame = ctk.CTkFrame(master=pref_scroll_frame, fg_color="transparent")
general_frame.pack(pady=5, padx=40, anchor='center')

launch_settings_on_start_var = tk.BooleanVar(value=launch_settings_on_start)
launch_settings_on_start_switch = ctk.CTkSwitch(master=general_frame, text="Open Settings Window on Vapor Start",
                                                variable=launch_settings_on_start_var, font=("Calibri", 14))
launch_settings_on_start_switch.pack(pady=5, anchor='w')

playtime_summary_var = tk.BooleanVar(value=enable_playtime_summary)
playtime_summary_switch = ctk.CTkSwitch(master=general_frame, text="Show Playtime Summary After Gaming",
                                        variable=playtime_summary_var, font=("Calibri", 14))
playtime_summary_switch.pack(pady=5, anchor='w')

# Playtime summary mode selection (Brief vs Detailed)
summary_mode_frame = ctk.CTkFrame(master=general_frame, fg_color="transparent")
summary_mode_frame.pack(pady=(0, 5), anchor='w', padx=(30, 0))

summary_mode_label = ctk.CTkLabel(master=summary_mode_frame, text="Summary Style:",
                                  font=("Calibri", 13))
summary_mode_label.pack(side="left", padx=(0, 10))

playtime_summary_mode_var = tk.StringVar(value=playtime_summary_mode)
ctk.CTkRadioButton(master=summary_mode_frame, text="Brief", variable=playtime_summary_mode_var,
                   value="brief", font=("Calibri", 13)).pack(side="left", padx=10)
ctk.CTkRadioButton(master=summary_mode_frame, text="Detailed", variable=playtime_summary_mode_var,
                   value="detailed", font=("Calibri", 13)).pack(side="left", padx=10)

startup_var = tk.BooleanVar(value=launch_at_startup)
startup_switch = ctk.CTkSwitch(master=general_frame, text="Launch Vapor at System Startup", variable=startup_var,
                               font=("Calibri", 14))
startup_switch.pack(pady=5, anchor='w')

debug_mode_var = tk.BooleanVar(value=enable_debug_mode)
debug_mode_switch = ctk.CTkSwitch(master=general_frame, text="Enable Debug Console Window",
                                  variable=debug_mode_var, font=("Calibri", 14))
debug_mode_switch.pack(pady=5, anchor='w')

pref_sep2 = ctk.CTkFrame(master=pref_scroll_frame, height=2, fg_color="gray50")
pref_sep2.pack(fill="x", padx=40, pady=15)

audio_title = ctk.CTkLabel(master=pref_scroll_frame, text="Audio Settings", font=("Calibri", 17, "bold"))
audio_title.pack(pady=(10, 5), anchor='center')

audio_hint = ctk.CTkLabel(master=pref_scroll_frame,
                          text="Automatically adjust volume levels when a game starts.",
                          font=("Calibri", 12), text_color="gray60")
audio_hint.pack(pady=(0, 10), anchor='center')

audio_frame = ctk.CTkFrame(master=pref_scroll_frame, fg_color="transparent")
audio_frame.pack(pady=10, anchor='center')

system_audio_column = ctk.CTkFrame(master=audio_frame, fg_color="transparent")
system_audio_column.pack(side="left", padx=40)

system_audio_label = ctk.CTkLabel(master=system_audio_column, text="System Volume", font=("Calibri", 15, "bold"))
system_audio_label.pack(anchor='center')

system_audio_slider_var = tk.IntVar(value=system_audio_level)
system_audio_slider = ctk.CTkSlider(master=system_audio_column, from_=0, to=100, number_of_steps=100,
                                    variable=system_audio_slider_var, width=180)
system_audio_slider.pack(pady=5, anchor='center')

system_current_value_label = ctk.CTkLabel(master=system_audio_column, text=f"{system_audio_level}%",
                                          font=("Calibri", 14))
system_current_value_label.pack(anchor='center')


def update_system_audio_label(value):
    """Update the system audio percentage display."""
    system_current_value_label.configure(text=f"{int(value)}%")


system_audio_slider.configure(command=update_system_audio_label)

enable_system_audio_var = tk.BooleanVar(value=enable_system_audio)
enable_system_audio_switch = ctk.CTkSwitch(master=system_audio_column, text="Enable", variable=enable_system_audio_var,
                                           font=("Calibri", 14))
enable_system_audio_switch.pack(pady=8, anchor='center')

game_audio_column = ctk.CTkFrame(master=audio_frame, fg_color="transparent")
game_audio_column.pack(side="left", padx=40)

game_audio_label = ctk.CTkLabel(master=game_audio_column, text="Game Volume", font=("Calibri", 15, "bold"))
game_audio_label.pack(anchor='center')

game_audio_slider_var = tk.IntVar(value=game_audio_level)
game_audio_slider = ctk.CTkSlider(master=game_audio_column, from_=0, to=100, number_of_steps=100,
                                  variable=game_audio_slider_var, width=180)
game_audio_slider.pack(pady=5, anchor='center')

game_current_value_label = ctk.CTkLabel(master=game_audio_column, text=f"{game_audio_level}%", font=("Calibri", 14))
game_current_value_label.pack(anchor='center')


def update_game_audio_label(value):
    """Update the game audio percentage display."""
    game_current_value_label.configure(text=f"{int(value)}%")


game_audio_slider.configure(command=update_game_audio_label)

enable_game_audio_var = tk.BooleanVar(value=enable_game_audio)
enable_game_audio_switch = ctk.CTkSwitch(master=game_audio_column, text="Enable", variable=enable_game_audio_var,
                                         font=("Calibri", 14))
enable_game_audio_switch.pack(pady=8, anchor='center')

pref_sep3 = ctk.CTkFrame(master=pref_scroll_frame, height=2, fg_color="gray50")
pref_sep3.pack(fill="x", padx=40, pady=15)

power_title = ctk.CTkLabel(master=pref_scroll_frame, text="Power Management", font=("Calibri", 17, "bold"))
power_title.pack(pady=(10, 5), anchor='center')

power_hint = ctk.CTkLabel(master=pref_scroll_frame,
                          text="Automatically switch power plans when gaming starts and ends.",
                          font=("Calibri", 12), text_color="gray60")
power_hint.pack(pady=(0, 10), anchor='center')

power_frame = ctk.CTkFrame(master=pref_scroll_frame, fg_color="transparent")
power_frame.pack(pady=10, anchor='center')

during_power_column = ctk.CTkFrame(master=power_frame, fg_color="transparent")
during_power_column.pack(side="left", padx=40)

during_power_label = ctk.CTkLabel(master=during_power_column, text="While Gaming", font=("Calibri", 15, "bold"))
during_power_label.pack(anchor='center')

during_power_var = tk.StringVar(value=during_power_plan)
during_power_combobox = ctk.CTkComboBox(master=during_power_column,
                                        values=["High Performance", "Balanced", "Power saver"],
                                        variable=during_power_var, width=160)
during_power_combobox.pack(pady=5, anchor='center')

enable_during_power_var = tk.BooleanVar(value=enable_during_power)
enable_during_power_switch = ctk.CTkSwitch(master=during_power_column, text="Enable", variable=enable_during_power_var,
                                           font=("Calibri", 14))
enable_during_power_switch.pack(pady=8, anchor='center')

after_power_column = ctk.CTkFrame(master=power_frame, fg_color="transparent")
after_power_column.pack(side="left", padx=40)

after_power_label = ctk.CTkLabel(master=after_power_column, text="After Gaming", font=("Calibri", 15, "bold"))
after_power_label.pack(anchor='center')

after_power_var = tk.StringVar(value=after_power_plan)
after_power_combobox = ctk.CTkComboBox(master=after_power_column,
                                       values=["High Performance", "Balanced", "Power saver"],
                                       variable=after_power_var, width=160)
after_power_combobox.pack(pady=5, anchor='center')

enable_after_power_var = tk.BooleanVar(value=enable_after_power)
enable_after_power_switch = ctk.CTkSwitch(master=after_power_column, text="Enable", variable=enable_after_power_var,
                                          font=("Calibri", 14))
enable_after_power_switch.pack(pady=8, anchor='center')

pref_sep4 = ctk.CTkFrame(master=pref_scroll_frame, height=2, fg_color="gray50")
pref_sep4.pack(fill="x", padx=40, pady=15)

game_mode_title = ctk.CTkLabel(master=pref_scroll_frame, text="Windows Game Mode", font=("Calibri", 17, "bold"))
game_mode_title.pack(pady=(10, 5), anchor='center')

game_mode_hint = ctk.CTkLabel(master=pref_scroll_frame,
                              text="Control Windows Game Mode automatically during gaming sessions.",
                              font=("Calibri", 12), text_color="gray60")
game_mode_hint.pack(pady=(0, 10), anchor='center')

game_mode_frame = ctk.CTkFrame(master=pref_scroll_frame, fg_color="transparent")
game_mode_frame.pack(pady=10, anchor='center')

enable_game_mode_start_var = tk.BooleanVar(value=enable_game_mode_start)
enable_game_mode_start_switch = ctk.CTkSwitch(master=game_mode_frame, text="Enable Game Mode When Game Starts",
                                              variable=enable_game_mode_start_var, font=("Calibri", 14))
enable_game_mode_start_switch.pack(pady=5, anchor='w')

enable_game_mode_end_var = tk.BooleanVar(value=enable_game_mode_end)
enable_game_mode_end_switch = ctk.CTkSwitch(master=game_mode_frame, text="Disable Game Mode When Game Ends",
                                            variable=enable_game_mode_end_var, font=("Calibri", 14))
enable_game_mode_end_switch.pack(pady=5, anchor='w')

# =============================================================================
# Thermal Tab
# =============================================================================

thermal_scroll_frame = ctk.CTkScrollableFrame(master=thermal_tab, fg_color="transparent")
thermal_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

thermal_main_title = ctk.CTkLabel(master=thermal_scroll_frame, text="Thermal Management", font=("Calibri", 25, "bold"))
thermal_main_title.pack(pady=(10, 5), anchor='center')

thermal_main_description = ctk.CTkLabel(master=thermal_scroll_frame,
                                        text="Monitor and track CPU and GPU temperatures during gaming sessions.",
                                        font=("Calibri", 13), text_color="gray60")
thermal_main_description.pack(pady=(0, 15), anchor='center')

thermal_sep1 = ctk.CTkFrame(master=thermal_scroll_frame, height=2, fg_color="gray50")
thermal_sep1.pack(fill="x", padx=40, pady=10)

# Temperature Monitoring Section
thermal_title = ctk.CTkLabel(master=thermal_scroll_frame, text="Temperature Monitoring", font=("Calibri", 17, "bold"))
thermal_title.pack(pady=(10, 5), anchor='center')

thermal_hint = ctk.CTkLabel(master=thermal_scroll_frame,
                            text="Track maximum CPU and GPU temperatures during gaming sessions.",
                            font=("Calibri", 12), text_color="gray60")
thermal_hint.pack(pady=(0, 10), anchor='center')

thermal_frame = ctk.CTkFrame(master=thermal_scroll_frame, fg_color="transparent")
thermal_frame.pack(pady=10, anchor='center')

enable_gpu_thermal_var = tk.BooleanVar(value=enable_gpu_thermal)
enable_gpu_thermal_switch = ctk.CTkSwitch(master=thermal_frame, text="Capture GPU Temperature",
                                          variable=enable_gpu_thermal_var, font=("Calibri", 14))
enable_gpu_thermal_switch.pack(pady=5, anchor='w')

enable_cpu_thermal_var = tk.BooleanVar(value=enable_cpu_thermal)
enable_cpu_thermal_switch = ctk.CTkSwitch(master=thermal_frame, text="Capture CPU Temperature",
                                          variable=enable_cpu_thermal_var, font=("Calibri", 14))
enable_cpu_thermal_switch.pack(pady=5, anchor='w')

cpu_thermal_disclaimer = ctk.CTkLabel(master=thermal_frame,
                                      text="Note: CPU temperature monitoring requires administrator privileges.\n"
                                           "Vapor will prompt for admin access when this option is enabled.",
                                      font=("Calibri", 11), text_color="orange", justify="left")
cpu_thermal_disclaimer.pack(pady=(5, 0), anchor='w')

# Temperature Alerts Section
thermal_sep2 = ctk.CTkFrame(master=thermal_scroll_frame, height=2, fg_color="gray50")
thermal_sep2.pack(fill="x", padx=40, pady=15)

thermal_alerts_title = ctk.CTkLabel(master=thermal_scroll_frame, text="Temperature Alerts", font=("Calibri", 17, "bold"))
thermal_alerts_title.pack(pady=(10, 5), anchor='center')

thermal_alerts_hint = ctk.CTkLabel(master=thermal_scroll_frame,
                                   text="Get notified when temperatures exceed thresholds during gaming.\n"
                                        "Warning alerts are silent. Critical alerts play a sound.",
                                   font=("Calibri", 12), text_color="gray60", justify="center")
thermal_alerts_hint.pack(pady=(0, 10), anchor='center')

thermal_alerts_frame = ctk.CTkFrame(master=thermal_scroll_frame, fg_color="transparent")
thermal_alerts_frame.pack(pady=10, anchor='center')

# GPU Temperature Alerts
gpu_alert_header = ctk.CTkLabel(master=thermal_alerts_frame, text="GPU Alerts", font=("Calibri", 14, "bold"))
gpu_alert_header.pack(pady=(5, 5), anchor='w')

gpu_alert_row = ctk.CTkFrame(master=thermal_alerts_frame, fg_color="transparent")
gpu_alert_row.pack(pady=5, fill='x')

enable_gpu_temp_alert_var = tk.BooleanVar(value=enable_gpu_temp_alert)
enable_gpu_temp_alert_switch = ctk.CTkSwitch(master=gpu_alert_row, text="Enable",
                                              variable=enable_gpu_temp_alert_var, font=("Calibri", 13))
enable_gpu_temp_alert_switch.pack(side='left', padx=(0, 20))

gpu_warning_label = ctk.CTkLabel(master=gpu_alert_row, text="Warning:", font=("Calibri", 13))
gpu_warning_label.pack(side='left', padx=(0, 5))

gpu_temp_warning_threshold_var = tk.StringVar(value=str(gpu_temp_warning_threshold))
gpu_warning_entry = ctk.CTkEntry(master=gpu_alert_row, textvariable=gpu_temp_warning_threshold_var,
                                  width=45, font=("Calibri", 13))
gpu_warning_entry.pack(side='left', padx=(0, 3))

gpu_warning_unit = ctk.CTkLabel(master=gpu_alert_row, text="°C", font=("Calibri", 13))
gpu_warning_unit.pack(side='left', padx=(0, 15))

gpu_critical_label = ctk.CTkLabel(master=gpu_alert_row, text="Critical:", font=("Calibri", 13), text_color="#ff6b6b")
gpu_critical_label.pack(side='left', padx=(0, 5))

gpu_temp_critical_threshold_var = tk.StringVar(value=str(gpu_temp_critical_threshold))
gpu_critical_entry = ctk.CTkEntry(master=gpu_alert_row, textvariable=gpu_temp_critical_threshold_var,
                                   width=45, font=("Calibri", 13))
gpu_critical_entry.pack(side='left', padx=(0, 3))

gpu_critical_unit = ctk.CTkLabel(master=gpu_alert_row, text="°C", font=("Calibri", 13))
gpu_critical_unit.pack(side='left')

# CPU Temperature Alerts
cpu_alert_header = ctk.CTkLabel(master=thermal_alerts_frame, text="CPU Alerts", font=("Calibri", 14, "bold"))
cpu_alert_header.pack(pady=(15, 5), anchor='w')

cpu_alert_row = ctk.CTkFrame(master=thermal_alerts_frame, fg_color="transparent")
cpu_alert_row.pack(pady=5, fill='x')

enable_cpu_temp_alert_var = tk.BooleanVar(value=enable_cpu_temp_alert)
enable_cpu_temp_alert_switch = ctk.CTkSwitch(master=cpu_alert_row, text="Enable",
                                              variable=enable_cpu_temp_alert_var, font=("Calibri", 13))
enable_cpu_temp_alert_switch.pack(side='left', padx=(0, 20))

cpu_warning_label = ctk.CTkLabel(master=cpu_alert_row, text="Warning:", font=("Calibri", 13))
cpu_warning_label.pack(side='left', padx=(0, 5))

cpu_temp_warning_threshold_var = tk.StringVar(value=str(cpu_temp_warning_threshold))
cpu_warning_entry = ctk.CTkEntry(master=cpu_alert_row, textvariable=cpu_temp_warning_threshold_var,
                                  width=45, font=("Calibri", 13))
cpu_warning_entry.pack(side='left', padx=(0, 3))

cpu_warning_unit = ctk.CTkLabel(master=cpu_alert_row, text="°C", font=("Calibri", 13))
cpu_warning_unit.pack(side='left', padx=(0, 15))

cpu_critical_label = ctk.CTkLabel(master=cpu_alert_row, text="Critical:", font=("Calibri", 13), text_color="#ff6b6b")
cpu_critical_label.pack(side='left', padx=(0, 5))

cpu_temp_critical_threshold_var = tk.StringVar(value=str(cpu_temp_critical_threshold))
cpu_critical_entry = ctk.CTkEntry(master=cpu_alert_row, textvariable=cpu_temp_critical_threshold_var,
                                   width=45, font=("Calibri", 13))
cpu_critical_entry.pack(side='left', padx=(0, 3))

cpu_critical_unit = ctk.CTkLabel(master=cpu_alert_row, text="°C", font=("Calibri", 13))
cpu_critical_unit.pack(side='left')

thermal_alerts_note = ctk.CTkLabel(master=thermal_alerts_frame,
                                   text="Each alert level triggers once per gaming session.",
                                   font=("Calibri", 11), text_color="gray60")
thermal_alerts_note.pack(pady=(15, 0), anchor='w')

# =============================================================================
# Resources Tab
# =============================================================================

res_scroll_frame = ctk.CTkScrollableFrame(master=resources_tab, fg_color="transparent")
res_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

resource_title = ctk.CTkLabel(master=res_scroll_frame, text="Resource Management", font=("Calibri", 25, "bold"))
resource_title.pack(pady=(10, 5), anchor='center')

res_description = ctk.CTkLabel(master=res_scroll_frame,
                               text="Control which resource-intensive apps are closed to free up system resources during gaming.",
                               font=("Calibri", 13), text_color="gray60")
res_description.pack(pady=(0, 15), anchor='center')

res_sep1 = ctk.CTkFrame(master=res_scroll_frame, height=2, fg_color="gray50")
res_sep1.pack(fill="x", padx=40, pady=10)

res_behavior_title = ctk.CTkLabel(master=res_scroll_frame, text="Behavior Settings", font=("Calibri", 17, "bold"))
res_behavior_title.pack(pady=(10, 10), anchor='center')

resource_options_frame = ctk.CTkFrame(master=res_scroll_frame, fg_color="transparent")
resource_options_frame.pack(pady=10, padx=20)

resource_close_startup_label = ctk.CTkLabel(master=resource_options_frame,
                                            text="Close Apps When Game Starts:",
                                            font=("Calibri", 14))
resource_close_startup_label.grid(row=0, column=0, pady=8, padx=10, sticky='w')

resource_close_startup_var = tk.StringVar(value="Enabled" if resource_close_on_startup else "Disabled")
ctk.CTkRadioButton(master=resource_options_frame, text="Enabled", variable=resource_close_startup_var, value="Enabled",
                   font=("Calibri", 14)).grid(row=0, column=1, pady=8, padx=15)
ctk.CTkRadioButton(master=resource_options_frame, text="Disabled", variable=resource_close_startup_var,
                   value="Disabled", font=("Calibri", 14)).grid(row=0, column=2, pady=8, padx=15)

resource_close_hotkey_label = ctk.CTkLabel(master=resource_options_frame,
                                           text="Close Apps With Hotkey (Ctrl+Alt+K):", font=("Calibri", 14))
resource_close_hotkey_label.grid(row=1, column=0, pady=8, padx=10, sticky='w')

resource_close_hotkey_var = tk.StringVar(value="Enabled" if resource_close_on_hotkey else "Disabled")
ctk.CTkRadioButton(master=resource_options_frame, text="Enabled", variable=resource_close_hotkey_var, value="Enabled",
                   font=("Calibri", 14)).grid(row=1, column=1, pady=8, padx=15)
ctk.CTkRadioButton(master=resource_options_frame, text="Disabled", variable=resource_close_hotkey_var, value="Disabled",
                   font=("Calibri", 14)).grid(row=1, column=2, pady=8, padx=15)

resource_relaunch_exit_label = ctk.CTkLabel(master=resource_options_frame,
                                            text="Relaunch Apps When Game Ends:",
                                            font=("Calibri", 14))
resource_relaunch_exit_label.grid(row=2, column=0, pady=8, padx=10, sticky='w')

resource_relaunch_exit_var = tk.StringVar(value="Enabled" if resource_relaunch_on_exit else "Disabled")
ctk.CTkRadioButton(master=resource_options_frame, text="Enabled", variable=resource_relaunch_exit_var, value="Enabled",
                   font=("Calibri", 14)).grid(row=2, column=1, pady=8, padx=15)
ctk.CTkRadioButton(master=resource_options_frame, text="Disabled", variable=resource_relaunch_exit_var,
                   value="Disabled", font=("Calibri", 14)).grid(row=2, column=2, pady=8, padx=15)

res_sep2 = ctk.CTkFrame(master=res_scroll_frame, height=2, fg_color="gray50")
res_sep2.pack(fill="x", padx=40, pady=15)

resource_apps_subtitle = ctk.CTkLabel(master=res_scroll_frame, text="Select Apps to Manage",
                                      font=("Calibri", 17, "bold"))
resource_apps_subtitle.pack(pady=(10, 5), anchor='center')

res_apps_hint = ctk.CTkLabel(master=res_scroll_frame,
                             text="Toggle the resource-heavy apps you want Vapor to close during gaming sessions.",
                             font=("Calibri", 12), text_color="gray60")
res_apps_hint.pack(pady=(0, 10), anchor='center')

resource_app_frame = ctk.CTkFrame(master=res_scroll_frame, fg_color="transparent")
resource_app_frame.pack(pady=10, padx=10)

resource_left_column = ctk.CTkFrame(master=resource_app_frame, fg_color="transparent")
resource_left_column.pack(side="left", padx=10)

resource_middle_column = ctk.CTkFrame(master=resource_app_frame, fg_color="transparent")
resource_middle_column.pack(side="left", padx=10)

resource_right_column = ctk.CTkFrame(master=resource_app_frame, fg_color="transparent")
resource_right_column.pack(side="left", padx=10)

# Browsers column (indices 0-3)
for i in range(4):
    app = BUILT_IN_RESOURCE_APPS[i]
    display_name = app['display_name']
    icon_path = app['icon_path']

    row_frame = ctk.CTkFrame(master=resource_left_column, fg_color="transparent")
    row_frame.pack(pady=6, anchor='w')

    if os.path.exists(icon_path):
        ctk_image = ctk.CTkImage(light_image=Image.open(icon_path), size=(26, 26))
        icon_label = ctk.CTkLabel(master=row_frame, image=ctk_image, text="")
        icon_label.pack(side="left", padx=5)
    else:
        ctk.CTkLabel(master=row_frame, text="*", font=("Calibri", 15)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_resource_apps)
    resource_switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14))
    switch.pack(side="left")

# Cloud/Media column (indices 4-7)
for i in range(4, 8):
    app = BUILT_IN_RESOURCE_APPS[i]
    display_name = app['display_name']
    icon_path = app['icon_path']

    row_frame = ctk.CTkFrame(master=resource_middle_column, fg_color="transparent")
    row_frame.pack(pady=6, anchor='w')

    if os.path.exists(icon_path):
        ctk_image = ctk.CTkImage(light_image=Image.open(icon_path), size=(26, 26))
        icon_label = ctk.CTkLabel(master=row_frame, image=ctk_image, text="")
        icon_label.pack(side="left", padx=5)
    else:
        ctk.CTkLabel(master=row_frame, text="*", font=("Calibri", 15)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_resource_apps)
    resource_switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14))
    switch.pack(side="left")

# Gaming Utilities column (indices 8-11)
for i in range(8, 12):
    app = BUILT_IN_RESOURCE_APPS[i]
    display_name = app['display_name']
    icon_path = app['icon_path']

    row_frame = ctk.CTkFrame(master=resource_right_column, fg_color="transparent")
    row_frame.pack(pady=6, anchor='w')

    if os.path.exists(icon_path):
        ctk_image = ctk.CTkImage(light_image=Image.open(icon_path), size=(26, 26))
        icon_label = ctk.CTkLabel(master=row_frame, image=ctk_image, text="")
        icon_label.pack(side="left", padx=5)
    else:
        ctk.CTkLabel(master=row_frame, text="*", font=("Calibri", 15)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_resource_apps)
    resource_switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14))
    switch.pack(side="left")


def on_resource_all_apps_toggle():
    """Toggle all resource apps on/off."""
    state = resource_all_apps_var.get()
    for var in resource_switch_vars.values():
        var.set(state)


resource_all_apps_var = tk.BooleanVar(value=all(display_name in selected_resource_apps for display_name in
                                                [app['display_name'] for app in BUILT_IN_RESOURCE_APPS]))

resource_all_apps_switch = ctk.CTkSwitch(master=res_scroll_frame, text="Toggle All Apps",
                                         variable=resource_all_apps_var,
                                         command=on_resource_all_apps_toggle, font=("Calibri", 14))
resource_all_apps_switch.pack(pady=10, anchor='center')

res_sep3 = ctk.CTkFrame(master=res_scroll_frame, height=2, fg_color="gray50")
res_sep3.pack(fill="x", padx=40, pady=15)

res_custom_title = ctk.CTkLabel(master=res_scroll_frame, text="Custom Processes", font=("Calibri", 17, "bold"))
res_custom_title.pack(pady=(10, 5), anchor='center')

custom_resource_label = ctk.CTkLabel(master=res_scroll_frame,
                                     text="Add additional processes to close (comma-separated, e.g.: MyApp1.exe, MyApp2.exe)",
                                     font=("Calibri", 12), text_color="gray60")
custom_resource_label.pack(pady=(0, 10), anchor='center')

custom_resource_entry = ctk.CTkEntry(master=res_scroll_frame, width=550, font=("Calibri", 14),
                                     placeholder_text="Enter custom process names...")
custom_resource_entry.insert(0, ','.join(custom_resource_processes))
custom_resource_entry.pack(pady=(0, 20), anchor='center')

# =============================================================================
# Help Tab
# =============================================================================

help_scroll_frame = ctk.CTkScrollableFrame(master=help_tab, fg_color="transparent")
help_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

help_title = ctk.CTkLabel(master=help_scroll_frame, text="Help & Support", font=("Calibri", 25, "bold"))
help_title.pack(pady=(10, 5), anchor='center')

help_description = ctk.CTkLabel(master=help_scroll_frame,
                                text="Get help with Vapor, learn how it works, and troubleshoot common issues.",
                                font=("Calibri", 13), text_color="gray60")
help_description.pack(pady=(0, 15), anchor='center')

help_sep1 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
help_sep1.pack(fill="x", padx=40, pady=10)

how_title = ctk.CTkLabel(master=help_scroll_frame, text="How Vapor Works", font=("Calibri", 17, "bold"))
how_title.pack(pady=(10, 10), anchor='center')

how_text = """Vapor runs quietly in your system tray and monitors Steam for game launches. When you start 
a Steam game, Vapor automatically:

  *  Closes notification apps (like Discord, Slack, Teams) to prevent interruptions
  *  Closes resource-heavy apps (like browsers, cloud sync) to free up RAM and CPU
  *  Adjusts your audio levels (if enabled)
  *  Switches your power plan (if enabled)
  *  Enables Windows Game Mode (if enabled)

When you exit your game, Vapor reverses these changes and relaunches your closed apps."""

how_label = ctk.CTkLabel(master=help_scroll_frame, text=how_text, font=("Calibri", 13),
                         wraplength=580, justify="left")
how_label.pack(pady=10, anchor='center')

help_sep2 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
help_sep2.pack(fill="x", padx=40, pady=15)

shortcuts_title = ctk.CTkLabel(master=help_scroll_frame, text="Keyboard Shortcuts", font=("Calibri", 17, "bold"))
shortcuts_title.pack(pady=(10, 10), anchor='center')

shortcuts_text = """Ctrl + Alt + K  -  Manually close all selected notification and resource apps

This hotkey works independently of game detection. When enabled in the Notifications 
or Resources tab, pressing this combination will immediately close all toggled apps 
in that category. This is useful for quickly silencing distractions before a meeting, 
stream, or any focus session - even when you're not gaming."""

shortcuts_label = ctk.CTkLabel(master=help_scroll_frame, text=shortcuts_text, font=("Calibri", 13),
                               wraplength=580, justify="left")
shortcuts_label.pack(pady=10, anchor='center')

help_sep3 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
help_sep3.pack(fill="x", padx=40, pady=15)

trouble_title = ctk.CTkLabel(master=help_scroll_frame, text="Troubleshooting", font=("Calibri", 17, "bold"))
trouble_title.pack(pady=(10, 10), anchor='center')

trouble_text = """If Vapor isn't working as expected, try these steps:

  *  Make sure Steam is running before launching games
  *  Check that the apps you want managed are toggled ON in the Notifications/Resources tabs
  *  Ensure Vapor is running (look for the icon in your system tray)
  *  Try clicking "Reset to Defaults" below to restore default settings

If issues persist, enable Debug Mode in Preferences to see detailed logs."""

trouble_label = ctk.CTkLabel(master=help_scroll_frame, text=trouble_text, font=("Calibri", 13),
                             wraplength=580, justify="left")
trouble_label.pack(pady=10, anchor='center')

help_sep4 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
help_sep4.pack(fill="x", padx=40, pady=15)

reset_title = ctk.CTkLabel(master=help_scroll_frame, text="Reset Settings", font=("Calibri", 17, "bold"))
reset_title.pack(pady=(10, 5), anchor='center')

reset_hint = ctk.CTkLabel(master=help_scroll_frame,
                          text="Restore all settings to their default values.",
                          font=("Calibri", 12), text_color="gray60")
reset_hint.pack(pady=(0, 10), anchor='center')


def reset_settings_and_restart():
    """Delete settings file and restart Vapor."""
    debug_log("Reset settings requested", "Reset")
    response = show_vapor_dialog(
        title="Reset Settings",
        message="This will delete all settings and restart Vapor.\n\n"
                "Your settings will be reset to defaults.\n"
                "Are you sure?",
        dialog_type="warning",
        buttons=[
            {"text": "Reset & Restart", "value": True, "color": "#c9302c"},
            {"text": "Cancel", "value": False, "color": "gray"}
        ],
        parent=root
    )

    if response:
        debug_log("User confirmed reset settings", "Reset")
        # Delete settings file
        try:
            if os.path.exists(SETTINGS_FILE):
                os.remove(SETTINGS_FILE)
                debug_log(f"Deleted settings file: {SETTINGS_FILE}", "Reset")
        except Exception as e:
            debug_log(f"Error deleting settings: {e}", "Reset")

        # Restart Vapor
        win11toast.notify(body="Settings reset. Restarting Vapor...", app_id='Vapor - Streamline Gaming',
                          duration='short', icon=TRAY_ICON_PATH, audio={'silent': 'true'})

        restart_vapor(main_pid, require_admin=False)
        root.destroy()
    else:
        debug_log("User cancelled reset settings", "Reset")


def reset_all_data_and_restart():
    """Delete settings file and all temperature data, then restart Vapor."""
    debug_log("Reset all data requested", "Reset")
    response = show_vapor_dialog(
        title="Reset All Data",
        message="This will delete ALL Vapor data including:\n\n"
                "• All settings\n"
                "• All temperature history\n"
                "• Lifetime max temperatures for all games\n\n"
                "This cannot be undone. Are you sure?",
        dialog_type="warning",
        buttons=[
            {"text": "Delete All & Restart", "value": True, "color": "#c9302c"},
            {"text": "Cancel", "value": False, "color": "gray"}
        ],
        parent=root
    )

    if response:
        debug_log("User confirmed reset all data", "Reset")
        # Delete settings file
        try:
            if os.path.exists(SETTINGS_FILE):
                os.remove(SETTINGS_FILE)
                debug_log(f"Deleted settings file: {SETTINGS_FILE}", "Reset")
        except Exception as e:
            debug_log(f"Error deleting settings: {e}", "Reset")

        # Delete temperature history folder
        temp_history_dir = os.path.join(appdata_dir, 'temp_history')
        try:
            if os.path.exists(temp_history_dir):
                shutil.rmtree(temp_history_dir)
                debug_log(f"Deleted temp history folder: {temp_history_dir}", "Reset")
        except Exception as e:
            debug_log(f"Error deleting temp history: {e}", "Reset")

        # Restart Vapor
        win11toast.notify(body="All data deleted. Restarting Vapor...", app_id='Vapor - Streamline Gaming',
                          duration='short', icon=TRAY_ICON_PATH, audio={'silent': 'true'})

        restart_vapor(main_pid, require_admin=False)
        root.destroy()
    else:
        debug_log("User cancelled reset all data", "Reset")


# Create a frame to hold both reset buttons side by side
reset_buttons_frame = ctk.CTkFrame(master=help_scroll_frame, fg_color="transparent")
reset_buttons_frame.pack(pady=(5, 20), anchor='center')

rebuild_button = ctk.CTkButton(master=reset_buttons_frame, text="Reset Settings", command=reset_settings_and_restart,
                               corner_radius=10,
                               fg_color="#c9302c", hover_color="#a02622", text_color="white", width=160,
                               font=("Calibri", 14))
rebuild_button.pack(side='left', padx=5)

reset_all_button = ctk.CTkButton(master=reset_buttons_frame, text="Reset All Data", command=reset_all_data_and_restart,
                                 corner_radius=10,
                                 fg_color="#8b0000", hover_color="#5c0000", text_color="white", width=160,
                                 font=("Calibri", 14))
reset_all_button.pack(side='left', padx=5)

# =============================================================================
# About Tab
# =============================================================================

about_scroll_frame = ctk.CTkScrollableFrame(master=about_tab, fg_color="transparent")
about_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

about_title = ctk.CTkLabel(master=about_scroll_frame, text="Vapor - Open Beta Release", font=("Calibri", 29, "bold"))
about_title.pack(pady=(10, 5), anchor='center')

version_label = ctk.CTkLabel(master=about_scroll_frame, text=f"Version {CURRENT_VERSION}", font=("Calibri", 15))
version_label.pack(pady=(0, 15), anchor='center')

description_text = """Vapor is a lightweight utility designed to enhance your gaming experience on Windows. 
It automatically detects when you launch a Steam game and optimizes your system by closing 
distracting notification apps and resource-heavy applications. When you're done gaming, 
Vapor seamlessly relaunches your closed apps, so you can pick up right where you left off.

Features include customizable app management, audio controls, power plan switching, 
Windows Game Mode integration, and playtime tracking with session summaries."""

description_label = ctk.CTkLabel(master=about_scroll_frame, text=description_text, font=("Calibri", 14),
                                 wraplength=620, justify="center")
description_label.pack(pady=10, anchor='center')

separator1 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
separator1.pack(fill="x", padx=40, pady=15)

developer_title = ctk.CTkLabel(master=about_scroll_frame, text="Developed by", font=("Calibri", 13))
developer_title.pack(pady=(5, 0), anchor='center')

developer_name = ctk.CTkLabel(master=about_scroll_frame, text="Greg Morton (@Master00Sniper)",
                              font=("Calibri", 17, "bold"))
developer_name.pack(pady=(0, 10), anchor='center')

bio_text = """I'm a passionate gamer, Sr. Systems Administrator by profession, wine enthusiast, and proud 
small winery owner. Vapor was born from my own frustration with notifications interrupting epic gaming 
moments, and constantly having to adjust audio levels for games. I hope it enhances your gaming sessions 
as much as it has mine."""

bio_label = ctk.CTkLabel(master=about_scroll_frame, text=bio_text, font=("Calibri", 13),
                         wraplength=620, justify="center")
bio_label.pack(pady=10, anchor='center')

separator2 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
separator2.pack(fill="x", padx=40, pady=15)

contact_title = ctk.CTkLabel(master=about_scroll_frame, text="Contact & Connect", font=("Calibri", 15, "bold"))
contact_title.pack(pady=(5, 10), anchor='center')

email_label = ctk.CTkLabel(master=about_scroll_frame, text="Email: greg@mortonapps.com", font=("Calibri", 13))
email_label.pack(pady=2, anchor='center')

x_link_frame = ctk.CTkFrame(master=about_scroll_frame, fg_color="transparent")
x_link_frame.pack(pady=2, anchor='center')

x_icon_label = ctk.CTkLabel(master=x_link_frame, text="X: ", font=("Calibri", 13))
x_icon_label.pack(side="left")

x_link_label = ctk.CTkLabel(master=x_link_frame, text="x.com/master00sniper", font=("Calibri", 13, "underline"),
                            text_color="#1DA1F2", cursor="hand2")
x_link_label.pack(side="left")
x_link_label.bind("<Button-1>", lambda e: os.startfile("https://x.com/master00sniper"))

x_handle_label = ctk.CTkLabel(master=x_link_frame, text="  -  @Master00Sniper", font=("Calibri", 13))
x_handle_label.pack(side="left")

separator3 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
separator3.pack(fill="x", padx=40, pady=15)

donate_title = ctk.CTkLabel(master=about_scroll_frame, text="Support Development", font=("Calibri", 15, "bold"))
donate_title.pack(pady=(5, 5), anchor='center')

donate_label = ctk.CTkLabel(master=about_scroll_frame, text="Donation page coming soon!",
                            font=("Calibri", 13))
donate_label.pack(pady=5, anchor='center')

separator4 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
separator4.pack(fill="x", padx=40, pady=15)

credits_title = ctk.CTkLabel(master=about_scroll_frame, text="Credits", font=("Calibri", 15, "bold"))
credits_title.pack(pady=(5, 5), anchor='center')

credits_frame = ctk.CTkFrame(master=about_scroll_frame, fg_color="transparent")
credits_frame.pack(pady=2, anchor='center')

credits_text_label = ctk.CTkLabel(master=credits_frame, text="Icons by ", font=("Calibri", 13))
credits_text_label.pack(side="left")

icons8_link_label = ctk.CTkLabel(master=credits_frame, text="Icons8", font=("Calibri", 13, "underline"),
                                 text_color="#1DA1F2", cursor="hand2")
icons8_link_label.pack(side="left")
icons8_link_label.bind("<Button-1>", lambda e: os.startfile("https://icons8.com"))

separator5 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
separator5.pack(fill="x", padx=40, pady=15)

copyright_label = ctk.CTkLabel(master=about_scroll_frame,
                               text=f"(c) 2024-2026 Greg Morton (@Master00Sniper). All Rights Reserved.",
                               font=("Calibri", 12))
copyright_label.pack(pady=(5, 5), anchor='center')

disclaimer_text = """DISCLAIMER: This software is provided "as is" without warranty of any kind, express or implied, 
including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. 
In no event shall the author be liable for any claim, damages, or other liability arising from the use of this software."""

disclaimer_label = ctk.CTkLabel(master=about_scroll_frame, text=disclaimer_text, font=("Calibri", 11),
                                wraplength=620, justify="center", text_color="gray60")
disclaimer_label.pack(pady=(5, 20), anchor='center')

# =============================================================================
# Bottom Button Bar
# =============================================================================

button_frame = ctk.CTkFrame(master=root, fg_color="transparent")
button_frame.pack(pady=20, fill='x', padx=40)

button_frame.grid_columnconfigure(0, weight=1)
button_frame.grid_columnconfigure(1, weight=0)
button_frame.grid_columnconfigure(2, weight=0)
button_frame.grid_columnconfigure(3, weight=0)
button_frame.grid_columnconfigure(4, weight=1)


def on_save():
    """Save current settings to file. Returns True if saved successfully, False if cancelled."""
    debug_log("Save button clicked", "Settings")
    new_selected_notification_apps = [name for name, var in switch_vars.items() if var.get()]
    raw_customs = [c.strip() for c in custom_entry.get().split(',') if c.strip()]
    new_selected_resource_apps = [name for name, var in resource_switch_vars.items() if var.get()]
    raw_resource_customs = [c.strip() for c in custom_resource_entry.get().split(',') if c.strip()]

    # Filter out protected processes
    blocked = []
    new_customs = []
    for proc in raw_customs:
        if proc.lower() in PROTECTED_PROCESSES:
            blocked.append(proc)
        else:
            new_customs.append(proc)

    new_resource_customs = []
    for proc in raw_resource_customs:
        if proc.lower() in PROTECTED_PROCESSES:
            blocked.append(proc)
        else:
            new_resource_customs.append(proc)

    # Warn user if any processes were blocked
    if blocked:
        blocked_list = ', '.join(blocked)
        messagebox.showwarning(
            "Protected Processes",
            f"The following system processes cannot be managed by Vapor and were removed:\n\n{blocked_list}"
        )
        # Update the entry fields to remove blocked processes
        custom_entry.delete(0, 'end')
        custom_entry.insert(0, ', '.join(new_customs))
        custom_resource_entry.delete(0, 'end')
        custom_resource_entry.insert(0, ', '.join(new_resource_customs))

    new_launch_startup = startup_var.get()
    new_launch_settings_on_start = launch_settings_on_start_var.get()
    new_close_on_startup = close_startup_var.get() == "Enabled"
    new_close_on_hotkey = close_hotkey_var.get() == "Enabled"
    new_relaunch_on_exit = relaunch_exit_var.get() == "Enabled"
    new_resource_close_on_startup = resource_close_startup_var.get() == "Enabled"
    new_resource_close_on_hotkey = resource_close_hotkey_var.get() == "Enabled"
    new_resource_relaunch_on_exit = resource_relaunch_exit_var.get() == "Enabled"
    new_enable_playtime_summary = playtime_summary_var.get()
    new_playtime_summary_mode = playtime_summary_mode_var.get()
    new_enable_debug_mode = debug_mode_var.get()
    new_system_audio_level = system_audio_slider_var.get()
    new_enable_system_audio = enable_system_audio_var.get()
    new_game_audio_level = game_audio_slider_var.get()
    new_enable_game_audio = enable_game_audio_var.get()
    new_enable_during_power = enable_during_power_var.get()
    new_during_power_plan = during_power_var.get()
    new_enable_after_power = enable_after_power_var.get()
    new_after_power_plan = after_power_var.get()
    new_enable_game_mode_start = enable_game_mode_start_var.get()
    new_enable_game_mode_end = enable_game_mode_end_var.get()
    new_enable_cpu_thermal = enable_cpu_thermal_var.get()
    new_enable_gpu_thermal = enable_gpu_thermal_var.get()
    new_enable_cpu_temp_alert = enable_cpu_temp_alert_var.get()
    new_enable_gpu_temp_alert = enable_gpu_temp_alert_var.get()
    # Parse threshold values, defaulting to safe values if invalid
    try:
        new_cpu_temp_warning_threshold = int(cpu_temp_warning_threshold_var.get())
    except ValueError:
        new_cpu_temp_warning_threshold = 85
    try:
        new_cpu_temp_critical_threshold = int(cpu_temp_critical_threshold_var.get())
    except ValueError:
        new_cpu_temp_critical_threshold = 95
    try:
        new_gpu_temp_warning_threshold = int(gpu_temp_warning_threshold_var.get())
    except ValueError:
        new_gpu_temp_warning_threshold = 80
    try:
        new_gpu_temp_critical_threshold = int(gpu_temp_critical_threshold_var.get())
    except ValueError:
        new_gpu_temp_critical_threshold = 90
    save_settings(new_selected_notification_apps, new_customs, new_selected_resource_apps, new_resource_customs,
                  new_launch_startup, new_launch_settings_on_start, new_close_on_startup, new_close_on_hotkey,
                  new_relaunch_on_exit, new_resource_close_on_startup, new_resource_close_on_hotkey,
                  new_resource_relaunch_on_exit, new_enable_playtime_summary, new_playtime_summary_mode,
                  new_enable_debug_mode, new_system_audio_level, new_enable_system_audio, new_game_audio_level,
                  new_enable_game_audio, new_enable_during_power, new_during_power_plan, new_enable_after_power,
                  new_after_power_plan, new_enable_game_mode_start, new_enable_game_mode_end, new_enable_cpu_thermal,
                  new_enable_gpu_thermal, new_enable_cpu_temp_alert, new_cpu_temp_warning_threshold,
                  new_cpu_temp_critical_threshold, new_enable_gpu_temp_alert, new_gpu_temp_warning_threshold,
                  new_gpu_temp_critical_threshold)

    # Check if CPU thermal is enabled and Vapor needs to restart with admin privileges
    if new_enable_cpu_thermal and not is_admin():
        response = show_vapor_dialog(
            title="Admin Privileges Required",
            message="CPU temperature monitoring requires administrator privileges.\n\n"
                    "Would you like to restart Vapor with admin privileges now?\n\n"
                    "If you click 'Restart as Admin', Vapor will close and relaunch\n"
                    "with elevated permissions to enable CPU temperature monitoring.",
            dialog_type="warning",
            buttons=[
                {"text": "Restart as Admin", "value": True, "color": "green"},
                {"text": "Cancel", "value": False, "color": "gray"}
            ],
            parent=root
        )
        if response is True:
            # User agreed to restart with admin
            # Set flag to trigger PawnIO check after restart
            set_pending_pawnio_check(True)
            if restart_vapor(main_pid, require_admin=True):
                # Successfully requested elevation, close settings window
                root.destroy()
                return True
            else:
                # Restart failed, clear the pending flag
                set_pending_pawnio_check(False)
                show_vapor_dialog(
                    title="Elevation Failed",
                    message="Failed to restart Vapor with admin privileges.\n\n"
                            "Please try running Vapor as administrator manually by\n"
                            "right-clicking the Vapor shortcut and selecting\n"
                            "'Run as administrator'.",
                    dialog_type="error",
                    parent=root
                )
                # Elevation failed - toggle CPU temp switch back to disabled
                enable_cpu_thermal_var.set(False)
                return False
        else:
            # User clicked "Cancel" or closed dialog - toggle CPU temp switch back to disabled
            # Return False to indicate save was cancelled (settings window stays open)
            enable_cpu_thermal_var.set(False)
            return False

    # Check if CPU thermal is being NEWLY enabled and PawnIO driver needs to be installed
    # Only check when changing from disabled to enabled (avoids slow winget check on every save)
    if new_enable_cpu_thermal and not enable_cpu_thermal and not is_pawnio_installed():
        response = show_vapor_dialog(
            title="CPU Temperature Driver Required",
            message="CPU temperature monitoring requires the PawnIO driver.\n\n"
                    "PawnIO is a secure, signed kernel driver that allows applications\n"
                    "to safely read hardware sensors like CPU temperatures. It replaces\n"
                    "the older WinRing0 driver which is now flagged by antivirus software.\n\n"
                    "Learn more: https://pawnio.eu\n\n"
                    "Click 'Install' to automatically install the driver.\n"
                    "You will be prompted for administrator approval.",
            dialog_type="warning",
            buttons=[
                {"text": "Install", "value": "install", "color": "green"},
                {"text": "Not Now", "value": "cancel", "color": "gray"}
            ],
            parent=root
        )
        if response == "install":
            # Show installing message with progress bar
            installing_dialog = ctk.CTkToplevel(root)
            installing_dialog.withdraw()  # Hide while setting up to avoid icon flash
            installing_dialog.title("Vapor - Installing Driver")
            installing_dialog.geometry("400x160")
            installing_dialog.resizable(False, False)
            installing_dialog.transient(root)
            installing_dialog.grab_set()

            # Center on parent
            installing_dialog.update_idletasks()
            x = root.winfo_x() + (root.winfo_width() - 400) // 2
            y = root.winfo_y() + (root.winfo_height() - 160) // 2
            installing_dialog.geometry(f"+{x}+{y}")

            msg_label = ctk.CTkLabel(
                installing_dialog,
                text="Requesting administrator approval...",
                font=("Calibri", 13),
                justify="center"
            )
            msg_label.pack(padx=20, pady=(25, 10))

            progress_bar = ctk.CTkProgressBar(installing_dialog, width=300)
            progress_bar.pack(padx=20, pady=10)
            progress_bar.set(0)

            status_label = ctk.CTkLabel(
                installing_dialog,
                text="Please approve the administrator prompt when it appears.",
                font=("Calibri", 11),
                text_color="gray"
            )
            status_label.pack(padx=20, pady=(5, 15))

            installing_dialog.update()
            # Set icon after all widgets added and window updated
            set_vapor_icon(installing_dialog)

            # Bring window to front and give it focus
            installing_dialog.deiconify()  # Show window now that icon is set
            installing_dialog.lift()
            installing_dialog.attributes('-topmost', True)
            installing_dialog.after(100, lambda: installing_dialog.attributes('-topmost', False))
            installing_dialog.focus_force()

            # Progress callback to update the dialog
            def update_progress(message, pct):
                try:
                    if installing_dialog.winfo_exists():
                        msg_label.configure(text=message)
                        progress_bar.set(pct / 100)
                        installing_dialog.update()
                except Exception:
                    pass

            # Run installer with progress updates
            install_success = install_pawnio_with_elevation(progress_callback=update_progress)

            # Clear cache after installation attempt
            clear_pawnio_cache()

            # Close installing dialog
            try:
                installing_dialog.destroy()
            except Exception:
                pass

            if install_success:
                # Ask user to restart Vapor
                restart_response = show_vapor_dialog(
                    title="Driver Installed",
                    message="PawnIO driver installed successfully!\n\n"
                            "Vapor needs to restart to enable CPU temperature monitoring.\n"
                            "Restart now?",
                    dialog_type="info",
                    buttons=[
                        {"text": "Restart Vapor", "value": True, "color": "green"},
                        {"text": "Later", "value": False, "color": "gray"}
                    ],
                    parent=root
                )
                if restart_response:
                    # Restart Vapor (already running as admin if we got here)
                    if restart_vapor(main_pid, require_admin=False):
                        root.destroy()
                        return True
            else:
                show_vapor_dialog(
                    title="Installation Failed",
                    message="Failed to install the PawnIO driver.\n\n"
                            "If you recently uninstalled PawnIO, try rebooting your\n"
                            "computer first - driver uninstalls often require a restart.\n\n"
                            "You can also try installing manually:\n"
                            "1. Run: winget install namazso.PawnIO\n"
                            "2. Or download from: https://pawnio.eu/",
                    dialog_type="error",
                    parent=root
                )
                # Installation failed - toggle CPU temp switch back to disabled
                enable_cpu_thermal_var.set(False)
        else:
            # User clicked "Not Now" - toggle CPU temp switch back to disabled
            enable_cpu_thermal_var.set(False)

    # Check if debug mode was changed - requires restart to take effect
    if new_enable_debug_mode != enable_debug_mode:
        debug_log(f"Debug mode changed from {enable_debug_mode} to {new_enable_debug_mode}", "Settings")
        response = show_vapor_dialog(
            title="Restart Required",
            message="Debug console setting changed.\n\n"
                    "Vapor needs to restart for this change to take effect.\n"
                    "Restart now?",
            dialog_type="info",
            buttons=[
                {"text": "Restart Now", "value": True, "color": "green"},
                {"text": "Later", "value": False, "color": "gray"}
            ],
            parent=root
        )
        if response:
            restart_vapor(main_pid, require_admin=False)
            root.destroy()
            return True

    return True


def on_save_and_close():
    """Save settings and close the window."""
    debug_log("Save & Close clicked", "Settings")
    if on_save():
        root.destroy()
    # If on_save() returns False, the user cancelled - keep window open


def on_discard_and_close():
    """Close without saving changes."""
    debug_log("Discard & Close clicked", "Settings")
    root.destroy()


def on_stop_vapor():
    """Terminate the main Vapor process and close settings."""
    debug_log("Stop Vapor clicked", "Settings")
    if main_pid:
        try:
            debug_log(f"Terminating main Vapor process (PID: {main_pid})", "Settings")
            main_process = psutil.Process(main_pid)
            main_process.terminate()
            debug_log("Main process terminated", "Settings")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            debug_log(f"Could not terminate: {e}", "Settings")
    root.destroy()


save_button = ctk.CTkButton(master=button_frame, text="Save & Close", command=on_save_and_close, corner_radius=10,
                            fg_color="green", text_color="white", width=150, font=("Calibri", 15))
save_button.grid(row=0, column=1, padx=15, sticky='ew')

discard_button = ctk.CTkButton(master=button_frame, text="Discard & Close", command=on_discard_and_close,
                               corner_radius=10,
                               fg_color="gray", text_color="white", width=150, font=("Calibri", 15))
discard_button.grid(row=0, column=2, padx=15, sticky='ew')

stop_button = ctk.CTkButton(master=button_frame, text="Stop Vapor", command=on_stop_vapor, corner_radius=10,
                            fg_color="red", text_color="white", width=150, font=("Calibri", 15))
stop_button.grid(row=0, column=3, padx=15, sticky='ew')

# Make the X button work like Discard & Close
root.protocol("WM_DELETE_WINDOW", on_discard_and_close)


# =============================================================================
# Main Process Monitoring
# =============================================================================

def check_main_process():
    """Auto-close settings if main Vapor process exits."""
    if main_pid:
        try:
            main_process = psutil.Process(main_pid)
            if not main_process.is_running():
                root.destroy()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            root.destroy()
    root.after(1000, check_main_process)


if main_pid:
    root.after(1000, check_main_process)


def check_pending_pawnio_install():
    """Check if PawnIO installation was pending after admin restart.
    This runs automatically after UI initializes if the pending flag was set."""
    debug_log("Checking for pending PawnIO installation...", "Startup")

    # Check if the flag is set
    pending_check = current_settings.get('pending_pawnio_check', False)
    if not pending_check:
        debug_log("No pending PawnIO check", "Startup")
        return

    # Clear the flag immediately to prevent repeated prompts
    set_pending_pawnio_check(False)
    debug_log("Cleared pending_pawnio_check flag", "Startup")

    # Only proceed if we're running as admin
    if not is_admin():
        debug_log("Not running as admin, skipping PawnIO check", "Startup")
        return

    # Check if PawnIO is already installed
    if is_pawnio_installed(use_cache=False):
        debug_log("PawnIO is already installed", "Startup")
        return

    debug_log("PawnIO not installed, showing installation prompt", "Startup")

    # Show the PawnIO installation dialog
    response = show_vapor_dialog(
        title="CPU Temperature Driver Required",
        message="CPU temperature monitoring requires the PawnIO driver.\n\n"
                "PawnIO is a secure, signed kernel driver that allows applications\n"
                "to safely read hardware sensors like CPU temperatures. It replaces\n"
                "the older WinRing0 driver which is now flagged by antivirus software.\n\n"
                "Learn more: https://pawnio.eu\n\n"
                "Click 'Install' to automatically install the driver.",
        dialog_type="warning",
        buttons=[
            {"text": "Install", "value": "install", "color": "green"},
            {"text": "Not Now", "value": "cancel", "color": "gray"}
        ],
        parent=root
    )

    if response == "install":
        # Show installing message with progress bar
        installing_dialog = ctk.CTkToplevel(root)
        installing_dialog.withdraw()  # Hide while setting up to avoid icon flash
        installing_dialog.title("Vapor - Installing Driver")
        installing_dialog.geometry("400x160")
        installing_dialog.resizable(False, False)
        installing_dialog.transient(root)
        installing_dialog.grab_set()

        # Center on parent
        installing_dialog.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - 400) // 2
        y = root.winfo_y() + (root.winfo_height() - 160) // 2
        installing_dialog.geometry(f"+{x}+{y}")

        msg_label = ctk.CTkLabel(
            installing_dialog,
            text="Installing PawnIO driver...",
            font=("Calibri", 13),
            justify="center"
        )
        msg_label.pack(padx=20, pady=(25, 10))

        progress_bar = ctk.CTkProgressBar(installing_dialog, width=300)
        progress_bar.pack(padx=20, pady=10)
        progress_bar.set(0)

        status_label = ctk.CTkLabel(
            installing_dialog,
            text="This may take a moment...",
            font=("Calibri", 11),
            text_color="gray"
        )
        status_label.pack(padx=20, pady=(5, 15))

        installing_dialog.update()
        set_vapor_icon(installing_dialog)

        # Bring window to front and give it focus
        installing_dialog.deiconify()  # Show window now that icon is set
        installing_dialog.lift()
        installing_dialog.attributes('-topmost', True)
        installing_dialog.after(100, lambda: installing_dialog.attributes('-topmost', False))
        installing_dialog.focus_force()

        # Progress callback
        def update_progress(message, pct):
            try:
                if installing_dialog.winfo_exists():
                    msg_label.configure(text=message)
                    progress_bar.set(pct / 100)
                    installing_dialog.update()
            except Exception:
                pass

        # Run installer
        install_success = install_pawnio_with_elevation(progress_callback=update_progress)
        clear_pawnio_cache()

        try:
            installing_dialog.destroy()
        except Exception:
            pass

        if install_success:
            # Ask user to restart Vapor to use the driver
            restart_response = show_vapor_dialog(
                title="Driver Installed",
                message="PawnIO driver installed successfully!\n\n"
                        "Vapor needs to restart to enable CPU temperature monitoring.\n"
                        "Restart now?",
                dialog_type="info",
                buttons=[
                    {"text": "Restart Vapor", "value": True, "color": "green"},
                    {"text": "Later", "value": False, "color": "gray"}
                ],
                parent=root
            )
            if restart_response:
                if restart_vapor(main_pid, require_admin=False):
                    root.destroy()
                    return
        else:
            show_vapor_dialog(
                title="Installation Failed",
                message="Failed to install the PawnIO driver.\n\n"
                        "If you recently uninstalled PawnIO, try rebooting your\n"
                        "computer first - driver uninstalls often require a restart.\n\n"
                        "You can also try installing manually:\n"
                        "1. Run: winget install namazso.PawnIO\n"
                        "2. Or download from: https://pawnio.eu/",
                dialog_type="error",
                parent=root
            )
            # Disable CPU thermal since installation failed
            enable_cpu_thermal_var.set(False)
    else:
        # User clicked "Not Now" - disable CPU thermal
        debug_log("User cancelled PawnIO installation", "Startup")
        enable_cpu_thermal_var.set(False)


# Schedule the pending PawnIO check to run after UI fully initializes
root.after(500, check_pending_pawnio_install)

# Start the UI
root.mainloop()