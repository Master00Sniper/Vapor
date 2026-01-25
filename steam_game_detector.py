# steam_game_detector.py

__version__ = "0.1.0"

# Keep these even if unused
import win32gui
import customtkinter

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
import sys
import re

# For system and game volume control
import comtypes
from comtypes import CLSCTX_ALL, COINIT_MULTITHREADED
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from pycaw.constants import CLSID_MMDeviceEnumerator
from pycaw.constants import EDataFlow, ERole
from pycaw.pycaw import IMMDeviceEnumerator

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# For notifications
import win11toast

# Path fix for frozen executable
application_path = ''
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(application_path)
sys.path.append(application_path)

# Added base_dir for frozen executable compatibility
base_dir = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))

# Use %APPDATA% for writable settings file
appdata_dir = os.path.join(os.getenv('APPDATA'), 'Vapor')
os.makedirs(appdata_dir, exist_ok=True)
SETTINGS_FILE = os.path.join(appdata_dir, 'vapor_settings.json')

TRAY_ICON_PATH = os.path.join(base_dir, 'Images', 'tray_icon.png')
UI_SCRIPT_PATH = os.path.join(base_dir, 'vapor_settings_ui.py')
STEAM_PATH = r"C:\Program Files (x86)\Steam\steamapps"

from updater import check_for_updates  # Assuming updater.py is in the same directory
__version__ = "1.0.0"  # Your current version - update this for each release

def load_process_names_and_startup():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            notification_processes = settings.get('notification_processes', [])
            resource_processes = settings.get('resource_processes', [])
            startup = settings.get('launch_at_startup', False)
            notification_close_on_startup = settings.get('close_on_startup', True)
            resource_close_on_startup = settings.get('resource_close_on_startup', True)
            notification_close_on_hotkey = settings.get('close_on_hotkey', False)
            resource_close_on_hotkey = settings.get('resource_close_on_hotkey', False)
            notification_relaunch_on_exit = settings.get('relaunch_on_exit', True)
            resource_relaunch_on_exit = settings.get('resource_relaunch_on_exit', True)
            enable_playtime_summary = settings.get('enable_playtime_summary', True)
            enable_system_audio = settings.get('enable_system_audio', False)
            system_audio_level = settings.get('system_audio_level', 50)
            enable_game_audio = settings.get('enable_game_audio', False)
            game_audio_level = settings.get('game_audio_level', 50)
            enable_during_power = settings.get('enable_during_power', False)
            during_power_plan = settings.get('during_power_plan', 'High Performance')
            enable_after_power = settings.get('enable_after_power', False)
            after_power_plan = settings.get('after_power_plan', 'Balanced')
            return notification_processes, resource_processes, startup, notification_close_on_startup, resource_close_on_startup, notification_close_on_hotkey, resource_close_on_hotkey, notification_relaunch_on_exit, resource_relaunch_on_exit, enable_playtime_summary, enable_system_audio, system_audio_level, enable_game_audio, game_audio_level, enable_during_power, during_power_plan, enable_after_power, after_power_plan
    else:
        print("No settings file found—using defaults.")
        default_notification = ['WhatsApp.Root.exe', 'Telegram.exe', 'ms-teams.exe', 'Messenger.exe', 'slack.exe', 'Signal.exe', 'WeChat.exe']
        default_resource = ['firefox.exe', 'msedge.exe', 'spotify.exe', 'OneDrive.exe', 'GoogleDriveFS.exe', 'Dropbox.exe', 'wallpaper64.exe']
        return default_notification, default_resource, False, True, True, True, True, True, False, True, False, 33, False, 100, False, 'High Performance', False, 'Balanced'


def set_startup(enabled):
    """Improved Startup Registry Function"""
    key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
    app_name = 'Vapor'

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)

        if enabled:
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(__file__)

            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            print("Vapor added to startup.")
        else:
            try:
                winreg.DeleteValue(key, app_name)
                print("Vapor removed from startup.")
            except FileNotFoundError:
                print("Vapor was not in startup—no change needed.")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Startup registry error (Try running as Administrator): {e}")


def get_running_steam_app_id():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        app_id, _ = winreg.QueryValueEx(key, "RunningAppID")
        winreg.CloseKey(key)
        return int(app_id)
    except:
        return 0


def get_game_name(app_id):
    if app_id == 0:
        return "No game running"
    try:
        url = f"http://store.steampowered.com/api/appdetails?appids={app_id}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if response.status_code == 200 and str(app_id) in data and data[str(app_id)]["success"]:
            return data[str(app_id)]["data"]["name"]
    except:
        pass
    return "Unknown"


def kill_processes(process_names, killed_processes):
    for name in process_names:
        killed_count = 0
        path_to_store = None
        for proc in psutil.process_iter(['name', 'exe']):
            if proc.info['name'].lower() == name.lower():
                try:
                    path = proc.info['exe']
                    if path and os.path.exists(path):
                        proc.terminate()
                        proc.wait(timeout=5)
                        killed_count += 1
                        if path_to_store is None:
                            path_to_store = path
                except psutil.TimeoutExpired:
                    proc.kill()
                except Exception as e:
                    print(f"Error closing {name}: {e}")

        if killed_count > 0:
            killed_processes[name] = path_to_store
            print(f"Closed {killed_count} instance(s) of {name}")


def relaunch_processes(killed_processes, relaunch_on_exit):
    if not relaunch_on_exit:
        return

    for name, path in list(killed_processes.items()):
        is_running = any(p.info['name'].lower() == name.lower() for p in psutil.process_iter(['name']))
        if is_running:
            killed_processes.pop(name, None)
            continue
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = win32con.SW_SHOWMINIMIZED
            subprocess.Popen(path, startupinfo=startupinfo)
            print(f"Relaunched {name} minimized")
            killed_processes.pop(name, None)
        except Exception as e:
            print(f"Failed to relaunch {name}: {e}")


def show_notification(message):
    icon_path = os.path.abspath(TRAY_ICON_PATH)
    win11toast.notify(body=message, app_id='Vapor - Streamline Gaming', duration='short', icon=icon_path, audio={'silent': 'true'})


def set_system_volume(level):
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
        print(f"✅ Set system volume to {int(level * 100)}% on active device")
    except Exception as e:
        print(f"❌ Failed to set system volume: {e}")
    finally:
        comtypes.CoUninitialize()


def get_power_plan_guid(plan_name):
    plan_map = {
        'Balanced': '381b4222-f694-41f0-9685-ff5bb260df2e',
        'High Performance': '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c',
        'Power saver': 'a1841308-3541-4fab-bc81-f71556f20b4a'
    }
    return plan_map.get(plan_name)


def set_power_plan(plan_name):
    guid = get_power_plan_guid(plan_name)
    if guid:
        try:
            subprocess.run(['powercfg', '/setactive', guid], check=True)
            print(f"Set power plan to {plan_name}")
        except Exception as e:
            print(f"Failed to set power plan to {plan_name}: {e}")
    else:
        print(f"Unknown power plan: {plan_name}")


def get_steam_path():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        path, _ = winreg.QueryValueEx(key, "SteamPath")
        winreg.CloseKey(key)
        return os.path.join(path, "steamapps")
    except Exception as e:
        print(f"Failed to auto-detect Steam path: {e}. Falling back to default.")
        return STEAM_PATH


def get_library_folders():
    main_steamapps = get_steam_path()
    steam_install_dir = os.path.dirname(main_steamapps)
    vdf_paths = [
        os.path.join(steam_install_dir, 'steamapps', 'libraryfolders.vdf'),
        os.path.join(steam_install_dir, 'config', 'libraryfolders.vdf')
    ]

    libraries = set()  # Use set to avoid duplicates
    for vdf_path in vdf_paths:
        print(f"Looking for VDF at: {vdf_path}")
        if os.path.exists(vdf_path):
            print(f"VDF found at {vdf_path}.")
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
                print(f"Error parsing VDF at {vdf_path}: {e}")
        else:
            print(f"VDF not found at {vdf_path}.")

    if os.path.exists(main_steamapps):
        libraries.add(main_steamapps)

    libraries = list(libraries)
    print(f"Library folders found: {libraries}")
    return libraries


def get_game_folder(app_id):
    libraries = get_library_folders()
    for lib in libraries:
        manifest_path = os.path.join(lib, f"appmanifest_{app_id}.acf")
        print(f"Checking manifest in {lib}: {manifest_path}")
        if os.path.exists(manifest_path):
            print(f"Manifest found in {lib}.")
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                installdir_match = re.search(r'"installdir"\s+"(.*?)"', content)
                if installdir_match:
                    installdir = installdir_match.group(1).replace('\\\\', '\\')
                    print(f"Parsed installdir: {installdir}")
                    game_folder = os.path.join(lib, "common", installdir)
                    if os.path.exists(game_folder):
                        print(f"Found game folder for AppID {app_id}: {game_folder}")
                        return game_folder
                    else:
                        print(f"Game folder not found: {game_folder}")
                else:
                    print(f"No 'installdir' found in manifest for AppID {app_id}")
            except Exception as e:
                print(f"Error parsing manifest {manifest_path}: {e}")
        else:
            print(f"Manifest not found in {lib}")
    print(f"Couldn't find manifest for AppID {app_id} across libraries: {libraries}")
    return None


def find_game_pids(game_folder):
    if not game_folder:
        return []
    pids = []
    base_procs = []
    for _ in range(10):
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
        time.sleep(3)
    else:
        print(f"Couldn't find any base processes in {game_folder} after waiting")

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
        print(f"Found {len(pids)} game PIDs (including children) in {game_folder}: {pids}")
        return pids
    print(f"Couldn't find any PIDs in {game_folder} after waiting")
    return []


def set_game_volume(game_pids, level):
    if not game_pids:
        return
    comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    try:
        level = max(0, min(100, level)) / 100.0
        max_attempts = 30  # Number of retry attempts
        retry_delay = 1  # Seconds to wait between retries

        for attempt in range(max_attempts):
            sessions = AudioUtilities.GetAllSessions()
            print(f"Attempt {attempt + 1}: All active audio sessions:")
            set_count = 0
            for session in sessions:
                pid = session.ProcessId
                try:
                    proc = psutil.Process(pid)
                    name = proc.name()
                    exe = proc.exe()
                except Exception as e:
                    name = "Unknown"
                    exe = "N/A"
                current_vol = session.SimpleAudioVolume.GetMasterVolume() if hasattr(session, 'SimpleAudioVolume') else 'N/A'
                print(f"Session PID: {pid}, Process Name: {name}, Exe: {exe}, Current Volume: {current_vol}")

                if session.ProcessId in game_pids:
                    if hasattr(session, 'SimpleAudioVolume'):
                        volume = session.SimpleAudioVolume
                        volume.SetMasterVolume(level, None)
                        set_count += 1
                        print(f"Set volume for session PID: {session.ProcessId} (Process Name: {name}) to {int(level * 100)}%")

            if set_count > 0:
                print(f"✅ Set game volume to {int(level * 100)}% for {set_count} session(s)")
                break  # Success, no need to retry
            else:
                if attempt < max_attempts - 1:
                    print(f"No audio sessions found for game PIDs on attempt {attempt + 1}—retrying in {retry_delay} seconds.")
                    time.sleep(retry_delay)
                else:
                    print("❌ Failed to find audio sessions for game PIDs after all attempts—might not be playing sound.")
    except Exception as e:
        print(f"❌ Failed to set game volume: {e}")
    finally:
        comtypes.CoUninitialize()


class SettingsFileHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback

    def on_modified(self, event):
        if event.src_path.endswith(SETTINGS_FILE):
            print(f"Settings file modified: {event.src_path}")
            self.callback()


def monitor_steam_games(stop_event, killed_notification, killed_resource):
    notification_processes, resource_processes, launch_at_startup, notification_close_on_startup, resource_close_on_startup, notification_close_on_hotkey, resource_close_on_hotkey, notification_relaunch_on_exit, resource_relaunch_on_exit, enable_playtime_summary, enable_system_audio, system_audio_level, enable_game_audio, game_audio_level, enable_during_power, during_power_plan, enable_after_power, after_power_plan = load_process_names_and_startup()
    print(f"Loaded notification processes: {notification_processes}")
    print(f"Loaded resource processes: {resource_processes}")

    set_startup(launch_at_startup)

    is_hotkey_registered = notification_close_on_hotkey or resource_close_on_hotkey
    if is_hotkey_registered:
        keyboard.add_hotkey('ctrl+alt+k', lambda: (
            kill_processes(notification_processes, killed_notification) if notification_close_on_hotkey else None,
            kill_processes(resource_processes, killed_resource) if resource_close_on_hotkey else None
        ))
        print("Hotkey ctrl+alt+k enabled.")

    previous_app_id = get_running_steam_app_id()
    start_time = None
    current_game_name = None
    if previous_app_id != 0:
        game_name = get_game_name(previous_app_id)
        print(f"Game already running at startup: {game_name} (AppID {previous_app_id})")
        start_time = time.time()
        current_game_name = game_name
        if notification_close_on_startup:
            kill_processes(notification_processes, killed_notification)
        if resource_close_on_startup:
            kill_processes(resource_processes, killed_resource)
        if enable_system_audio:
            set_system_volume(system_audio_level)
        if enable_game_audio:
            game_folder = get_game_folder(previous_app_id)
            game_pids = find_game_pids(game_folder)
            set_game_volume(game_pids, game_audio_level)
        if enable_during_power:
            set_power_plan(during_power_plan)

    print("Vapor is now monitoring Steam games...")

    show_notification("Vapor is now monitoring Steam games")

    # Define a callback to reload settings (extracted from your polling logic)
    def reload_settings():
        nonlocal notification_processes, resource_processes, launch_at_startup, notification_close_on_startup, \
            resource_close_on_startup, notification_close_on_hotkey, resource_close_on_hotkey, \
            notification_relaunch_on_exit, resource_relaunch_on_exit, enable_playtime_summary, \
            enable_system_audio, system_audio_level, enable_game_audio, game_audio_level, is_hotkey_registered, \
            enable_during_power, during_power_plan, enable_after_power, after_power_plan

        print("Settings file changed → reloading...")
        new_notification_processes, new_resource_processes, new_startup, new_notification_close_startup, \
            new_resource_close_startup, new_notification_close_hotkey, new_resource_close_hotkey, \
            new_notification_relaunch, new_resource_relaunch, new_enable_playtime_summary, \
            new_enable_system_audio, new_system_audio_level, new_enable_game_audio, \
            new_game_audio_level, new_enable_during_power, new_during_power_plan, \
            new_enable_after_power, new_after_power_plan = load_process_names_and_startup()

        notification_processes[:] = new_notification_processes
        resource_processes[:] = new_resource_processes

        if new_startup != launch_at_startup:
            launch_at_startup = new_startup
            set_startup(launch_at_startup)

        new_is_hotkey_registered = new_notification_close_hotkey or new_resource_close_hotkey
        if new_is_hotkey_registered != is_hotkey_registered:
            if new_is_hotkey_registered:
                keyboard.add_hotkey('ctrl+alt+k', lambda: (
                    kill_processes(notification_processes, killed_notification) if new_notification_close_hotkey else None,
                    kill_processes(resource_processes, killed_resource) if new_resource_close_hotkey else None
                ))
                print("Hotkey enabled.")
            else:
                try:
                    keyboard.remove_hotkey('ctrl+alt+k')
                except:
                    pass
                print("Hotkey disabled.")
            is_hotkey_registered = new_is_hotkey_registered

        notification_close_on_startup = new_notification_close_startup
        resource_close_on_startup = new_resource_close_startup
        notification_close_on_hotkey = new_notification_close_hotkey
        resource_close_on_hotkey = new_resource_close_hotkey
        notification_relaunch_on_exit = new_notification_relaunch
        resource_relaunch_on_exit = new_resource_relaunch
        enable_playtime_summary = new_enable_playtime_summary
        enable_system_audio = new_enable_system_audio
        system_audio_level = new_system_audio_level
        enable_game_audio = new_enable_game_audio
        game_audio_level = new_game_audio_level
        enable_during_power = new_enable_during_power
        during_power_plan = new_during_power_plan
        enable_after_power = new_enable_after_power
        after_power_plan = new_after_power_plan
        print("Settings reloaded successfully.")

    # Set up file watcher
    event_handler = SettingsFileHandler(reload_settings)
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(os.path.abspath(SETTINGS_FILE)) or '.', recursive=False)
    observer.start()

    try:
        while True:
            current_app_id = get_running_steam_app_id()

            if current_app_id != previous_app_id:
                if current_app_id == 0:
                    print("No Steam game running.")
                    if previous_app_id != 0:
                        if enable_playtime_summary and start_time is not None:
                            end_time = time.time()
                            duration = end_time - start_time
                            hours = int(duration // 3600)
                            minutes = int((duration % 3600) // 60)
                            closed_apps_count = len(killed_notification) + len(killed_resource)
                            if hours == 0:
                                message = f"You played {current_game_name} for {minutes} minutes. Vapor closed {closed_apps_count} apps when you started."
                            elif hours == 1:
                                message = f"You played {current_game_name} for {hours} hour and {minutes} minutes. Vapor closed {closed_apps_count} apps when you started."
                            else:
                                message = f"You played {current_game_name} for {hours} hours and {minutes} minutes. Vapor closed {closed_apps_count} apps when you started."
                            show_notification(message)

                        if notification_relaunch_on_exit:
                            relaunch_processes(killed_notification, notification_relaunch_on_exit)
                        if resource_relaunch_on_exit:
                            relaunch_processes(killed_resource, resource_relaunch_on_exit)

                        if enable_after_power:
                            set_power_plan(after_power_plan)

                        start_time = None
                        current_game_name = None
                else:
                    game_name = get_game_name(current_app_id)
                    print(f"Steam game started: {game_name} (AppID {current_app_id})")
                    if previous_app_id == 0:
                        start_time = time.time()
                        current_game_name = game_name
                        if notification_close_on_startup:
                            kill_processes(notification_processes, killed_notification)
                        if resource_close_on_startup:
                            kill_processes(resource_processes, killed_resource)
                        if enable_system_audio:
                            set_system_volume(system_audio_level)
                        if enable_game_audio:
                            game_folder = get_game_folder(current_app_id)
                            game_pids = find_game_pids(game_folder)
                            set_game_volume(game_pids, game_audio_level)
                        if enable_during_power:
                            set_power_plan(during_power_plan)

                previous_app_id = current_app_id

            if stop_event.wait(3):
                break

    finally:
        observer.stop()
        observer.join()


def open_settings(icon, query):
    try:
        if getattr(sys, 'frozen', False):
            subprocess.Popen([sys.executable, '--ui', str(os.getpid())])
        else:
            subprocess.Popen([sys.executable, __file__, '--ui', str(os.getpid())])

        print("Opened Vapor Settings UI")
    except Exception as e:
        print(f"Could not open settings: {e}")


def quit_app(icon, query):
    print("Quitting Vapor...")
    stop_event.set()
    try:
        keyboard.unhook_all()
    except:
        pass
    icon.stop()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--ui':
        # === UI MODE ===
        pid = int(sys.argv[2]) if len(sys.argv) > 2 else None
        os.chdir(base_dir)
        sys.path.append(base_dir)

        with open(UI_SCRIPT_PATH, 'r', encoding='utf-8') as f:
            ui_code = f.read()
        globals_dict = {'__name__': '__main__', '__file__': UI_SCRIPT_PATH, 'main_pid': pid}
        exec(ui_code, globals_dict)

    else:
        # === NORMAL TRAY MODE ===
        killed_notification = {}
        killed_resource = {}
        stop_event = threading.Event()

        thread = threading.Thread(target=monitor_steam_games, args=(stop_event, killed_notification, killed_resource), daemon=True)
        thread.start()

        update_thread = threading.Thread(target=check_for_updates, daemon=True)
        update_thread.start()

        # Hide console window
        ctypes.windll.kernel32.GetConsoleWindow.restype = ctypes.c_void_p
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd != 0:
            ctypes.windll.user32.ShowWindow(hwnd, 0)

        menu = pystray.Menu(
            item('Settings', open_settings),
            item('Quit', quit_app)
        )

        icon_image = Image.open(TRAY_ICON_PATH) if os.path.exists(TRAY_ICON_PATH) else None
        icon = pystray.Icon("Vapor", icon_image, "Vapor - Streamline Gaming", menu)
        icon.run()

        thread.join()
        print("Vapor has stopped.")