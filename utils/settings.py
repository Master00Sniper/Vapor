# utils/settings.py
# Shared settings management for Vapor application

import os
import json
from utils.constants import SETTINGS_FILE
from utils.logging import log

# =============================================================================
# Default Settings
# =============================================================================

DEFAULT_SETTINGS = {
    # Notification apps
    'notification_processes': [
        'WhatsApp.Root.exe', 'Telegram.exe', 'ms-teams.exe',
        'Messenger.exe', 'slack.exe', 'Signal.exe', 'WeChat.exe'
    ],
    'selected_notification_apps': [
        'WhatsApp', 'Telegram', 'Microsoft Teams', 'Facebook Messenger',
        'Slack', 'Signal', 'WeChat'
    ],
    'custom_processes': [],

    # Resource apps
    'resource_processes': [
        'spotify.exe', 'OneDrive.exe', 'GoogleDriveFS.exe',
        'Dropbox.exe', 'wallpaper64.exe'
    ],
    'selected_resource_apps': [
        'Spotify', 'OneDrive', 'Google Drive', 'Dropbox',
        'Wallpaper Engine', 'iCUE', 'Razer Synapse', 'NZXT CAM'
    ],
    'custom_resource_processes': [],

    # Startup behavior
    'launch_at_startup': False,
    'launch_settings_on_start': True,

    # Notification app behavior
    'close_on_startup': True,
    'close_on_hotkey': True,
    'relaunch_on_exit': True,

    # Resource app behavior
    'resource_close_on_startup': True,
    'resource_close_on_hotkey': True,
    'resource_relaunch_on_exit': False,

    # Playtime summary
    'enable_playtime_summary': True,
    'playtime_summary_mode': 'detailed',

    # Debug
    'enable_debug_mode': False,

    # Audio settings
    'system_audio_level': 33,
    'enable_system_audio': False,
    'game_audio_level': 100,
    'enable_game_audio': False,

    # Power management
    'enable_during_power': False,
    'during_power_plan': 'High Performance',
    'enable_after_power': False,
    'after_power_plan': 'Balanced',

    # Game mode
    'enable_game_mode_start': True,
    'enable_game_mode_end': False,

    # Temperature monitoring
    'enable_cpu_thermal': False,
    'enable_gpu_thermal': True,

    # Temperature alerts
    'enable_cpu_temp_alert': False,
    'cpu_temp_warning_threshold': 85,
    'cpu_temp_critical_threshold': 95,
    'enable_gpu_temp_alert': False,
    'gpu_temp_warning_threshold': 80,
    'gpu_temp_critical_threshold': 90,

    # Telemetry
    'enable_telemetry': True,
}


# =============================================================================
# Settings Functions
# =============================================================================

def load_settings():
    """
    Load settings from file or return defaults.

    Returns:
        dict: Settings dictionary with all configuration values
    """
    if os.path.exists(SETTINGS_FILE):
        log(f"Loading settings from {SETTINGS_FILE}", "SETTINGS")
        try:
            with open(SETTINGS_FILE, 'r') as f:
                saved_settings = json.load(f)

            # Merge with defaults to ensure all keys exist
            settings = DEFAULT_SETTINGS.copy()
            settings.update(saved_settings)
            log("Settings loaded successfully", "SETTINGS")
            return settings
        except (json.JSONDecodeError, IOError) as e:
            log(f"Error loading settings: {e}, using defaults", "SETTINGS")
            return DEFAULT_SETTINGS.copy()
    else:
        log("Settings file not found, using defaults", "SETTINGS")
        return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    """
    Save settings dictionary to file.

    Args:
        settings: Dictionary containing all settings
    """
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        log(f"Settings saved to {SETTINGS_FILE}", "SETTINGS")
    except IOError as e:
        log(f"Error saving settings: {e}", "ERROR")


def create_default_settings():
    """Create default settings file if it doesn't exist."""
    if not os.path.exists(SETTINGS_FILE):
        log("Creating default settings file...", "SETTINGS")
        save_settings(DEFAULT_SETTINGS)
        log("Default settings file created", "SETTINGS")
        return True
    return False


def get_setting(key, default=None):
    """
    Get a single setting value.

    Args:
        key: Setting key to retrieve
        default: Default value if key not found

    Returns:
        The setting value or default
    """
    settings = load_settings()
    return settings.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))


def set_setting(key, value):
    """
    Set a single setting value.

    Args:
        key: Setting key to update
        value: New value for the setting
    """
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
