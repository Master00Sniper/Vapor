# ui/app.py
# Main application orchestrator for Vapor Settings UI.
# Sets up window, loads settings, builds tabs, handles save/close.

import os
import sys
import ctypes
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import psutil

from utils import (
    base_dir, appdata_dir, SETTINGS_FILE, PROTECTED_PROCESSES, log as debug_log,
    load_settings as load_settings_dict, save_settings as save_settings_dict, set_setting,
    GAME_STARTED_SIGNAL_FILE
)
from platform_utils import (
    is_admin, is_pawnio_installed, clear_pawnio_cache, install_pawnio_with_elevation
)

import ui.state as state
from ui.constants import (
    TAB_NOTIFICATIONS, TAB_RESOURCES, TAB_THERMAL,
    TAB_PREFERENCES, TAB_HELP, TAB_ABOUT,
    BUILT_IN_APPS, BUILT_IN_RESOURCE_APPS,
    add_button_press_effect
)
from ui.dialogs import show_vapor_dialog, set_vapor_icon
from ui.restart import restart_vapor
from ui.tabs import (
    build_notifications_tab, build_resources_tab, build_thermal_tab,
    build_preferences_tab, build_help_tab, build_about_tab
)

try:
    from updater import CURRENT_VERSION
except ImportError:
    CURRENT_VERSION = "Unknown"


def save_settings_to_file(selected_notification_apps, customs, selected_resource_apps, resource_customs,
                          launch_startup, launch_settings_on_start, close_on_startup, close_on_hotkey,
                          relaunch_on_exit, resource_close_on_startup, resource_close_on_hotkey,
                          resource_relaunch_on_exit, enable_playtime_summary, playtime_summary_mode,
                          enable_debug_mode, enable_telemetry, system_audio_level, enable_system_audio,
                          game_audio_level, enable_game_audio, enable_during_power, during_power_plan,
                          enable_after_power, after_power_plan, enable_game_mode_start, enable_game_mode_end,
                          enable_cpu_thermal, enable_gpu_thermal, enable_cpu_temp_alert,
                          cpu_temp_warning_threshold, cpu_temp_critical_threshold, enable_gpu_temp_alert,
                          gpu_temp_warning_threshold, gpu_temp_critical_threshold):
    """Save all settings to the JSON configuration file."""
    # Build process lists from selected apps
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
        'playtime_summary_mode': playtime_summary_mode,
        'enable_debug_mode': enable_debug_mode,
        'enable_telemetry': enable_telemetry,
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
    """Set or clear the pending PawnIO check flag in settings."""
    debug_log(f"Setting pending_pawnio_check to {value}", "Settings")
    set_setting('pending_pawnio_check', value)


def set_pending_settings_reopen(value=True):
    """Set or clear the pending settings reopen flag."""
    debug_log(f"Setting pending_settings_reopen to {value}", "Settings")
    set_setting('pending_settings_reopen', value)


def on_save():
    """Save current settings to file. Returns True if saved successfully, False if cancelled."""
    debug_log("Save button clicked", "Settings")

    # Collect values from UI state
    new_selected_notification_apps = [name for name, var in state.switch_vars.items() if var.get()]
    raw_customs = [c.strip() for c in state.custom_entry.get().split(',') if c.strip()]
    new_selected_resource_apps = [name for name, var in state.resource_switch_vars.items() if var.get()]
    raw_resource_customs = [c.strip() for c in state.custom_resource_entry.get().split(',') if c.strip()]

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
        state.custom_entry.delete(0, 'end')
        state.custom_entry.insert(0, ', '.join(new_customs))
        state.custom_resource_entry.delete(0, 'end')
        state.custom_resource_entry.insert(0, ', '.join(new_resource_customs))

    # Collect all settings from state variables
    new_launch_startup = state.startup_var.get()
    new_launch_settings_on_start = state.launch_settings_on_start_var.get()
    new_close_on_startup = state.close_startup_var.get() == "Enabled"
    new_close_on_hotkey = state.close_hotkey_var.get() == "Enabled"
    new_relaunch_on_exit = state.relaunch_exit_var.get() == "Enabled"
    new_resource_close_on_startup = state.resource_close_startup_var.get() == "Enabled"
    new_resource_close_on_hotkey = state.resource_close_hotkey_var.get() == "Enabled"
    new_resource_relaunch_on_exit = state.resource_relaunch_exit_var.get() == "Enabled"
    new_enable_playtime_summary = state.playtime_summary_var.get()
    new_playtime_summary_mode = state.playtime_summary_mode_var.get()
    new_enable_debug_mode = state.debug_mode_var.get()
    new_enable_telemetry = state.enable_telemetry_var.get()
    new_system_audio_level = state.system_audio_slider_var.get()
    new_enable_system_audio = state.enable_system_audio_var.get()
    new_game_audio_level = state.game_audio_slider_var.get()
    new_enable_game_audio = state.enable_game_audio_var.get()
    new_enable_during_power = state.enable_during_power_var.get()
    new_during_power_plan = state.during_power_var.get()
    new_enable_after_power = state.enable_after_power_var.get()
    new_after_power_plan = state.after_power_var.get()
    new_enable_game_mode_start = state.enable_game_mode_start_var.get()
    new_enable_game_mode_end = state.enable_game_mode_end_var.get()
    new_enable_cpu_thermal = state.enable_cpu_thermal_var.get()
    new_enable_gpu_thermal = state.enable_gpu_thermal_var.get()
    new_enable_cpu_temp_alert = state.enable_cpu_temp_alert_var.get()
    new_enable_gpu_temp_alert = state.enable_gpu_temp_alert_var.get()

    # Parse threshold values
    try:
        new_cpu_temp_warning_threshold = int(state.cpu_temp_warning_threshold_var.get())
    except (ValueError, AttributeError):
        new_cpu_temp_warning_threshold = 85
    try:
        new_cpu_temp_critical_threshold = int(state.cpu_temp_critical_threshold_var.get())
    except (ValueError, AttributeError):
        new_cpu_temp_critical_threshold = 95
    try:
        new_gpu_temp_warning_threshold = int(state.gpu_temp_warning_threshold_var.get())
    except (ValueError, AttributeError):
        new_gpu_temp_warning_threshold = 80
    try:
        new_gpu_temp_critical_threshold = int(state.gpu_temp_critical_threshold_var.get())
    except (ValueError, AttributeError):
        new_gpu_temp_critical_threshold = 90

    # Save settings
    save_settings_to_file(
        new_selected_notification_apps, new_customs, new_selected_resource_apps, new_resource_customs,
        new_launch_startup, new_launch_settings_on_start, new_close_on_startup, new_close_on_hotkey,
        new_relaunch_on_exit, new_resource_close_on_startup, new_resource_close_on_hotkey,
        new_resource_relaunch_on_exit, new_enable_playtime_summary, new_playtime_summary_mode,
        new_enable_debug_mode, new_enable_telemetry, new_system_audio_level, new_enable_system_audio,
        new_game_audio_level, new_enable_game_audio, new_enable_during_power, new_during_power_plan,
        new_enable_after_power, new_after_power_plan, new_enable_game_mode_start, new_enable_game_mode_end,
        new_enable_cpu_thermal, new_enable_gpu_thermal, new_enable_cpu_temp_alert,
        new_cpu_temp_warning_threshold, new_cpu_temp_critical_threshold, new_enable_gpu_temp_alert,
        new_gpu_temp_warning_threshold, new_gpu_temp_critical_threshold
    )

    state.mark_clean()

    # Check if CPU thermal is enabled and Vapor needs to restart with admin privileges
    if new_enable_cpu_thermal and not is_admin():
        response = show_vapor_dialog(
            title="Admin Privileges Required",
            message="CPU temperature monitoring requires administrator privileges.\n\n"
                    "Would you like to restart Vapor with admin privileges now?\n\n"
                    "If you click 'Restart as Admin', Vapor will close and relaunch\n"
                    "with elevated permissions to enable CPU temperature monitoring.\n\n"
                    "Note: Vapor will continue to request admin privileges at startup\n"
                    "while Capture CPU Temperature is enabled.",
            dialog_type="warning",
            buttons=[
                {"text": "Restart as Admin", "value": True, "color": "green"},
                {"text": "Cancel", "value": False, "color": "gray"}
            ],
            parent=state.root
        )
        if response is True:
            set_pending_pawnio_check(True)
            set_pending_settings_reopen(True)
            if restart_vapor(state.main_pid, require_admin=True):
                state.root.destroy()
                return True
            else:
                set_pending_pawnio_check(False)
                set_pending_settings_reopen(False)
                show_vapor_dialog(
                    title="Elevation Failed",
                    message="Failed to restart Vapor with admin privileges.\n\n"
                            "Please try running Vapor as administrator manually by\n"
                            "right-clicking the Vapor shortcut and selecting\n"
                            "'Run as administrator'.",
                    dialog_type="error",
                    parent=state.root
                )
                state.enable_cpu_thermal_var.set(False)
                return False
        else:
            state.enable_cpu_thermal_var.set(False)
            return False

    # Check if CPU thermal is being NEWLY enabled and PawnIO driver needs to be installed
    if new_enable_cpu_thermal and not state.enable_cpu_thermal and not is_pawnio_installed():
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
            parent=state.root
        )
        if response == "install":
            # Show installing message with progress bar
            installing_dialog = ctk.CTkToplevel(state.root)
            installing_dialog.title("Vapor - Installing Driver")
            installing_dialog.geometry("400x160")
            installing_dialog.resizable(False, False)
            installing_dialog.transient(state.root)

            installing_dialog.update_idletasks()
            x = state.root.winfo_x() + (state.root.winfo_width() - 400) // 2
            y = state.root.winfo_y() + (state.root.winfo_height() - 160) // 2
            installing_dialog.geometry(f"+{x}+{y}")

            msg_label = ctk.CTkLabel(installing_dialog, text="Installing PawnIO driver...",
                                     font=("Calibri", 13), justify="center")
            msg_label.pack(padx=20, pady=(25, 10))

            progress_bar = ctk.CTkProgressBar(installing_dialog, width=300)
            progress_bar.pack(padx=20, pady=10)
            progress_bar.set(0)

            status_label = ctk.CTkLabel(installing_dialog, text="Please wait while the driver is installed...",
                                        font=("Calibri", 11), text_color="gray")
            status_label.pack(padx=20, pady=(5, 15))

            installing_dialog.update()
            set_vapor_icon(installing_dialog)
            installing_dialog.lift()
            installing_dialog.attributes('-topmost', True)
            installing_dialog.after(100, lambda: installing_dialog.attributes('-topmost', False))
            installing_dialog.focus_force()

            def update_progress(message, pct):
                try:
                    if installing_dialog.winfo_exists():
                        msg_label.configure(text=message)
                        progress_bar.set(pct / 100)
                        installing_dialog.update()
                except Exception:
                    pass

            install_success = install_pawnio_with_elevation(progress_callback=update_progress)
            clear_pawnio_cache()

            try:
                installing_dialog.destroy()
            except Exception:
                pass

            if install_success:
                try:
                    from core import temperature
                    temperature.HWMON_COMPUTER = None
                    temperature.LHM_COMPUTER = None
                    debug_log("Reset temperature monitor globals after driver install", "Settings")

                    test_temp = temperature.get_cpu_temperature()
                    if test_temp is not None:
                        debug_log(f"CPU temperature read successful: {test_temp}°C", "Settings")
                        state.enable_cpu_thermal_var.set(True)
                        show_vapor_dialog(
                            title="Driver Installed",
                            message=f"PawnIO driver installed successfully!\n\n"
                                    f"CPU temperature monitoring is now active.\n"
                                    f"Current CPU temperature: {test_temp}°C",
                            dialog_type="info",
                            buttons=[{"text": "OK", "value": True, "color": "green"}],
                            parent=state.root
                        )
                        return True
                    else:
                        debug_log("CPU temperature read returned None after driver install", "Settings")
                except Exception as e:
                    debug_log(f"Error testing temperature after driver install: {e}", "Settings")

                show_vapor_dialog(
                    title="Driver Installed - Please Restart",
                    message="PawnIO driver installed successfully!\n\n"
                            "Please close and restart Vapor manually to enable\n"
                            "CPU temperature monitoring.\n\n"
                            "Vapor will now close.",
                    dialog_type="info",
                    buttons=[{"text": "Close Vapor", "value": True, "color": "green"}],
                    parent=state.root
                )
                if state.main_pid:
                    try:
                        psutil.Process(state.main_pid).terminate()
                    except Exception:
                        pass
                state.root.destroy()
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
                    parent=state.root
                )
                state.enable_cpu_thermal_var.set(False)
        else:
            state.enable_cpu_thermal_var.set(False)

    # Check if debug mode changed and needs restart
    if new_enable_debug_mode != state.enable_debug_mode:
        debug_log(f"Debug mode changed from {state.enable_debug_mode} to {new_enable_debug_mode}", "Settings")
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
            parent=state.root
        )
        if response:
            restart_vapor(state.main_pid, require_admin=False)
            state.root.destroy()
            return True

    return True


def on_save_and_close():
    """Save settings and close the window."""
    debug_log("Save & Close clicked", "Settings")
    if on_save():
        state.root.destroy()


def on_discard_and_close():
    """Close without saving changes."""
    debug_log("Discard & Close clicked", "Settings")
    state.root.destroy()


def on_stop_vapor():
    """Terminate the main Vapor process and close settings."""
    debug_log("Stop Vapor clicked", "Settings")
    if state.main_pid:
        try:
            debug_log(f"Terminating main Vapor process (PID: {state.main_pid})", "Settings")
            main_process = psutil.Process(state.main_pid)
            main_process.terminate()
            debug_log("Main process terminated", "Settings")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            debug_log(f"Could not terminate: {e}", "Settings")
    state.root.destroy()


def check_main_process():
    """Auto-close settings if main Vapor process exits."""
    if state.main_pid:
        try:
            main_process = psutil.Process(state.main_pid)
            if not main_process.is_running():
                state.root.destroy()
                return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            state.root.destroy()
            return
    state.root.after(1000, check_main_process)


def check_game_started_signal():
    """Check if a game has started and auto-save/close settings if so."""
    try:
        if os.path.exists(GAME_STARTED_SIGNAL_FILE):
            debug_log("Game started signal detected - auto-saving and closing settings", "Settings")
            # Remove the signal file
            try:
                os.remove(GAME_STARTED_SIGNAL_FILE)
            except Exception:
                pass
            # Save and close
            on_save_and_close()
            return
    except Exception as e:
        debug_log(f"Error checking game started signal: {e}", "Settings")

    # Check again in 1 second
    state.root.after(1000, check_game_started_signal)


def check_pending_pawnio_install():
    """Check if PawnIO installation was pending after admin restart."""
    debug_log("Checking for pending PawnIO installation...", "Startup")

    pending_check = state.current_settings.get('pending_pawnio_check', False)
    if not pending_check:
        debug_log("No pending PawnIO check", "Startup")
        return

    set_pending_pawnio_check(False)
    debug_log("Cleared pending_pawnio_check flag", "Startup")

    if not is_admin():
        debug_log("Not running as admin, skipping PawnIO check", "Startup")
        return

    if is_pawnio_installed(use_cache=False):
        debug_log("PawnIO is already installed", "Startup")
        return

    debug_log("PawnIO not installed, showing installation prompt", "Startup")

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
        parent=state.root
    )

    if response == "install":
        installing_dialog = ctk.CTkToplevel(state.root)
        installing_dialog.title("Vapor - Installing Driver")
        installing_dialog.geometry("400x160")
        installing_dialog.resizable(False, False)
        installing_dialog.transient(state.root)

        installing_dialog.update_idletasks()
        x = state.root.winfo_x() + (state.root.winfo_width() - 400) // 2
        y = state.root.winfo_y() + (state.root.winfo_height() - 160) // 2
        installing_dialog.geometry(f"+{x}+{y}")

        msg_label = ctk.CTkLabel(installing_dialog, text="Installing PawnIO driver...",
                                 font=("Calibri", 13), justify="center")
        msg_label.pack(padx=20, pady=(25, 10))

        progress_bar = ctk.CTkProgressBar(installing_dialog, width=300)
        progress_bar.pack(padx=20, pady=10)
        progress_bar.set(0)

        status_label = ctk.CTkLabel(installing_dialog, text="Please wait while the driver is installed...",
                                    font=("Calibri", 11), text_color="gray")
        status_label.pack(padx=20, pady=(5, 15))

        installing_dialog.update()
        set_vapor_icon(installing_dialog)
        installing_dialog.lift()
        installing_dialog.attributes('-topmost', True)
        installing_dialog.after(100, lambda: installing_dialog.attributes('-topmost', False))
        installing_dialog.focus_force()

        def update_progress(message, pct):
            try:
                if installing_dialog.winfo_exists():
                    msg_label.configure(text=message)
                    progress_bar.set(pct / 100)
                    installing_dialog.update()
            except Exception:
                pass

        install_success = install_pawnio_with_elevation(progress_callback=update_progress)
        clear_pawnio_cache()

        try:
            installing_dialog.destroy()
        except Exception:
            pass

        if install_success:
            try:
                from core import temperature
                temperature.HWMON_COMPUTER = None
                temperature.LHM_COMPUTER = None
                debug_log("Reset temperature monitor globals after driver install", "Settings")

                test_temp = temperature.get_cpu_temperature()
                if test_temp is not None:
                    debug_log(f"CPU temperature read successful: {test_temp}°C", "Settings")
                    state.enable_cpu_thermal_var.set(True)
                    show_vapor_dialog(
                        title="Driver Installed",
                        message=f"PawnIO driver installed successfully!\n\n"
                                f"CPU temperature monitoring is now active.\n"
                                f"Current CPU temperature: {test_temp}°C",
                        dialog_type="info",
                        buttons=[{"text": "OK", "value": True, "color": "green"}],
                        parent=state.root
                    )
                    return
                else:
                    debug_log("CPU temperature read returned None after driver install", "Settings")
            except Exception as e:
                debug_log(f"Error testing temperature after driver install: {e}", "Settings")

            show_vapor_dialog(
                title="Driver Installed - Please Restart",
                message="PawnIO driver installed successfully!\n\n"
                        "Please close and restart Vapor manually to enable\n"
                        "CPU temperature monitoring.\n\n"
                        "Vapor will now close.",
                dialog_type="info",
                buttons=[{"text": "Close Vapor", "value": True, "color": "green"}],
                parent=state.root
            )
            if state.main_pid:
                try:
                    psutil.Process(state.main_pid).terminate()
                except Exception:
                    pass
            state.root.destroy()
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
                parent=state.root
            )
            state.enable_cpu_thermal_var.set(False)
    else:
        debug_log("User cancelled PawnIO installation", "Startup")
        state.enable_cpu_thermal_var.set(False)


def run_settings_ui():
    """Main entry point for the Settings UI."""
    # Create main window
    state.root = ctk.CTk()
    state.root.withdraw()  # Hide while setting up
    state.root.title("Vapor Settings")

    # Get screen dimensions and calculate window size
    screen_width = state.root.winfo_screenwidth()
    screen_height = state.root.winfo_screenheight()

    window_width = 700
    window_height = int(screen_height * 0.85)
    window_height = max(600, min(window_height, 1000))

    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2

    state.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    state.root.resizable(False, False)

    # Set window icon
    icon_path = os.path.join(base_dir, 'Images', 'exe_icon.ico')
    if os.path.exists(icon_path):
        try:
            state.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"Error setting icon: {e}")

    state.root.deiconify()
    state.root.update()

    state.root.lift()
    state.root.attributes('-topmost', True)
    state.root.after(100, lambda: state.root.attributes('-topmost', False))
    state.root.focus_force()

    # Load settings
    settings_dict = load_settings_dict()
    state.load_settings_into_state(settings_dict)

    # Get main process PID
    if os.environ.get('VAPOR_MAIN_PID'):
        try:
            state.main_pid = int(os.environ.get('VAPOR_MAIN_PID'))
        except ValueError:
            pass
    elif len(sys.argv) > 1:
        if sys.argv[1] == '--ui':
            if len(sys.argv) > 2:
                try:
                    state.main_pid = int(sys.argv[2])
                except ValueError:
                    pass
        else:
            try:
                state.main_pid = int(sys.argv[1])
            except ValueError:
                pass

    # Debug console attachment if enabled
    if state.enable_debug_mode:
        try:
            kernel32 = ctypes.windll.kernel32
            ATTACH_PARENT_PROCESS = -1
            attached = kernel32.AttachConsole(ATTACH_PARENT_PROCESS)
            if attached:
                sys.stdout = open('CONOUT$', 'w')
                sys.stderr = open('CONOUT$', 'w')
                debug_log("Settings UI attached to main debug console", "Startup")
            debug_log(f"Settings UI started (main_pid: {state.main_pid})", "Startup")
            debug_log(f"Running as admin: {is_admin()}", "Startup")
        except Exception:
            pass

    # Create tab view
    state.tabview = ctk.CTkTabview(master=state.root)
    state.tabview.pack(pady=10, padx=10, fill="both", expand=True)

    notifications_tab = state.tabview.add(TAB_NOTIFICATIONS)
    resources_tab = state.tabview.add(TAB_RESOURCES)
    thermal_tab = state.tabview.add(TAB_THERMAL)
    preferences_tab = state.tabview.add(TAB_PREFERENCES)
    help_tab = state.tabview.add(TAB_HELP)
    about_tab = state.tabview.add(TAB_ABOUT)

    # Build all tabs
    build_notifications_tab(notifications_tab)
    build_resources_tab(resources_tab)
    build_thermal_tab(thermal_tab)
    build_preferences_tab(preferences_tab)
    build_help_tab(help_tab)
    build_about_tab(about_tab)

    # Bottom button bar
    bottom_separator = ctk.CTkFrame(master=state.root, height=2, fg_color="gray50")
    bottom_separator.pack(fill="x", padx=40, pady=(10, 0))

    button_frame = ctk.CTkFrame(master=state.root, fg_color="transparent")
    button_frame.pack(pady=15, fill='x', padx=40)

    # Configure grid columns
    button_frame.grid_columnconfigure(0, weight=1)
    button_frame.grid_columnconfigure(4, weight=1)

    state.save_button = ctk.CTkButton(
        master=button_frame, text="Save & Close", command=on_save_and_close,
        corner_radius=10, fg_color="#28a745", hover_color="#218838",
        text_color="white", width=150, font=("Calibri", 15)
    )
    state.save_button.grid(row=0, column=1, padx=15, sticky='ew')

    def on_save_button_enter(event):
        if not state.is_dirty():
            state.save_button.configure(fg_color="#2d8a4e")

    def on_save_button_leave(event):
        if not state.is_dirty():
            state.save_button.configure(fg_color="#28a745")

    state.save_button.bind("<Enter>", on_save_button_enter)
    state.save_button.bind("<Leave>", on_save_button_leave)

    discard_button = ctk.CTkButton(
        master=button_frame, text="Discard & Close", command=on_discard_and_close,
        corner_radius=10, fg_color="#6c757d", hover_color="#5a6268",
        text_color="white", width=150, font=("Calibri", 15)
    )
    discard_button.grid(row=0, column=2, padx=15, sticky='ew')

    stop_button = ctk.CTkButton(
        master=button_frame, text="Stop Vapor", command=on_stop_vapor,
        corner_radius=10, fg_color="#e67e22", hover_color="#d35400",
        text_color="white", width=150, font=("Calibri", 15)
    )
    stop_button.grid(row=0, column=3, padx=15, sticky='ew')

    # Add button press effect to main buttons
    add_button_press_effect(state.save_button)
    add_button_press_effect(discard_button)
    add_button_press_effect(stop_button)

    # Make X button work like Discard & Close
    state.root.protocol("WM_DELETE_WINDOW", on_discard_and_close)

    # Start main process monitoring
    if state.main_pid:
        state.root.after(1000, check_main_process)

    # Start game started signal monitoring (auto-save/close when game starts)
    state.root.after(1000, check_game_started_signal)

    # Check for pending PawnIO installation
    state.root.after(500, check_pending_pawnio_install)

    # Start the UI
    state.root.mainloop()
