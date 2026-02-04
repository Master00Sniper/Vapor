# ui/state.py
# Shared state for the Vapor Settings UI.
# Contains settings values, UI variables, and dirty tracking.

import os
import sys
import tkinter as tk

# Will be set by app.py after window creation
root = None
tabview = None
main_pid = None

# Settings loaded at startup (populated by app.py)
current_settings = {}

# Individual setting values (populated from current_settings by app.py)
selected_notification_apps = []
custom_processes = []
selected_resource_apps = []
custom_resource_processes = []
launch_at_startup = False
launch_settings_on_start = True
close_on_startup = True
close_on_hotkey = False
relaunch_on_exit = True
resource_close_on_startup = True
resource_close_on_hotkey = False
resource_relaunch_on_exit = True
enable_playtime_summary = True
playtime_summary_mode = 'brief'
enable_debug_mode = False
enable_telemetry = True
system_audio_level = 50
enable_system_audio = False
game_audio_level = 50
enable_game_audio = False
enable_during_power = False
during_power_plan = 'High Performance'
enable_after_power = False
after_power_plan = 'Balanced'
enable_game_mode_start = False
enable_game_mode_end = False
enable_cpu_thermal = False
enable_gpu_thermal = True
enable_cpu_temp_alert = False
cpu_temp_warning_threshold = 85
cpu_temp_critical_threshold = 95
enable_gpu_temp_alert = False
gpu_temp_warning_threshold = 80
gpu_temp_critical_threshold = 90

# UI state tracking - maps app names to their BooleanVar
switch_vars = {}
resource_switch_vars = {}

# Unsaved changes tracking
_is_dirty = False
_original_title = "Vapor Settings"

# UI widget references that need to be accessed across modules
# These are set by the modules that create them
save_button = None
custom_entry = None
custom_resource_entry = None

# Notification tab variables (set by notifications tab)
close_startup_var = None
close_hotkey_var = None
relaunch_exit_var = None

# Resource tab variables (set by resources tab)
resource_close_startup_var = None
resource_close_hotkey_var = None
resource_relaunch_exit_var = None

# Preferences tab variables (set by preferences tab)
startup_var = None
launch_settings_on_start_var = None
debug_mode_var = None
enable_telemetry_var = None
playtime_summary_var = None
playtime_summary_mode_var = None
system_audio_slider_var = None
enable_system_audio_var = None
game_audio_slider_var = None
enable_game_audio_var = None
enable_during_power_var = None
during_power_var = None
enable_after_power_var = None
after_power_var = None
enable_game_mode_start_var = None
enable_game_mode_end_var = None

# Thermal tab variables (set by thermal tab)
enable_cpu_thermal_var = None
enable_gpu_thermal_var = None
enable_cpu_temp_alert_var = None
cpu_temp_warning_threshold_var = None
cpu_temp_critical_threshold_var = None
enable_gpu_temp_alert_var = None
gpu_temp_warning_threshold_var = None
gpu_temp_critical_threshold_var = None

# Hidden toggles for Konami code easter egg
debug_mode_switch = None
telemetry_frame = None
telemetry_switch = None
telemetry_hint = None
startup_switch = None  # Reference for placing debug switch after it

# Konami code state
_konami_sequence = ['Up', 'Up', 'Down', 'Down', 'Left', 'Right', 'Left', 'Right']
_konami_index = [0]
_easter_egg_revealed = [False]

# Save button pulse animation state
_pulse_animation_id = None
_pulse_direction = 1
_pulse_intensity = 0


def mark_dirty(*args):
    """Mark that unsaved changes exist."""
    global _is_dirty
    if not _is_dirty:
        _is_dirty = True
        if root:
            root.title(f"{_original_title} - Unsaved Changes")
        # Start save button pulse animation
        from ui.state import start_save_button_pulse
        start_save_button_pulse()


def mark_clean():
    """Mark that all changes have been saved."""
    global _is_dirty
    _is_dirty = False
    if root:
        root.title(_original_title)
    stop_save_button_pulse()


def is_dirty():
    """Check if there are unsaved changes."""
    return _is_dirty


def start_save_button_pulse():
    """Start the gold pulse animation on the save button border."""
    global _pulse_animation_id, _pulse_direction, _pulse_intensity
    if save_button is None:
        return

    def pulse():
        global _pulse_animation_id, _pulse_direction, _pulse_intensity
        if not _is_dirty:
            return

        _pulse_intensity += _pulse_direction * 0.05
        if _pulse_intensity >= 1:
            _pulse_intensity = 1
            _pulse_direction = -1
        elif _pulse_intensity <= 0:
            _pulse_intensity = 0
            _pulse_direction = 1

        # Interpolate border color from transparent to gold (#d4a017)
        # Use intensity to control alpha-like effect by blending with background
        r = int(0x2d + (0xd4 - 0x2d) * _pulse_intensity)
        g = int(0x8a + (0xa0 - 0x8a) * _pulse_intensity)
        b = int(0x4e + (0x17 - 0x4e) * _pulse_intensity)
        border_color = f'#{r:02x}{g:02x}{b:02x}'

        try:
            save_button.configure(border_color=border_color, border_width=3)
        except Exception:
            pass

        _pulse_animation_id = root.after(50, pulse)

    if _pulse_animation_id is None:
        _pulse_direction = 1
        _pulse_intensity = 0
        pulse()


def stop_save_button_pulse():
    """Stop the save button pulse animation and reset border."""
    global _pulse_animation_id
    if _pulse_animation_id is not None:
        if root:
            root.after_cancel(_pulse_animation_id)
        _pulse_animation_id = None
    if save_button:
        try:
            save_button.configure(border_width=0)
        except Exception:
            pass


def load_settings_into_state(settings_dict):
    """Load settings dictionary into module state variables."""
    global current_settings, selected_notification_apps, custom_processes
    global selected_resource_apps, custom_resource_processes
    global launch_at_startup, launch_settings_on_start, close_on_startup
    global close_on_hotkey, relaunch_on_exit, resource_close_on_startup
    global resource_close_on_hotkey, resource_relaunch_on_exit
    global enable_playtime_summary, playtime_summary_mode, enable_debug_mode
    global enable_telemetry, system_audio_level, enable_system_audio
    global game_audio_level, enable_game_audio, enable_during_power
    global during_power_plan, enable_after_power, after_power_plan
    global enable_game_mode_start, enable_game_mode_end
    global enable_cpu_thermal, enable_gpu_thermal
    global enable_cpu_temp_alert, cpu_temp_warning_threshold, cpu_temp_critical_threshold
    global enable_gpu_temp_alert, gpu_temp_warning_threshold, gpu_temp_critical_threshold

    current_settings = settings_dict

    selected_notification_apps = settings_dict.get('selected_notification_apps',
                                                    settings_dict.get('selected_apps', []))
    custom_processes = settings_dict.get('custom_processes', [])
    selected_resource_apps = settings_dict.get('selected_resource_apps', [])
    custom_resource_processes = settings_dict.get('custom_resource_processes', [])
    launch_at_startup = settings_dict.get('launch_at_startup', False)
    launch_settings_on_start = settings_dict.get('launch_settings_on_start', True)
    close_on_startup = settings_dict.get('close_on_startup', True)
    close_on_hotkey = settings_dict.get('close_on_hotkey', False)
    relaunch_on_exit = settings_dict.get('relaunch_on_exit', True)
    resource_close_on_startup = settings_dict.get('resource_close_on_startup', True)
    resource_close_on_hotkey = settings_dict.get('resource_close_on_hotkey', False)
    resource_relaunch_on_exit = settings_dict.get('resource_relaunch_on_exit', True)
    enable_playtime_summary = settings_dict.get('enable_playtime_summary', True)
    playtime_summary_mode = settings_dict.get('playtime_summary_mode', 'brief')
    enable_debug_mode = settings_dict.get('enable_debug_mode', False)
    enable_telemetry = settings_dict.get('enable_telemetry', True)
    system_audio_level = settings_dict.get('system_audio_level', 50)
    enable_system_audio = settings_dict.get('enable_system_audio', False)
    game_audio_level = settings_dict.get('game_audio_level', 50)
    enable_game_audio = settings_dict.get('enable_game_audio', False)
    enable_during_power = settings_dict.get('enable_during_power', False)
    during_power_plan = settings_dict.get('during_power_plan', 'High Performance')
    enable_after_power = settings_dict.get('enable_after_power', False)
    after_power_plan = settings_dict.get('after_power_plan', 'Balanced')
    enable_game_mode_start = settings_dict.get('enable_game_mode_start', False)
    enable_game_mode_end = settings_dict.get('enable_game_mode_end', False)
    enable_cpu_thermal = settings_dict.get('enable_cpu_thermal', False)
    enable_gpu_thermal = settings_dict.get('enable_gpu_thermal', True)
    enable_cpu_temp_alert = settings_dict.get('enable_cpu_temp_alert', False)
    cpu_temp_warning_threshold = settings_dict.get('cpu_temp_warning_threshold', 85)
    cpu_temp_critical_threshold = settings_dict.get('cpu_temp_critical_threshold', 95)
    enable_gpu_temp_alert = settings_dict.get('enable_gpu_temp_alert', False)
    gpu_temp_warning_threshold = settings_dict.get('gpu_temp_warning_threshold', 80)
    gpu_temp_critical_threshold = settings_dict.get('gpu_temp_critical_threshold', 90)
