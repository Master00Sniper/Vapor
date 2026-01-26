# vapor_settings_ui.py

import os
import sys

# NEW: Imports for mutex
import win32event
import win32api
import winerror

# Check for existing instance
mutex = win32event.CreateMutex(None, True, "Vapor_Settings_SingleInstance_Mutex")
if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
    print("Settings window is already open. Exiting.")
    sys.exit(0)

# Path fix for frozen executable
application_path = ''
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(application_path)
sys.path.append(application_path)

import customtkinter as ctk  # Import CustomTkinter (install with pip install customtkinter)
import tkinter as tk  # Standard Tkinter for BooleanVar (switch states)
import json
from PIL import Image, ImageTk  # From Pillow (already installed, for icons)
import psutil  # For terminating the main process
import win32gui  # From pywin32, for modifying window style
import win32con  # From pywin32

# NEW: Import version from updater
try:
    from updater import CURRENT_VERSION
except ImportError:
    CURRENT_VERSION = "Unknown"

# Added base_dir for frozen executable compatibility
base_dir = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))

# Use %APPDATA% for writable settings file
appdata_dir = os.path.join(os.getenv('APPDATA'), 'Vapor')
os.makedirs(appdata_dir, exist_ok=True)
SETTINGS_FILE = os.path.join(appdata_dir, 'vapor_settings.json')

TRAY_ICON_PATH = os.path.join(base_dir, 'Images', 'tray_icon.png')

# Built-in messaging apps (for Notifications tab)
BUILT_IN_APPS = [
    {'display_name': 'WhatsApp', 'processes': ['WhatsApp.Root.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'whatsapp_icon.png')},
    {'display_name': 'Discord', 'processes': ['Discord.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'discord_icon.png')},
    {'display_name': 'Telegram', 'processes': ['Telegram.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'telegram_icon.png')},
    {'display_name': 'Microsoft Teams', 'processes': ['ms-teams.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'teams_icon.png')},
    {'display_name': 'Facebook Messenger', 'processes': ['Messenger.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'messenger_icon.png')},
    {'display_name': 'Slack', 'processes': ['slack.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'slack_icon.png')},
    {'display_name': 'Signal', 'processes': ['Signal.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'signal_icon.png')},
    {'display_name': 'WeChat', 'processes': ['WeChat.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'wechat_icon.png')}
]

# Built-in resource-heavy apps (for Resources tab) - these are examples; change if needed
BUILT_IN_RESOURCE_APPS = [
    {'display_name': 'Chrome', 'processes': ['chrome.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'chrome_icon.png')},
    {'display_name': 'Firefox', 'processes': ['firefox.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'firefox_icon.png')},
    {'display_name': 'Edge', 'processes': ['msedge.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'edge_icon.png')},
    {'display_name': 'Spotify', 'processes': ['spotify.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'spotify_icon.png')},
    {'display_name': 'OneDrive', 'processes': ['OneDrive.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'onedrive_icon.png')},
    {'display_name': 'Google Drive', 'processes': ['GoogleDriveFS.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'googledrive_icon.png')},
    {'display_name': 'Dropbox', 'processes': ['Dropbox.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'dropbox_icon.png')},
    {'display_name': 'Wallpaper Engine', 'processes': ['wallpaper64.exe'], 'icon_path': os.path.join(base_dir, 'Images', 'wallpaperengine_icon.png')}
]


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    else:
        default_selected = ["WhatsApp", "Telegram", "Microsoft Teams", "Facebook Messenger", "Slack", "Signal", "WeChat"]
        default_resource_selected = ["Firefox", "Edge", "Spotify", "OneDrive", "Google Drive", "Dropbox", "Wallpaper Engine"]
        return {'selected_apps': default_selected, 'custom_processes': [],
                'selected_resource_apps': default_resource_selected, 'custom_resource_processes': [],
                'launch_at_startup': False,
                'close_on_startup': True, 'close_on_hotkey': True, 'relaunch_on_exit': True,
                'resource_close_on_startup': True, 'resource_close_on_hotkey': True, 'resource_relaunch_on_exit': False,
                'enable_playtime_summary': True, 'enable_debug_mode': False, 'system_audio_level': 33, 'enable_system_audio': False,
                'game_audio_level': 100, 'enable_game_audio': False,
                'enable_during_power': False, 'during_power_plan': 'High Performance',
                'enable_after_power': False, 'after_power_plan': 'Balanced',
                'enable_game_mode_start': False, 'enable_game_mode_end': False}

def save_settings(selected_apps, customs, selected_resource_apps, resource_customs, launch_startup, close_on_startup, close_on_hotkey, relaunch_on_exit, resource_close_on_startup, resource_close_on_hotkey, resource_relaunch_on_exit, enable_playtime_summary, enable_debug_mode, system_audio_level, enable_system_audio, game_audio_level, enable_game_audio, enable_during_power, during_power_plan, enable_after_power, after_power_plan, enable_game_mode_start, enable_game_mode_end):
    # Flatten processes for Notifications (messaging)
    notification_processes = []
    for app in BUILT_IN_APPS:
        if app['display_name'] in selected_apps:
            notification_processes.extend(app['processes'])
    notification_processes.extend(customs)

    # Flatten processes for Resources
    resource_processes = []
    for app in BUILT_IN_RESOURCE_APPS:
        if app['display_name'] in selected_resource_apps:
            resource_processes.extend(app['processes'])
    resource_processes.extend(resource_customs)

    settings = {
        'notification_processes': notification_processes,
        'selected_apps': selected_apps,  # For UI preload
        'custom_processes': customs,  # For UI preload
        'resource_processes': resource_processes,
        'selected_resource_apps': selected_resource_apps,
        'custom_resource_processes': resource_customs,
        'launch_at_startup': launch_startup,
        'close_on_startup': close_on_startup,
        'close_on_hotkey': close_on_hotkey,
        'relaunch_on_exit': relaunch_on_exit,
        'resource_close_on_startup': resource_close_on_startup,
        'resource_close_on_hotkey': resource_close_on_hotkey,
        'resource_relaunch_on_exit': resource_relaunch_on_exit,
        'enable_playtime_summary': enable_playtime_summary,
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
        'enable_game_mode_end': enable_game_mode_end
    }
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

# Create window
root = ctk.CTk()
root.withdraw()  # Hide the window initially to prevent flash
root.title(f"Vapor Settings v{CURRENT_VERSION}")  # UPDATED: Added version number
root.geometry("700x900")
root.resizable(False, False)

# Set the window icon (using ICO for better taskbar support on Windows)
icon_path = os.path.join(base_dir, 'Images', 'tray_icon.ico')
if os.path.exists(icon_path):
    root.iconbitmap(icon_path)

# Remove X button from title bar
root.update()
hwnd = int(root.wm_frame(), 16)
style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
new_style = style & ~win32con.WS_SYSMENU
win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, new_style)

# Center the window on the screen
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
window_width = 700
window_height = 900
x = (screen_width - window_width) // 2
y = (screen_height - window_height) // 2
root.geometry(f"{window_width}x{window_height}+{x}+{y}")

# Now show the window after positioning
root.deiconify()

# Load settings
current_settings = load_settings()
selected_apps = current_settings.get('selected_apps', [])
custom_processes = current_settings.get('custom_processes', [])
selected_resource_apps = current_settings.get('selected_resource_apps', [])
custom_resource_processes = current_settings.get('custom_resource_processes', [])
launch_at_startup = current_settings.get('launch_at_startup', False)
close_on_startup = current_settings.get('close_on_startup', True)
close_on_hotkey = current_settings.get('close_on_hotkey', False)
relaunch_on_exit = current_settings.get('relaunch_on_exit', True)
resource_close_on_startup = current_settings.get('resource_close_on_startup', True)
resource_close_on_hotkey = current_settings.get('resource_close_on_hotkey', False)
resource_relaunch_on_exit = current_settings.get('resource_relaunch_on_exit', True)
enable_playtime_summary = current_settings.get('enable_playtime_summary', True)
enable_debug_mode = current_settings.get('enable_debug_mode', False)
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

# Get main process PID for Close button
main_pid = None
if len(sys.argv) > 1:
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

switch_vars = {}
resource_switch_vars = {}

# Create the tabview (tabs at the top)
tabview = ctk.CTkTabview(master=root)
tabview.pack(pady=10, padx=10, fill="both", expand=True)  # Fills the window space

# Add the three tabs
notifications_tab = tabview.add("Notifications")
preferences_tab = tabview.add("Preferences")
resources_tab = tabview.add("Resources")

# ===== Content for Notifications Tab =====
# Title
notification_title = ctk.CTkLabel(master=notifications_tab, text="Notification Management Settings", font=("Calibri", 20, "bold"))
notification_title.pack(pady=20, anchor='center')

# Options frame for the 3 radiobutton groups
options_frame = ctk.CTkFrame(master=notifications_tab, fg_color="transparent")
options_frame.pack(pady=10, padx=10, anchor='w')

# First option: Automatically Close Selected Apps When Game Starts
close_startup_label = ctk.CTkLabel(master=options_frame, text="Automatically Close Selected Apps When Game Starts:", font=("Calibri", 14))
close_startup_label.grid(row=0, column=0, pady=5, padx=10, sticky='w')

close_startup_var = tk.StringVar(value="Enabled" if close_on_startup else "Disabled")
ctk.CTkRadioButton(master=options_frame, text="Enabled", variable=close_startup_var, value="Enabled", font=("Calibri", 14)).grid(row=0, column=1, pady=5, padx=20)
ctk.CTkRadioButton(master=options_frame, text="Disabled", variable=close_startup_var, value="Disabled", font=("Calibri", 14)).grid(row=0, column=2, pady=5, padx=20)

# Second option: Close Selected Apps With Hotkey (Ctrl-Alt-k)
close_hotkey_label = ctk.CTkLabel(master=options_frame, text="Close Selected Apps With Hotkey (Ctrl-Alt-k):", font=("Calibri", 14))
close_hotkey_label.grid(row=1, column=0, pady=5, padx=10, sticky='w')

close_hotkey_var = tk.StringVar(value="Enabled" if close_on_hotkey else "Disabled")
ctk.CTkRadioButton(master=options_frame, text="Enabled", variable=close_hotkey_var, value="Enabled", font=("Calibri", 14)).grid(row=1, column=1, pady=5, padx=20)
ctk.CTkRadioButton(master=options_frame, text="Disabled", variable=close_hotkey_var, value="Disabled", font=("Calibri", 14)).grid(row=1, column=2, pady=5, padx=20)

# Third option: Automatically Relaunch Closed Apps When Game Ends
relaunch_exit_label = ctk.CTkLabel(master=options_frame, text="Automatically Relaunch Closed Apps When Game Ends:", font=("Calibri", 14))
relaunch_exit_label.grid(row=2, column=0, pady=5, padx=10, sticky='w')

relaunch_exit_var = tk.StringVar(value="Enabled" if relaunch_on_exit else "Disabled")
ctk.CTkRadioButton(master=options_frame, text="Enabled", variable=relaunch_exit_var, value="Enabled", font=("Calibri", 14)).grid(row=2, column=1, pady=5, padx=20)
ctk.CTkRadioButton(master=options_frame, text="Disabled", variable=relaunch_exit_var, value="Disabled", font=("Calibri", 14)).grid(row=2, column=2, pady=5, padx=20)

# Apps subtitle
apps_subtitle = ctk.CTkLabel(master=notifications_tab, text="Select Apps to Close", font=("Calibri", 16, "bold"))
apps_subtitle.pack(pady=10, anchor='center')

# App list frame with two columns
app_frame = ctk.CTkFrame(master=notifications_tab, fg_color="transparent")
app_frame.pack(pady=10, padx=10)

left_column = ctk.CTkFrame(master=app_frame, fg_color="transparent")
left_column.pack(side="left", padx=10)

right_column = ctk.CTkFrame(master=app_frame, fg_color="transparent")
right_column.pack(side="left", padx=10)

# Left column - first 4 apps
for i in range(4):
    app = BUILT_IN_APPS[i]
    display_name = app['display_name']
    icon_path = app['icon_path']

    row_frame = ctk.CTkFrame(master=left_column, fg_color="transparent")
    row_frame.pack(pady=5, anchor='w')

    if os.path.exists(icon_path):
        img = Image.open(icon_path).convert("RGBA")
        img = img.resize((30, 30), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        icon_label = tk.Label(row_frame, image=photo, bg=notifications_tab.cget("fg_color"))
        icon_label.image = photo
        icon_label.pack(side="left", padx=5)
    else:
        ctk.CTkLabel(master=row_frame, text="Icon", font=("Calibri", 14)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_apps)
    switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14))
    switch.pack(side="left")

# Right column - last 4 apps
for i in range(4, 8):
    app = BUILT_IN_APPS[i]
    display_name = app['display_name']
    icon_path = app['icon_path']

    row_frame = ctk.CTkFrame(master=right_column, fg_color="transparent")
    row_frame.pack(pady=5, anchor='w')

    if os.path.exists(icon_path):
        img = Image.open(icon_path).convert("RGBA")
        img = img.resize((30, 30), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        icon_label = tk.Label(row_frame, image=photo, bg=notifications_tab.cget("fg_color"))
        icon_label.image = photo
        icon_label.pack(side="left", padx=5)
    else:
        ctk.CTkLabel(master=row_frame, text="Icon", font=("Calibri", 14)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_apps)
    switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14))
    switch.pack(side="left")

# All Apps toggle - under the app list, centered
def on_all_apps_toggle():
    state = all_apps_var.get()
    for var in switch_vars.values():
        var.set(state)

all_apps_var = tk.BooleanVar(value=all(display_name in selected_apps for display_name in
                                        [app['display_name'] for app in BUILT_IN_APPS]))

all_apps_switch = ctk.CTkSwitch(master=notifications_tab, text="Toggle All Apps", variable=all_apps_var, command=on_all_apps_toggle, font=("Calibri", 14))
all_apps_switch.pack(pady=15, anchor='center')

# Custom processes
custom_label_text = "Add custom processes (comma-separated, e.g.: MyApp1.exe,MyApp2.exe):"
custom_label = ctk.CTkLabel(master=notifications_tab, text=custom_label_text, font=("Calibri", 14))
custom_label.pack(pady=20, padx=20, anchor='w')

custom_entry = ctk.CTkEntry(master=notifications_tab, width=660, font=("Calibri", 14))
custom_entry.insert(0, ','.join(custom_processes))
custom_entry.pack(padx=20, anchor='w')

# ===== Content for Resources Tab =====
# Title
resource_title = ctk.CTkLabel(master=resources_tab, text="Resource Management Settings", font=("Calibri", 20, "bold"))
resource_title.pack(pady=20, anchor='center')

# Options frame for Resources
resource_options_frame = ctk.CTkFrame(master=resources_tab, fg_color="transparent")
resource_options_frame.pack(pady=10, padx=10, anchor='w')

# First option: Automatically Close Selected Apps When Game Starts
resource_close_startup_label = ctk.CTkLabel(master=resource_options_frame, text="Automatically Close Selected Apps When Game Starts:", font=("Calibri", 14))
resource_close_startup_label.grid(row=0, column=0, pady=5, padx=10, sticky='w')

resource_close_startup_var = tk.StringVar(value="Enabled" if resource_close_on_startup else "Disabled")
ctk.CTkRadioButton(master=resource_options_frame, text="Enabled", variable=resource_close_startup_var, value="Enabled", font=("Calibri", 14)).grid(row=0, column=1, pady=5, padx=20)
ctk.CTkRadioButton(master=resource_options_frame, text="Disabled", variable=resource_close_startup_var, value="Disabled", font=("Calibri", 14)).grid(row=0, column=2, pady=5, padx=20)

# Second option: Close Selected Apps With Hotkey (Ctrl-Alt-k)
resource_close_hotkey_label = ctk.CTkLabel(master=resource_options_frame, text="Close Selected Apps With Hotkey (Ctrl-Alt-k):", font=("Calibri", 14))
resource_close_hotkey_label.grid(row=1, column=0, pady=5, padx=10, sticky='w')

resource_close_hotkey_var = tk.StringVar(value="Enabled" if resource_close_on_hotkey else "Disabled")
ctk.CTkRadioButton(master=resource_options_frame, text="Enabled", variable=resource_close_hotkey_var, value="Enabled", font=("Calibri", 14)).grid(row=1, column=1, pady=5, padx=20)
ctk.CTkRadioButton(master=resource_options_frame, text="Disabled", variable=resource_close_hotkey_var, value="Disabled", font=("Calibri", 14)).grid(row=1, column=2, pady=5, padx=20)

# Third option: Automatically Relaunch Closed Apps When Game Ends
resource_relaunch_exit_label = ctk.CTkLabel(master=resource_options_frame, text="Automatically Relaunch Closed Apps When Game Ends:", font=("Calibri", 14))
resource_relaunch_exit_label.grid(row=2, column=0, pady=5, padx=10, sticky='w')

resource_relaunch_exit_var = tk.StringVar(value="Enabled" if resource_relaunch_on_exit else "Disabled")
ctk.CTkRadioButton(master=resource_options_frame, text="Enabled", variable=resource_relaunch_exit_var, value="Enabled", font=("Calibri", 14)).grid(row=2, column=1, pady=5, padx=20)
ctk.CTkRadioButton(master=resource_options_frame, text="Disabled", variable=resource_relaunch_exit_var, value="Disabled", font=("Calibri", 14)).grid(row=2, column=2, pady=5, padx=20)

# Apps subtitle for Resources
resource_apps_subtitle = ctk.CTkLabel(master=resources_tab, text="Select Apps to Close", font=("Calibri", 16, "bold"))
resource_apps_subtitle.pack(pady=10, anchor='center')

# App list frame with two columns for Resources
resource_app_frame = ctk.CTkFrame(master=resources_tab, fg_color="transparent")
resource_app_frame.pack(pady=10, padx=10)

resource_left_column = ctk.CTkFrame(master=resource_app_frame, fg_color="transparent")
resource_left_column.pack(side="left", padx=10)

resource_right_column = ctk.CTkFrame(master=resource_app_frame, fg_color="transparent")
resource_right_column.pack(side="left", padx=10)

# Left column - first 4 resource apps
for i in range(4):
    app = BUILT_IN_RESOURCE_APPS[i]
    display_name = app['display_name']
    icon_path = app['icon_path']

    row_frame = ctk.CTkFrame(master=resource_left_column, fg_color="transparent")
    row_frame.pack(pady=5, anchor='w')

    if os.path.exists(icon_path):
        img = Image.open(icon_path).convert("RGBA")
        img = img.resize((30, 30), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        icon_label = tk.Label(row_frame, image=photo, bg=resources_tab.cget("fg_color"))
        icon_label.image = photo
        icon_label.pack(side="left", padx=5)
    else:
        ctk.CTkLabel(master=row_frame, text="Icon", font=("Calibri", 14)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_resource_apps)
    resource_switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14))
    switch.pack(side="left")

# Right column - last 4 resource apps
for i in range(4, 8):
    app = BUILT_IN_RESOURCE_APPS[i]
    display_name = app['display_name']
    icon_path = app['icon_path']

    row_frame = ctk.CTkFrame(master=resource_right_column, fg_color="transparent")
    row_frame.pack(pady=5, anchor='w')

    if os.path.exists(icon_path):
        img = Image.open(icon_path).convert("RGBA")
        img = img.resize((30, 30), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        icon_label = tk.Label(row_frame, image=photo, bg=resources_tab.cget("fg_color"))
        icon_label.image = photo
        icon_label.pack(side="left", padx=5)
    else:
        ctk.CTkLabel(master=row_frame, text="Icon", font=("Calibri", 14)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_resource_apps)
    resource_switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14))
    switch.pack(side="left")

# All Apps toggle for Resources - under the app list, centered
def on_resource_all_apps_toggle():
    state = resource_all_apps_var.get()
    for var in resource_switch_vars.values():
        var.set(state)

resource_all_apps_var = tk.BooleanVar(value=all(display_name in selected_resource_apps for display_name in
                                                [app['display_name'] for app in BUILT_IN_RESOURCE_APPS]))

resource_all_apps_switch = ctk.CTkSwitch(master=resources_tab, text="Toggle All Apps", variable=resource_all_apps_var, command=on_resource_all_apps_toggle, font=("Calibri", 14))
resource_all_apps_switch.pack(pady=15, anchor='center')

# Custom processes for Resources
custom_resource_label_text = "Add custom resource processes (comma-separated, e.g.: MyApp1.exe,MyApp2.exe):"
custom_resource_label = ctk.CTkLabel(master=resources_tab, text=custom_resource_label_text, font=("Calibri", 14))
custom_resource_label.pack(pady=20, padx=20, anchor='w')

custom_resource_entry = ctk.CTkEntry(master=resources_tab, width=660, font=("Calibri", 14))
custom_resource_entry.insert(0, ','.join(custom_resource_processes))
custom_resource_entry.pack(padx=20, anchor='w')

# ===== Content for Preferences Tab =====
# Preferences title
preferences_title = ctk.CTkLabel(master=preferences_tab, text="Vapor Preferences", font=("Calibri", 16, "bold"))
preferences_title.pack(pady=10, anchor='center')

# Playtime summary toggle (at top)
playtime_summary_var = tk.BooleanVar(value=enable_playtime_summary)
playtime_summary_switch = ctk.CTkSwitch(master=preferences_tab, text="Enable Playtime Summary Report", variable=playtime_summary_var, font=("Calibri", 14))
playtime_summary_switch.pack(padx=20, pady=5, anchor='w')

# Startup toggle
startup_var = tk.BooleanVar(value=launch_at_startup)
startup_switch = ctk.CTkSwitch(master=preferences_tab, text="Launch Vapor at System Startup", variable=startup_var, font=("Calibri", 14))
startup_switch.pack(padx=20, pady=5, anchor='w')

# Debug mode toggle
debug_mode_var = tk.BooleanVar(value=enable_debug_mode)
debug_mode_switch = ctk.CTkSwitch(master=preferences_tab, text="Enable Debug Mode (Show Console Window)", variable=debug_mode_var, font=("Calibri", 14))
debug_mode_switch.pack(padx=20, pady=5, anchor='w')

# Audio subtitle
audio_subtitle = ctk.CTkLabel(master=preferences_tab, text="Audio Settings - Applied At Game Start", font=("Calibri", 16, "bold"))
audio_subtitle.pack(pady=10, anchor='center')

# Audio settings frame to hold system and game audio side by side
audio_frame = ctk.CTkFrame(master=preferences_tab, fg_color="transparent")
audio_frame.pack(padx=20, pady=10, anchor='w')

# System audio column
system_audio_column = ctk.CTkFrame(master=audio_frame, fg_color="transparent")
system_audio_column.pack(side="left", padx=50)

system_audio_label = ctk.CTkLabel(master=system_audio_column, text="Set System Audio Level:", font=("Calibri", 14))
system_audio_label.pack(anchor='w')

system_audio_slider_var = tk.IntVar(value=system_audio_level)
system_audio_slider = ctk.CTkSlider(master=system_audio_column, from_=0, to=100, number_of_steps=100, variable=system_audio_slider_var)
system_audio_slider.pack(anchor='w')

system_current_value_label = ctk.CTkLabel(master=system_audio_column, text=f"{system_audio_level}%", font=("Calibri", 14))
system_current_value_label.pack(anchor='w')

def update_system_audio_label(value):
    system_current_value_label.configure(text=f"{int(value)}%")

system_audio_slider.configure(command=update_system_audio_label)

enable_system_audio_var = tk.BooleanVar(value=enable_system_audio)
enable_system_audio_switch = ctk.CTkSwitch(master=system_audio_column, text="Enable", variable=enable_system_audio_var, font=("Calibri", 14))
enable_system_audio_switch.pack(anchor='w')

# Game audio column (moved to right)
game_audio_column = ctk.CTkFrame(master=audio_frame, fg_color="transparent")
game_audio_column.pack(side="left", padx=30)

game_audio_label = ctk.CTkLabel(master=game_audio_column, text="Set Game Audio Level:", font=("Calibri", 14))
game_audio_label.pack(anchor='w')

game_audio_slider_var = tk.IntVar(value=game_audio_level)
game_audio_slider = ctk.CTkSlider(master=game_audio_column, from_=0, to=100, number_of_steps=100, variable=game_audio_slider_var)
game_audio_slider.pack(anchor='w')

game_current_value_label = ctk.CTkLabel(master=game_audio_column, text=f"{game_audio_level}%", font=("Calibri", 14))
game_current_value_label.pack(anchor='w')

def update_game_audio_label(value):
    game_current_value_label.configure(text=f"{int(value)}%")

game_audio_slider.configure(command=update_game_audio_label)

enable_game_audio_var = tk.BooleanVar(value=enable_game_audio)
enable_game_audio_switch = ctk.CTkSwitch(master=game_audio_column, text="Enable", variable=enable_game_audio_var, font=("Calibri", 14))
enable_game_audio_switch.pack(anchor='w')

# Power subtitle
power_subtitle = ctk.CTkLabel(master=preferences_tab, text="Power Settings - Applied at Game Start and Exit", font=("Calibri", 16, "bold"))
power_subtitle.pack(pady=10, anchor='center')

# Power plan settings frame
power_frame = ctk.CTkFrame(master=preferences_tab, fg_color="transparent")
power_frame.pack(padx=20, pady=10, anchor='w')

# During gaming power plan column
during_power_column = ctk.CTkFrame(master=power_frame, fg_color="transparent")
during_power_column.pack(side="left", padx=50)

during_power_label = ctk.CTkLabel(master=during_power_column, text="Power Profile During Gaming:", font=("Calibri", 14))
during_power_label.pack(anchor='w')

during_power_var = tk.StringVar(value=during_power_plan)
during_power_combobox = ctk.CTkComboBox(master=during_power_column, values=["High Performance", "Balanced", "Power saver"], variable=during_power_var)
during_power_combobox.pack(anchor='w')

enable_during_power_var = tk.BooleanVar(value=enable_during_power)
enable_during_power_switch = ctk.CTkSwitch(master=during_power_column, text="Enable", variable=enable_during_power_var, font=("Calibri", 14))
enable_during_power_switch.pack(anchor='w', pady=10)

# After gaming power plan column
after_power_column = ctk.CTkFrame(master=power_frame, fg_color="transparent")
after_power_column.pack(side="left", padx=62)

after_power_label = ctk.CTkLabel(master=after_power_column, text="Power Profile After Gaming:", font=("Calibri", 14))
after_power_label.pack(anchor='w')

after_power_var = tk.StringVar(value=after_power_plan)
after_power_combobox = ctk.CTkComboBox(master=after_power_column, values=["High Performance", "Balanced", "Power saver"], variable=after_power_var)
after_power_combobox.pack(anchor='w')

enable_after_power_var = tk.BooleanVar(value=enable_after_power)
enable_after_power_switch = ctk.CTkSwitch(master=after_power_column, text="Enable", variable=enable_after_power_var, font=("Calibri", 14))
enable_after_power_switch.pack(anchor='w', pady=10)

# Game Mode subtitle
game_mode_subtitle = ctk.CTkLabel(master=preferences_tab, text="Windows Game Mode Settings", font=("Calibri", 16, "bold"))
game_mode_subtitle.pack(pady=10, anchor='center')

# Game Mode settings frame
game_mode_frame = ctk.CTkFrame(master=preferences_tab, fg_color="transparent")
game_mode_frame.pack(padx=20, pady=10, anchor='w')

# Game Mode at game start column
game_mode_start_column = ctk.CTkFrame(master=game_mode_frame, fg_color="transparent")
game_mode_start_column.pack(side="left", padx=50)

enable_game_mode_start_var = tk.BooleanVar(value=enable_game_mode_start)
enable_game_mode_start_switch = ctk.CTkSwitch(master=game_mode_start_column, text="Enable Game Mode at Game Start", variable=enable_game_mode_start_var, font=("Calibri", 14))
enable_game_mode_start_switch.pack(anchor='w')

# Game Mode at game end column
game_mode_end_column = ctk.CTkFrame(master=game_mode_frame, fg_color="transparent")
game_mode_end_column.pack(side="left", padx=30)

enable_game_mode_end_var = tk.BooleanVar(value=enable_game_mode_end)
enable_game_mode_end_switch = ctk.CTkSwitch(master=game_mode_end_column, text="Disable Game Mode at Game End", variable=enable_game_mode_end_var, font=("Calibri", 14))
enable_game_mode_end_switch.pack(anchor='w')

# Bottom buttons frame (outside tabs, always at bottom)
button_frame = ctk.CTkFrame(master=root, fg_color="transparent")
button_frame.pack(pady=20, fill='x', padx=40)  # Pushed to bottom with padding

# Grid layout for centered buttons with cushion
button_frame.grid_columnconfigure(0, weight=1)
button_frame.grid_columnconfigure(1, weight=0)
button_frame.grid_columnconfigure(2, weight=0)
button_frame.grid_columnconfigure(3, weight=1)

def on_save():
    new_selected_apps = [name for name, var in switch_vars.items() if var.get()]
    new_customs = [c.strip() for c in custom_entry.get().split(',') if c.strip()]
    new_selected_resource_apps = [name for name, var in resource_switch_vars.items() if var.get()]
    new_resource_customs = [c.strip() for c in custom_resource_entry.get().split(',') if c.strip()]
    new_launch_startup = startup_var.get()
    new_close_on_startup = close_startup_var.get() == "Enabled"
    new_close_on_hotkey = close_hotkey_var.get() == "Enabled"
    new_relaunch_on_exit = relaunch_exit_var.get() == "Enabled"
    new_resource_close_on_startup = resource_close_startup_var.get() == "Enabled"
    new_resource_close_on_hotkey = resource_close_hotkey_var.get() == "Enabled"
    new_resource_relaunch_on_exit = resource_relaunch_exit_var.get() == "Enabled"
    new_enable_playtime_summary = playtime_summary_var.get()
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
    save_settings(new_selected_apps, new_customs, new_selected_resource_apps, new_resource_customs, new_launch_startup, new_close_on_startup, new_close_on_hotkey, new_relaunch_on_exit, new_resource_close_on_startup, new_resource_close_on_hotkey, new_resource_relaunch_on_exit, new_enable_playtime_summary, new_enable_debug_mode, new_system_audio_level, new_enable_system_audio, new_game_audio_level, new_enable_game_audio, new_enable_during_power, new_during_power_plan, new_enable_after_power, new_after_power_plan, new_enable_game_mode_start, new_enable_game_mode_end)

save_button = ctk.CTkButton(master=button_frame, text="Save Settings", command=on_save, corner_radius=10, fg_color="blue", text_color="white", width=150, font=("Calibri", 14))
save_button.grid(row=0, column=1, padx=30, sticky='ew')

def on_close():
    root.destroy()

close_button = ctk.CTkButton(master=button_frame, text="Close", command=on_close, corner_radius=10, fg_color="red", text_color="white", width=150, font=("Calibri", 14))
close_button.grid(row=0, column=2, padx=30, sticky='ew')

# Function to check if main process is running
def check_main_process():
    if main_pid:
        try:
            main_process = psutil.Process(main_pid)
            if not main_process.is_running():
                root.destroy()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            root.destroy()
    root.after(1000, check_main_process)  # Check every second

# Start checking if main_pid is provided
if main_pid:
    root.after(1000, check_main_process)

# Start the app
root.mainloop()