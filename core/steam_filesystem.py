# core/steam_filesystem.py
# Steam library discovery and game file location

import os
import re
import winreg

from utils import log


# Default Steam path (used as fallback)
DEFAULT_STEAM_PATH = r"C:\Program Files (x86)\Steam\steamapps"


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
        return DEFAULT_STEAM_PATH


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
