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

import customtkinter as ctk
import tkinter as tk
import json
from PIL import Image
import psutil
import win32gui
import win32con
import win11toast

try:
    from updater import CURRENT_VERSION
except ImportError:
    CURRENT_VERSION = "Unknown"

base_dir = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))

appdata_dir = os.path.join(os.getenv('APPDATA'), 'Vapor')
os.makedirs(appdata_dir, exist_ok=True)
SETTINGS_FILE = os.path.join(appdata_dir, 'vapor_settings.json')

TRAY_ICON_PATH = os.path.join(base_dir, 'Images', 'tray_icon.png')

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

BUILT_IN_RESOURCE_APPS = [
    # Left column - Browsers (indices 0-3)
    {'display_name': 'Chrome', 'processes': ['chrome.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'chrome_icon.png')},
    {'display_name': 'Firefox', 'processes': ['firefox.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'firefox_icon.png')},
    {'display_name': 'Edge', 'processes': ['msedge.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'edge_icon.png')},
    {'display_name': 'Opera', 'processes': ['opera.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'opera_icon.png')},
    # Middle column - Cloud/Media (indices 4-7)
    {'display_name': 'Spotify', 'processes': ['spotify.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'spotify_icon.png')},
    {'display_name': 'OneDrive', 'processes': ['OneDrive.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'onedrive_icon.png')},
    {'display_name': 'Google Drive', 'processes': ['GoogleDriveFS.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'googledrive_icon.png')},
    {'display_name': 'Dropbox', 'processes': ['Dropbox.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'dropbox_icon.png')},
    # Right column - Gaming Utilities (indices 8-11)
    {'display_name': 'Wallpaper Engine', 'processes': ['wallpaper64.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'wallpaperengine_icon.png')},
    {'display_name': 'iCUE', 'processes': ['iCUE.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'icue_icon.png')},
    {'display_name': 'Razer Synapse', 'processes': ['RazerCentralService.exe', 'Razer Synapse 3.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'razer_icon.png')},
    {'display_name': 'NZXT CAM', 'processes': ['NZXT CAM.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'nzxtcam_icon.png')}
]


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    else:
        default_selected = ["WhatsApp", "Telegram", "Microsoft Teams", "Facebook Messenger", "Slack", "Signal",
                            "WeChat"]
        default_resource_selected = ["Spotify", "OneDrive", "Google Drive", "Dropbox", "Wallpaper Engine",
                                     "iCUE", "Razer Synapse", "NZXT CAM"]
        return {'selected_notification_apps': default_selected, 'custom_processes': [],
                'selected_resource_apps': default_resource_selected, 'custom_resource_processes': [],
                'launch_at_startup': False, 'launch_settings_on_start': True,
                'close_on_startup': True, 'close_on_hotkey': True, 'relaunch_on_exit': True,
                'resource_close_on_startup': True, 'resource_close_on_hotkey': True, 'resource_relaunch_on_exit': False,
                'enable_playtime_summary': True, 'enable_debug_mode': False, 'system_audio_level': 33,
                'enable_system_audio': False,
                'game_audio_level': 100, 'enable_game_audio': False,
                'enable_during_power': False, 'during_power_plan': 'High Performance',
                'enable_after_power': False, 'after_power_plan': 'Balanced',
                'enable_game_mode_start': True, 'enable_game_mode_end': False}


def save_settings(selected_notification_apps, customs, selected_resource_apps, resource_customs, launch_startup,
                  launch_settings_on_start, close_on_startup, close_on_hotkey, relaunch_on_exit,
                  resource_close_on_startup, resource_close_on_hotkey, resource_relaunch_on_exit,
                  enable_playtime_summary, enable_debug_mode, system_audio_level, enable_system_audio,
                  game_audio_level, enable_game_audio, enable_during_power, during_power_plan,
                  enable_after_power, after_power_plan, enable_game_mode_start, enable_game_mode_end):
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


root = ctk.CTk()
root.withdraw()
root.title("Vapor Settings")
root.geometry("700x900")
root.resizable(False, False)

icon_path = os.path.join(base_dir, 'Images', 'exe_icon.ico')
if os.path.exists(icon_path):
    root.iconbitmap(icon_path)

root.update()
hwnd = int(root.wm_frame(), 16)
style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
new_style = style & ~win32con.WS_SYSMENU
win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, new_style)

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
window_width = 700
window_height = 900
x = (screen_width - window_width) // 2
y = (screen_height - window_height) // 2
root.geometry(f"{window_width}x{window_height}+{x}+{y}")

root.deiconify()

current_settings = load_settings()
selected_notification_apps = current_settings.get('selected_notification_apps', current_settings.get('selected_apps', []))
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

tabview = ctk.CTkTabview(master=root)
tabview.pack(pady=10, padx=10, fill="both", expand=True)

notifications_tab = tabview.add("Notifications")
resources_tab = tabview.add(" Resources ")
preferences_tab = tabview.add("Preferences ")
help_tab = tabview.add("   Help   ")
about_tab = tabview.add("  About  ")

# ===== Content for Notifications Tab =====
notif_scroll_frame = ctk.CTkScrollableFrame(master=notifications_tab, fg_color="transparent")
notif_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

notification_title = ctk.CTkLabel(master=notif_scroll_frame, text="Notification Management",
                                  font=("Calibri", 24, "bold"))
notification_title.pack(pady=(10, 5), anchor='center')

notif_description = ctk.CTkLabel(master=notif_scroll_frame,
                                  text="Control which messaging and notification apps are closed when you start gaming.",
                                  font=("Calibri", 12), text_color="gray60")
notif_description.pack(pady=(0, 15), anchor='center')

notif_sep1 = ctk.CTkFrame(master=notif_scroll_frame, height=2, fg_color="gray50")
notif_sep1.pack(fill="x", padx=40, pady=10)

behavior_title = ctk.CTkLabel(master=notif_scroll_frame, text="Behavior Settings", font=("Calibri", 16, "bold"))
behavior_title.pack(pady=(10, 10), anchor='center')

options_frame = ctk.CTkFrame(master=notif_scroll_frame, fg_color="transparent")
options_frame.pack(pady=10, padx=20)

close_startup_label = ctk.CTkLabel(master=options_frame, text="Close Apps When Game Starts:",
                                   font=("Calibri", 13))
close_startup_label.grid(row=0, column=0, pady=8, padx=10, sticky='w')

close_startup_var = tk.StringVar(value="Enabled" if close_on_startup else "Disabled")
ctk.CTkRadioButton(master=options_frame, text="Enabled", variable=close_startup_var, value="Enabled",
                   font=("Calibri", 13)).grid(row=0, column=1, pady=8, padx=15)
ctk.CTkRadioButton(master=options_frame, text="Disabled", variable=close_startup_var, value="Disabled",
                   font=("Calibri", 13)).grid(row=0, column=2, pady=8, padx=15)

close_hotkey_label = ctk.CTkLabel(master=options_frame, text="Close Apps With Hotkey (Ctrl+Alt+K):",
                                  font=("Calibri", 13))
close_hotkey_label.grid(row=1, column=0, pady=8, padx=10, sticky='w')

close_hotkey_var = tk.StringVar(value="Enabled" if close_on_hotkey else "Disabled")
ctk.CTkRadioButton(master=options_frame, text="Enabled", variable=close_hotkey_var, value="Enabled",
                   font=("Calibri", 13)).grid(row=1, column=1, pady=8, padx=15)
ctk.CTkRadioButton(master=options_frame, text="Disabled", variable=close_hotkey_var, value="Disabled",
                   font=("Calibri", 13)).grid(row=1, column=2, pady=8, padx=15)

relaunch_exit_label = ctk.CTkLabel(master=options_frame, text="Relaunch Apps When Game Ends:",
                                   font=("Calibri", 13))
relaunch_exit_label.grid(row=2, column=0, pady=8, padx=10, sticky='w')

relaunch_exit_var = tk.StringVar(value="Enabled" if relaunch_on_exit else "Disabled")
ctk.CTkRadioButton(master=options_frame, text="Enabled", variable=relaunch_exit_var, value="Enabled",
                   font=("Calibri", 13)).grid(row=2, column=1, pady=8, padx=15)
ctk.CTkRadioButton(master=options_frame, text="Disabled", variable=relaunch_exit_var, value="Disabled",
                   font=("Calibri", 13)).grid(row=2, column=2, pady=8, padx=15)

notif_sep2 = ctk.CTkFrame(master=notif_scroll_frame, height=2, fg_color="gray50")
notif_sep2.pack(fill="x", padx=40, pady=15)

apps_subtitle = ctk.CTkLabel(master=notif_scroll_frame, text="Select Apps to Manage", font=("Calibri", 16, "bold"))
apps_subtitle.pack(pady=(10, 5), anchor='center')

apps_hint = ctk.CTkLabel(master=notif_scroll_frame,
                          text="Toggle the apps you want Vapor to close during gaming sessions.",
                          font=("Calibri", 11), text_color="gray60")
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
        ctk.CTkLabel(master=row_frame, text="●", font=("Calibri", 14)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_notification_apps)
    switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 13))
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
        ctk.CTkLabel(master=row_frame, text="●", font=("Calibri", 14)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_notification_apps)
    switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 13))
    switch.pack(side="left")


def on_all_apps_toggle():
    state = all_apps_var.get()
    for var in switch_vars.values():
        var.set(state)


all_apps_var = tk.BooleanVar(value=all(display_name in selected_notification_apps for display_name in
                                       [app['display_name'] for app in BUILT_IN_APPS]))

all_apps_switch = ctk.CTkSwitch(master=notif_scroll_frame, text="Toggle All Apps", variable=all_apps_var,
                                command=on_all_apps_toggle, font=("Calibri", 13))
all_apps_switch.pack(pady=10, anchor='center')

notif_sep3 = ctk.CTkFrame(master=notif_scroll_frame, height=2, fg_color="gray50")
notif_sep3.pack(fill="x", padx=40, pady=15)

custom_title = ctk.CTkLabel(master=notif_scroll_frame, text="Custom Processes", font=("Calibri", 16, "bold"))
custom_title.pack(pady=(10, 5), anchor='center')

custom_label = ctk.CTkLabel(master=notif_scroll_frame,
                             text="Add additional processes to close (comma-separated, e.g.: MyApp1.exe, MyApp2.exe)",
                             font=("Calibri", 11), text_color="gray60")
custom_label.pack(pady=(0, 10), anchor='center')

custom_entry = ctk.CTkEntry(master=notif_scroll_frame, width=550, font=("Calibri", 13),
                             placeholder_text="Enter custom process names...")
custom_entry.insert(0, ','.join(custom_processes))
custom_entry.pack(pady=(0, 20), anchor='center')

# ===== Content for Preferences Tab =====
pref_scroll_frame = ctk.CTkScrollableFrame(master=preferences_tab, fg_color="transparent")
pref_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

preferences_title = ctk.CTkLabel(master=pref_scroll_frame, text="Preferences", font=("Calibri", 24, "bold"))
preferences_title.pack(pady=(10, 5), anchor='center')

pref_description = ctk.CTkLabel(master=pref_scroll_frame,
                                 text="Customize Vapor's behavior, audio settings, and power management options.",
                                 font=("Calibri", 12), text_color="gray60")
pref_description.pack(pady=(0, 15), anchor='center')

pref_sep1 = ctk.CTkFrame(master=pref_scroll_frame, height=2, fg_color="gray50")
pref_sep1.pack(fill="x", padx=40, pady=10)

general_title = ctk.CTkLabel(master=pref_scroll_frame, text="General Settings", font=("Calibri", 16, "bold"))
general_title.pack(pady=(10, 10), anchor='center')

general_frame = ctk.CTkFrame(master=pref_scroll_frame, fg_color="transparent")
general_frame.pack(pady=5, padx=40, anchor='center')

launch_settings_on_start_var = tk.BooleanVar(value=launch_settings_on_start)
launch_settings_on_start_switch = ctk.CTkSwitch(master=general_frame, text="Open Settings Window on Vapor Start",
                                                variable=launch_settings_on_start_var, font=("Calibri", 13))
launch_settings_on_start_switch.pack(pady=5, anchor='w')

playtime_summary_var = tk.BooleanVar(value=enable_playtime_summary)
playtime_summary_switch = ctk.CTkSwitch(master=general_frame, text="Show Playtime Summary After Gaming",
                                        variable=playtime_summary_var, font=("Calibri", 13))
playtime_summary_switch.pack(pady=5, anchor='w')

startup_var = tk.BooleanVar(value=launch_at_startup)
startup_switch = ctk.CTkSwitch(master=general_frame, text="Launch Vapor at System Startup", variable=startup_var,
                               font=("Calibri", 13))
startup_switch.pack(pady=5, anchor='w')

debug_mode_var = tk.BooleanVar(value=enable_debug_mode)
debug_mode_switch = ctk.CTkSwitch(master=general_frame, text="Enable Debug Console Window",
                                  variable=debug_mode_var, font=("Calibri", 13))
debug_mode_switch.pack(pady=5, anchor='w')

pref_sep2 = ctk.CTkFrame(master=pref_scroll_frame, height=2, fg_color="gray50")
pref_sep2.pack(fill="x", padx=40, pady=15)

audio_title = ctk.CTkLabel(master=pref_scroll_frame, text="Audio Settings", font=("Calibri", 16, "bold"))
audio_title.pack(pady=(10, 5), anchor='center')

audio_hint = ctk.CTkLabel(master=pref_scroll_frame,
                           text="Automatically adjust volume levels when a game starts.",
                           font=("Calibri", 11), text_color="gray60")
audio_hint.pack(pady=(0, 10), anchor='center')

audio_frame = ctk.CTkFrame(master=pref_scroll_frame, fg_color="transparent")
audio_frame.pack(pady=10, anchor='center')

system_audio_column = ctk.CTkFrame(master=audio_frame, fg_color="transparent")
system_audio_column.pack(side="left", padx=40)

system_audio_label = ctk.CTkLabel(master=system_audio_column, text="System Volume", font=("Calibri", 14, "bold"))
system_audio_label.pack(anchor='center')

system_audio_slider_var = tk.IntVar(value=system_audio_level)
system_audio_slider = ctk.CTkSlider(master=system_audio_column, from_=0, to=100, number_of_steps=100,
                                    variable=system_audio_slider_var, width=180)
system_audio_slider.pack(pady=5, anchor='center')

system_current_value_label = ctk.CTkLabel(master=system_audio_column, text=f"{system_audio_level}%",
                                          font=("Calibri", 13))
system_current_value_label.pack(anchor='center')


def update_system_audio_label(value):
    system_current_value_label.configure(text=f"{int(value)}%")


system_audio_slider.configure(command=update_system_audio_label)

enable_system_audio_var = tk.BooleanVar(value=enable_system_audio)
enable_system_audio_switch = ctk.CTkSwitch(master=system_audio_column, text="Enable", variable=enable_system_audio_var,
                                           font=("Calibri", 13))
enable_system_audio_switch.pack(pady=8, anchor='center')

game_audio_column = ctk.CTkFrame(master=audio_frame, fg_color="transparent")
game_audio_column.pack(side="left", padx=40)

game_audio_label = ctk.CTkLabel(master=game_audio_column, text="Game Volume", font=("Calibri", 14, "bold"))
game_audio_label.pack(anchor='center')

game_audio_slider_var = tk.IntVar(value=game_audio_level)
game_audio_slider = ctk.CTkSlider(master=game_audio_column, from_=0, to=100, number_of_steps=100,
                                  variable=game_audio_slider_var, width=180)
game_audio_slider.pack(pady=5, anchor='center')

game_current_value_label = ctk.CTkLabel(master=game_audio_column, text=f"{game_audio_level}%", font=("Calibri", 13))
game_current_value_label.pack(anchor='center')


def update_game_audio_label(value):
    game_current_value_label.configure(text=f"{int(value)}%")


game_audio_slider.configure(command=update_game_audio_label)

enable_game_audio_var = tk.BooleanVar(value=enable_game_audio)
enable_game_audio_switch = ctk.CTkSwitch(master=game_audio_column, text="Enable", variable=enable_game_audio_var,
                                         font=("Calibri", 13))
enable_game_audio_switch.pack(pady=8, anchor='center')

pref_sep3 = ctk.CTkFrame(master=pref_scroll_frame, height=2, fg_color="gray50")
pref_sep3.pack(fill="x", padx=40, pady=15)

power_title = ctk.CTkLabel(master=pref_scroll_frame, text="Power Management", font=("Calibri", 16, "bold"))
power_title.pack(pady=(10, 5), anchor='center')

power_hint = ctk.CTkLabel(master=pref_scroll_frame,
                           text="Automatically switch power plans when gaming starts and ends.",
                           font=("Calibri", 11), text_color="gray60")
power_hint.pack(pady=(0, 10), anchor='center')

power_frame = ctk.CTkFrame(master=pref_scroll_frame, fg_color="transparent")
power_frame.pack(pady=10, anchor='center')

during_power_column = ctk.CTkFrame(master=power_frame, fg_color="transparent")
during_power_column.pack(side="left", padx=40)

during_power_label = ctk.CTkLabel(master=during_power_column, text="While Gaming", font=("Calibri", 14, "bold"))
during_power_label.pack(anchor='center')

during_power_var = tk.StringVar(value=during_power_plan)
during_power_combobox = ctk.CTkComboBox(master=during_power_column,
                                        values=["High Performance", "Balanced", "Power saver"],
                                        variable=during_power_var, width=160)
during_power_combobox.pack(pady=5, anchor='center')

enable_during_power_var = tk.BooleanVar(value=enable_during_power)
enable_during_power_switch = ctk.CTkSwitch(master=during_power_column, text="Enable", variable=enable_during_power_var,
                                           font=("Calibri", 13))
enable_during_power_switch.pack(pady=8, anchor='center')

after_power_column = ctk.CTkFrame(master=power_frame, fg_color="transparent")
after_power_column.pack(side="left", padx=40)

after_power_label = ctk.CTkLabel(master=after_power_column, text="After Gaming", font=("Calibri", 14, "bold"))
after_power_label.pack(anchor='center')

after_power_var = tk.StringVar(value=after_power_plan)
after_power_combobox = ctk.CTkComboBox(master=after_power_column,
                                       values=["High Performance", "Balanced", "Power saver"],
                                       variable=after_power_var, width=160)
after_power_combobox.pack(pady=5, anchor='center')

enable_after_power_var = tk.BooleanVar(value=enable_after_power)
enable_after_power_switch = ctk.CTkSwitch(master=after_power_column, text="Enable", variable=enable_after_power_var,
                                          font=("Calibri", 13))
enable_after_power_switch.pack(pady=8, anchor='center')

pref_sep4 = ctk.CTkFrame(master=pref_scroll_frame, height=2, fg_color="gray50")
pref_sep4.pack(fill="x", padx=40, pady=15)

game_mode_title = ctk.CTkLabel(master=pref_scroll_frame, text="Windows Game Mode", font=("Calibri", 16, "bold"))
game_mode_title.pack(pady=(10, 5), anchor='center')

game_mode_hint = ctk.CTkLabel(master=pref_scroll_frame,
                               text="Control Windows Game Mode automatically during gaming sessions.",
                               font=("Calibri", 11), text_color="gray60")
game_mode_hint.pack(pady=(0, 10), anchor='center')

game_mode_frame = ctk.CTkFrame(master=pref_scroll_frame, fg_color="transparent")
game_mode_frame.pack(pady=10, anchor='center')

enable_game_mode_start_var = tk.BooleanVar(value=enable_game_mode_start)
enable_game_mode_start_switch = ctk.CTkSwitch(master=game_mode_frame, text="Enable Game Mode When Game Starts",
                                              variable=enable_game_mode_start_var, font=("Calibri", 13))
enable_game_mode_start_switch.pack(pady=5, anchor='w')

enable_game_mode_end_var = tk.BooleanVar(value=enable_game_mode_end)
enable_game_mode_end_switch = ctk.CTkSwitch(master=game_mode_frame, text="Disable Game Mode When Game Ends",
                                            variable=enable_game_mode_end_var, font=("Calibri", 13))
enable_game_mode_end_switch.pack(pady=5, anchor='w')

# ===== Content for Resources Tab =====
res_scroll_frame = ctk.CTkScrollableFrame(master=resources_tab, fg_color="transparent")
res_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

resource_title = ctk.CTkLabel(master=res_scroll_frame, text="Resource Management", font=("Calibri", 24, "bold"))
resource_title.pack(pady=(10, 5), anchor='center')

res_description = ctk.CTkLabel(master=res_scroll_frame,
                                text="Control which resource-intensive apps are closed to free up system resources during gaming.",
                                font=("Calibri", 12), text_color="gray60")
res_description.pack(pady=(0, 15), anchor='center')

res_sep1 = ctk.CTkFrame(master=res_scroll_frame, height=2, fg_color="gray50")
res_sep1.pack(fill="x", padx=40, pady=10)

res_behavior_title = ctk.CTkLabel(master=res_scroll_frame, text="Behavior Settings", font=("Calibri", 16, "bold"))
res_behavior_title.pack(pady=(10, 10), anchor='center')

resource_options_frame = ctk.CTkFrame(master=res_scroll_frame, fg_color="transparent")
resource_options_frame.pack(pady=10, padx=20)

resource_close_startup_label = ctk.CTkLabel(master=resource_options_frame,
                                            text="Close Apps When Game Starts:",
                                            font=("Calibri", 13))
resource_close_startup_label.grid(row=0, column=0, pady=8, padx=10, sticky='w')

resource_close_startup_var = tk.StringVar(value="Enabled" if resource_close_on_startup else "Disabled")
ctk.CTkRadioButton(master=resource_options_frame, text="Enabled", variable=resource_close_startup_var, value="Enabled",
                   font=("Calibri", 13)).grid(row=0, column=1, pady=8, padx=15)
ctk.CTkRadioButton(master=resource_options_frame, text="Disabled", variable=resource_close_startup_var,
                   value="Disabled", font=("Calibri", 13)).grid(row=0, column=2, pady=8, padx=15)

resource_close_hotkey_label = ctk.CTkLabel(master=resource_options_frame,
                                           text="Close Apps With Hotkey (Ctrl+Alt+K):", font=("Calibri", 13))
resource_close_hotkey_label.grid(row=1, column=0, pady=8, padx=10, sticky='w')

resource_close_hotkey_var = tk.StringVar(value="Enabled" if resource_close_on_hotkey else "Disabled")
ctk.CTkRadioButton(master=resource_options_frame, text="Enabled", variable=resource_close_hotkey_var, value="Enabled",
                   font=("Calibri", 13)).grid(row=1, column=1, pady=8, padx=15)
ctk.CTkRadioButton(master=resource_options_frame, text="Disabled", variable=resource_close_hotkey_var, value="Disabled",
                   font=("Calibri", 13)).grid(row=1, column=2, pady=8, padx=15)

resource_relaunch_exit_label = ctk.CTkLabel(master=resource_options_frame,
                                            text="Relaunch Apps When Game Ends:",
                                            font=("Calibri", 13))
resource_relaunch_exit_label.grid(row=2, column=0, pady=8, padx=10, sticky='w')

resource_relaunch_exit_var = tk.StringVar(value="Enabled" if resource_relaunch_on_exit else "Disabled")
ctk.CTkRadioButton(master=resource_options_frame, text="Enabled", variable=resource_relaunch_exit_var, value="Enabled",
                   font=("Calibri", 13)).grid(row=2, column=1, pady=8, padx=15)
ctk.CTkRadioButton(master=resource_options_frame, text="Disabled", variable=resource_relaunch_exit_var,
                   value="Disabled", font=("Calibri", 13)).grid(row=2, column=2, pady=8, padx=15)

res_sep2 = ctk.CTkFrame(master=res_scroll_frame, height=2, fg_color="gray50")
res_sep2.pack(fill="x", padx=40, pady=15)

resource_apps_subtitle = ctk.CTkLabel(master=res_scroll_frame, text="Select Apps to Manage", font=("Calibri", 16, "bold"))
resource_apps_subtitle.pack(pady=(10, 5), anchor='center')

res_apps_hint = ctk.CTkLabel(master=res_scroll_frame,
                              text="Toggle the resource-heavy apps you want Vapor to close during gaming sessions.",
                              font=("Calibri", 11), text_color="gray60")
res_apps_hint.pack(pady=(0, 10), anchor='center')

resource_app_frame = ctk.CTkFrame(master=res_scroll_frame, fg_color="transparent")
resource_app_frame.pack(pady=10, padx=10)

resource_left_column = ctk.CTkFrame(master=resource_app_frame, fg_color="transparent")
resource_left_column.pack(side="left", padx=10)

resource_middle_column = ctk.CTkFrame(master=resource_app_frame, fg_color="transparent")
resource_middle_column.pack(side="left", padx=10)

resource_right_column = ctk.CTkFrame(master=resource_app_frame, fg_color="transparent")
resource_right_column.pack(side="left", padx=10)

# Left column - Browsers (indices 0-3)
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
        ctk.CTkLabel(master=row_frame, text="●", font=("Calibri", 14)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_resource_apps)
    resource_switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 13))
    switch.pack(side="left")

# Middle column - Cloud/Media (indices 4-7)
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
        ctk.CTkLabel(master=row_frame, text="●", font=("Calibri", 14)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_resource_apps)
    resource_switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 13))
    switch.pack(side="left")

# Right column - Gaming Utilities (indices 8-11)
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
        ctk.CTkLabel(master=row_frame, text="●", font=("Calibri", 14)).pack(side="left", padx=5)

    var = tk.BooleanVar(value=display_name in selected_resource_apps)
    resource_switch_vars[display_name] = var
    switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 13))
    switch.pack(side="left")


def on_resource_all_apps_toggle():
    state = resource_all_apps_var.get()
    for var in resource_switch_vars.values():
        var.set(state)


resource_all_apps_var = tk.BooleanVar(value=all(display_name in selected_resource_apps for display_name in
                                                [app['display_name'] for app in BUILT_IN_RESOURCE_APPS]))

resource_all_apps_switch = ctk.CTkSwitch(master=res_scroll_frame, text="Toggle All Apps", variable=resource_all_apps_var,
                                         command=on_resource_all_apps_toggle, font=("Calibri", 13))
resource_all_apps_switch.pack(pady=10, anchor='center')

res_sep3 = ctk.CTkFrame(master=res_scroll_frame, height=2, fg_color="gray50")
res_sep3.pack(fill="x", padx=40, pady=15)

res_custom_title = ctk.CTkLabel(master=res_scroll_frame, text="Custom Processes", font=("Calibri", 16, "bold"))
res_custom_title.pack(pady=(10, 5), anchor='center')

custom_resource_label = ctk.CTkLabel(master=res_scroll_frame,
                                      text="Add additional processes to close (comma-separated, e.g.: MyApp1.exe, MyApp2.exe)",
                                      font=("Calibri", 11), text_color="gray60")
custom_resource_label.pack(pady=(0, 10), anchor='center')

custom_resource_entry = ctk.CTkEntry(master=res_scroll_frame, width=550, font=("Calibri", 13),
                                      placeholder_text="Enter custom process names...")
custom_resource_entry.insert(0, ','.join(custom_resource_processes))
custom_resource_entry.pack(pady=(0, 20), anchor='center')

# ===== Content for Help Tab =====
help_scroll_frame = ctk.CTkScrollableFrame(master=help_tab, fg_color="transparent")
help_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

help_title = ctk.CTkLabel(master=help_scroll_frame, text="Help & Support", font=("Calibri", 24, "bold"))
help_title.pack(pady=(10, 5), anchor='center')

help_description = ctk.CTkLabel(master=help_scroll_frame,
                                 text="Get help with Vapor, learn how it works, and troubleshoot common issues.",
                                 font=("Calibri", 12), text_color="gray60")
help_description.pack(pady=(0, 15), anchor='center')

help_sep1 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
help_sep1.pack(fill="x", padx=40, pady=10)

how_title = ctk.CTkLabel(master=help_scroll_frame, text="How Vapor Works", font=("Calibri", 16, "bold"))
how_title.pack(pady=(10, 10), anchor='center')

how_text = """Vapor runs quietly in your system tray and monitors Steam for game launches. When you start 
a Steam game, Vapor automatically:

  •  Closes notification apps (like Discord, Slack, Teams) to prevent interruptions
  •  Closes resource-heavy apps (like browsers, cloud sync) to free up RAM and CPU
  •  Adjusts your audio levels (if enabled)
  •  Switches your power plan (if enabled)
  •  Enables Windows Game Mode (if enabled)

When you exit your game, Vapor reverses these changes and relaunches your closed apps."""

how_label = ctk.CTkLabel(master=help_scroll_frame, text=how_text, font=("Calibri", 12),
                          wraplength=580, justify="left")
how_label.pack(pady=10, anchor='center')

help_sep2 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
help_sep2.pack(fill="x", padx=40, pady=15)

shortcuts_title = ctk.CTkLabel(master=help_scroll_frame, text="Keyboard Shortcuts", font=("Calibri", 16, "bold"))
shortcuts_title.pack(pady=(10, 10), anchor='center')

shortcuts_text = """Ctrl + Alt + K  —  Manually close all selected notification and resource apps

This hotkey works independently of game detection. When enabled in the Notifications 
or Resources tab, pressing this combination will immediately close all toggled apps 
in that category. This is useful for quickly silencing distractions before a meeting, 
stream, or any focus session — even when you're not gaming."""

shortcuts_label = ctk.CTkLabel(master=help_scroll_frame, text=shortcuts_text, font=("Calibri", 12),
                                wraplength=580, justify="left")
shortcuts_label.pack(pady=10, anchor='center')

help_sep3 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
help_sep3.pack(fill="x", padx=40, pady=15)

trouble_title = ctk.CTkLabel(master=help_scroll_frame, text="Troubleshooting", font=("Calibri", 16, "bold"))
trouble_title.pack(pady=(10, 10), anchor='center')

trouble_text = """If Vapor isn't working as expected, try these steps:

  •  Make sure Steam is running before launching games
  •  Check that the apps you want managed are toggled ON in the Notifications/Resources tabs
  •  Ensure Vapor is running (look for the icon in your system tray)
  •  Try clicking "Reset to Defaults" below to restore default settings

If issues persist, enable Debug Mode in Preferences to see detailed logs."""

trouble_label = ctk.CTkLabel(master=help_scroll_frame, text=trouble_text, font=("Calibri", 12),
                              wraplength=580, justify="left")
trouble_label.pack(pady=10, anchor='center')

help_sep4 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
help_sep4.pack(fill="x", padx=40, pady=15)

reset_title = ctk.CTkLabel(master=help_scroll_frame, text="Reset Settings", font=("Calibri", 16, "bold"))
reset_title.pack(pady=(10, 5), anchor='center')

reset_hint = ctk.CTkLabel(master=help_scroll_frame,
                           text="Restore all settings to their default values.",
                           font=("Calibri", 11), text_color="gray60")
reset_hint.pack(pady=(0, 10), anchor='center')


def rebuild_settings():
    default_selected = ["WhatsApp", "Telegram", "Microsoft Teams", "Facebook Messenger", "Slack", "Signal", "WeChat"]
    default_resource_selected = ["Spotify", "OneDrive", "Google Drive", "Dropbox", "Wallpaper Engine",
                                 "iCUE", "Razer Synapse", "NZXT CAM"]

    for display_name in switch_vars:
        switch_vars[display_name].set(display_name in default_selected)
    custom_entry.delete(0, 'end')

    for display_name in resource_switch_vars:
        resource_switch_vars[display_name].set(display_name in default_resource_selected)
    custom_resource_entry.delete(0, 'end')

    startup_var.set(False)
    launch_settings_on_start_var.set(True)
    close_startup_var.set("Enabled")
    close_hotkey_var.set("Enabled")
    relaunch_exit_var.set("Enabled")
    resource_close_startup_var.set("Enabled")
    resource_close_hotkey_var.set("Enabled")
    resource_relaunch_exit_var.set("Disabled")
    playtime_summary_var.set(True)
    debug_mode_var.set(False)
    system_audio_slider_var.set(33)
    update_system_audio_label(33)
    enable_system_audio_var.set(False)
    game_audio_slider_var.set(100)
    update_game_audio_label(100)
    enable_game_audio_var.set(False)
    enable_during_power_var.set(False)
    during_power_var.set("High Performance")
    enable_after_power_var.set(False)
    after_power_var.set("Balanced")
    enable_game_mode_start_var.set(True)
    enable_game_mode_end_var.set(False)

    on_save()

    win11toast.notify(body="Settings have been reset to defaults.", app_id='Vapor - Streamline Gaming',
                      duration='short', icon=TRAY_ICON_PATH, audio={'silent': 'true'})


rebuild_button = ctk.CTkButton(master=help_scroll_frame, text="Reset to Defaults", command=rebuild_settings, corner_radius=10,
                               fg_color="#c9302c", hover_color="#a02622", text_color="white", width=200, font=("Calibri", 14))
rebuild_button.pack(pady=(5, 20), anchor='center')

# ===== Content for About Tab =====
about_scroll_frame = ctk.CTkScrollableFrame(master=about_tab, fg_color="transparent")
about_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

about_title = ctk.CTkLabel(master=about_scroll_frame, text="Vapor", font=("Calibri", 28, "bold"))
about_title.pack(pady=(10, 5), anchor='center')

version_label = ctk.CTkLabel(master=about_scroll_frame, text=f"Version {CURRENT_VERSION}", font=("Calibri", 14))
version_label.pack(pady=(0, 15), anchor='center')

description_text = """Vapor is a lightweight utility designed to enhance your gaming experience on Windows. 
It automatically detects when you launch a Steam game and optimizes your system by closing 
distracting notification apps and resource-heavy applications. When you're done gaming, 
Vapor seamlessly relaunches your closed apps, so you can pick up right where you left off.

Features include customizable app management, audio controls, power plan switching, 
Windows Game Mode integration, and playtime tracking with session summaries."""

description_label = ctk.CTkLabel(master=about_scroll_frame, text=description_text, font=("Calibri", 13),
                                  wraplength=620, justify="center")
description_label.pack(pady=10, anchor='center')

separator1 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
separator1.pack(fill="x", padx=40, pady=15)

developer_title = ctk.CTkLabel(master=about_scroll_frame, text="Developed by", font=("Calibri", 12))
developer_title.pack(pady=(5, 0), anchor='center')

developer_name = ctk.CTkLabel(master=about_scroll_frame, text="Greg Morton (@Master00Sniper)",
                               font=("Calibri", 16, "bold"))
developer_name.pack(pady=(0, 10), anchor='center')

bio_text = """This is my first software application! I'm a passionate gamer, Sr. Systems Administrator 
by profession, wine enthusiast, and proud small winery owner. Vapor was born from my own frustration 
with notifications interrupting epic gaming moments – I hope it enhances your gaming sessions as much as it has mine."""

bio_label = ctk.CTkLabel(master=about_scroll_frame, text=bio_text, font=("Calibri", 12),
                          wraplength=620, justify="center")
bio_label.pack(pady=10, anchor='center')

separator2 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
separator2.pack(fill="x", padx=40, pady=15)

contact_title = ctk.CTkLabel(master=about_scroll_frame, text="Contact & Connect", font=("Calibri", 14, "bold"))
contact_title.pack(pady=(5, 10), anchor='center')

email_label = ctk.CTkLabel(master=about_scroll_frame, text="📧  gkmorton1@gmail.com", font=("Calibri", 12))
email_label.pack(pady=2, anchor='center')

x_link_frame = ctk.CTkFrame(master=about_scroll_frame, fg_color="transparent")
x_link_frame.pack(pady=2, anchor='center')

x_icon_label = ctk.CTkLabel(master=x_link_frame, text="𝕏  ", font=("Calibri", 12))
x_icon_label.pack(side="left")

x_link_label = ctk.CTkLabel(master=x_link_frame, text="x.com/master00sniper", font=("Calibri", 12, "underline"),
                             text_color="#1DA1F2", cursor="hand2")
x_link_label.pack(side="left")
x_link_label.bind("<Button-1>", lambda e: os.startfile("https://x.com/master00sniper"))

x_handle_label = ctk.CTkLabel(master=x_link_frame, text="  •  @Master00Sniper", font=("Calibri", 12))
x_handle_label.pack(side="left")

separator3 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
separator3.pack(fill="x", padx=40, pady=15)

donate_title = ctk.CTkLabel(master=about_scroll_frame, text="Support Development", font=("Calibri", 14, "bold"))
donate_title.pack(pady=(5, 5), anchor='center')

donate_label = ctk.CTkLabel(master=about_scroll_frame, text="☕  Donation page coming soon!",
                             font=("Calibri", 12))
donate_label.pack(pady=5, anchor='center')

separator4 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
separator4.pack(fill="x", padx=40, pady=15)

copyright_label = ctk.CTkLabel(master=about_scroll_frame,
                                text=f"© 2024-2026 Greg Morton (@Master00Sniper). All Rights Reserved.",
                                font=("Calibri", 11))
copyright_label.pack(pady=(5, 5), anchor='center')

disclaimer_text = """DISCLAIMER: This software is provided "as is" without warranty of any kind, express or implied, 
including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. 
In no event shall the author be liable for any claim, damages, or other liability arising from the use of this software."""

disclaimer_label = ctk.CTkLabel(master=about_scroll_frame, text=disclaimer_text, font=("Calibri", 10),
                                 wraplength=620, justify="center", text_color="gray60")
disclaimer_label.pack(pady=(5, 20), anchor='center')

button_frame = ctk.CTkFrame(master=root, fg_color="transparent")
button_frame.pack(pady=20, fill='x', padx=40)

button_frame.grid_columnconfigure(0, weight=1)
button_frame.grid_columnconfigure(1, weight=0)
button_frame.grid_columnconfigure(2, weight=0)
button_frame.grid_columnconfigure(3, weight=0)
button_frame.grid_columnconfigure(4, weight=1)


def on_save():
    new_selected_notification_apps = [name for name, var in switch_vars.items() if var.get()]
    new_customs = [c.strip() for c in custom_entry.get().split(',') if c.strip()]
    new_selected_resource_apps = [name for name, var in resource_switch_vars.items() if var.get()]
    new_resource_customs = [c.strip() for c in custom_resource_entry.get().split(',') if c.strip()]
    new_launch_startup = startup_var.get()
    new_launch_settings_on_start = launch_settings_on_start_var.get()
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
    save_settings(new_selected_notification_apps, new_customs, new_selected_resource_apps, new_resource_customs,
                  new_launch_startup, new_launch_settings_on_start, new_close_on_startup, new_close_on_hotkey,
                  new_relaunch_on_exit, new_resource_close_on_startup, new_resource_close_on_hotkey,
                  new_resource_relaunch_on_exit, new_enable_playtime_summary, new_enable_debug_mode,
                  new_system_audio_level, new_enable_system_audio, new_game_audio_level, new_enable_game_audio,
                  new_enable_during_power, new_during_power_plan, new_enable_after_power, new_after_power_plan,
                  new_enable_game_mode_start, new_enable_game_mode_end)


def on_save_and_close():
    on_save()
    root.destroy()


def on_discard_and_close():
    root.destroy()


def on_stop_vapor():
    if main_pid:
        try:
            main_process = psutil.Process(main_pid)
            main_process.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    root.destroy()


save_button = ctk.CTkButton(master=button_frame, text="Save & Close", command=on_save_and_close, corner_radius=10,
                            fg_color="green", text_color="white", width=150, font=("Calibri", 14))
save_button.grid(row=0, column=1, padx=15, sticky='ew')

discard_button = ctk.CTkButton(master=button_frame, text="Discard & Close", command=on_discard_and_close, corner_radius=10,
                               fg_color="gray", text_color="white", width=150, font=("Calibri", 14))
discard_button.grid(row=0, column=2, padx=15, sticky='ew')

stop_button = ctk.CTkButton(master=button_frame, text="Stop Vapor", command=on_stop_vapor, corner_radius=10,
                            fg_color="red", text_color="white", width=150, font=("Calibri", 14))
stop_button.grid(row=0, column=3, padx=15, sticky='ew')


def check_main_process():
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

root.mainloop()