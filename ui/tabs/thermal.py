# ui/tabs/thermal.py
# Thermal tab for the Vapor Settings UI.

import tkinter as tk
import customtkinter as ctk

import ui.state as state
from platform_utils import is_admin

# Try to import temperature functions
try:
    from core.temperature import get_gpu_temperature, get_cpu_temperature
    TEMP_FUNCTIONS_AVAILABLE = True
except ImportError:
    TEMP_FUNCTIONS_AVAILABLE = False

# Module-level references for temperature display update
_temp_update_job = None
_gpu_temp_label = None
_cpu_temp_label = None
_gpu_temp_status = None
_cpu_temp_status = None

# Temperature color thresholds
TEMP_COLOR_GREEN = "#2ecc71"   # Under 65°C
TEMP_COLOR_YELLOW = "#f1c40f"  # 66-80°C
TEMP_COLOR_RED = "#e74c3c"     # 81°C and above


def _get_temp_color(temp):
    """Get the color for a temperature value based on thresholds."""
    if temp <= 65:
        return TEMP_COLOR_GREEN
    elif temp <= 80:
        return TEMP_COLOR_YELLOW
    else:
        return TEMP_COLOR_RED


def _update_temperature_display():
    """Update the live temperature display every 10 seconds."""
    global _temp_update_job, _gpu_temp_label, _cpu_temp_label
    global _gpu_temp_status, _cpu_temp_status

    if not TEMP_FUNCTIONS_AVAILABLE:
        return

    if state.root is None:
        return

    # Update GPU temperature
    if _gpu_temp_label and _gpu_temp_status:
        if state.enable_gpu_thermal_var and state.enable_gpu_thermal_var.get():
            gpu_temp = get_gpu_temperature()
            if gpu_temp is not None:
                temp_color = _get_temp_color(gpu_temp)
                _gpu_temp_label.configure(text=f"{gpu_temp}°C", text_color=temp_color)
                _gpu_temp_status.configure(text="")
            else:
                _gpu_temp_label.configure(text="--", text_color="gray50")
                _gpu_temp_status.configure(text="(unavailable)")
        else:
            _gpu_temp_label.configure(text="--", text_color="gray50")
            _gpu_temp_status.configure(text="(disabled)")

    # Update CPU temperature
    if _cpu_temp_label and _cpu_temp_status:
        if state.enable_cpu_thermal_var and state.enable_cpu_thermal_var.get():
            if is_admin():
                cpu_temp = get_cpu_temperature()
                if cpu_temp is not None:
                    temp_color = _get_temp_color(cpu_temp)
                    _cpu_temp_label.configure(text=f"{cpu_temp}°C", text_color=temp_color)
                    _cpu_temp_status.configure(text="")
                else:
                    _cpu_temp_label.configure(text="--", text_color="gray50")
                    _cpu_temp_status.configure(text="(unavailable)")
            else:
                _cpu_temp_label.configure(text="--", text_color="gray50")
                _cpu_temp_status.configure(text="(requires admin)")
        else:
            _cpu_temp_label.configure(text="--", text_color="gray50")
            _cpu_temp_status.configure(text="(disabled)")

    # Schedule next update in 10 seconds
    _temp_update_job = state.root.after(10000, _update_temperature_display)


def _stop_temperature_updates():
    """Stop the temperature update loop."""
    global _temp_update_job
    if _temp_update_job and state.root:
        try:
            state.root.after_cancel(_temp_update_job)
        except Exception:
            pass
        _temp_update_job = None


def build_thermal_tab(parent_frame):
    """
    Build the Thermal tab content.

    Args:
        parent_frame: The tab frame to build content in

    Returns:
        dict: References to widgets that need to be accessed elsewhere
    """
    global _gpu_temp_label, _cpu_temp_label, _gpu_temp_status, _cpu_temp_status

    thermal_scroll_frame = ctk.CTkScrollableFrame(master=parent_frame, fg_color="transparent")
    thermal_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

    thermal_main_title = ctk.CTkLabel(master=thermal_scroll_frame, text="Thermal Management", font=("Calibri", 25, "bold"))
    thermal_main_title.pack(pady=(10, 5), anchor='center')

    thermal_main_description = ctk.CTkLabel(master=thermal_scroll_frame,
                                            text="Monitor and track CPU and GPU temperatures during gaming sessions.",
                                            font=("Calibri", 13), text_color="gray60")
    thermal_main_description.pack(pady=(0, 15), anchor='center')

    # ==========================================================================
    # Current Temperatures Section (Live Display)
    # ==========================================================================
    thermal_sep0 = ctk.CTkFrame(master=thermal_scroll_frame, height=2, fg_color="gray50")
    thermal_sep0.pack(fill="x", padx=40, pady=10)

    current_temps_title = ctk.CTkLabel(master=thermal_scroll_frame, text="Current Temperatures",
                                        font=("Calibri", 17, "bold"))
    current_temps_title.pack(pady=(10, 5), anchor='center')

    current_temps_hint = ctk.CTkLabel(master=thermal_scroll_frame,
                                       text="Live readings updated every 10 seconds.",
                                       font=("Calibri", 12), text_color="gray60")
    current_temps_hint.pack(pady=(0, 10), anchor='center')

    # Temperature display frame
    current_temps_frame = ctk.CTkFrame(master=thermal_scroll_frame, fg_color="transparent")
    current_temps_frame.pack(pady=10, anchor='center')

    # GPU Temperature display
    gpu_display_frame = ctk.CTkFrame(master=current_temps_frame, fg_color="transparent")
    gpu_display_frame.pack(side='left', padx=30)

    gpu_icon_label = ctk.CTkLabel(master=gpu_display_frame, text="GPU", font=("Calibri", 14, "bold"))
    gpu_icon_label.pack()

    _gpu_temp_label = ctk.CTkLabel(master=gpu_display_frame, text="--", font=("Calibri", 32, "bold"),
                                    text_color="gray50")
    _gpu_temp_label.pack()

    _gpu_temp_status = ctk.CTkLabel(master=gpu_display_frame, text="(disabled)",
                                     font=("Calibri", 11), text_color="gray50")
    _gpu_temp_status.pack()

    # CPU Temperature display
    cpu_display_frame = ctk.CTkFrame(master=current_temps_frame, fg_color="transparent")
    cpu_display_frame.pack(side='left', padx=30)

    cpu_icon_label = ctk.CTkLabel(master=cpu_display_frame, text="CPU", font=("Calibri", 14, "bold"))
    cpu_icon_label.pack()

    _cpu_temp_label = ctk.CTkLabel(master=cpu_display_frame, text="--", font=("Calibri", 32, "bold"),
                                    text_color="gray50")
    _cpu_temp_label.pack()

    _cpu_temp_status = ctk.CTkLabel(master=cpu_display_frame, text="(disabled)",
                                     font=("Calibri", 11), text_color="gray50")
    _cpu_temp_status.pack()

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

    state.enable_gpu_thermal_var = tk.BooleanVar(value=state.enable_gpu_thermal)
    enable_gpu_thermal_switch = ctk.CTkSwitch(master=thermal_frame, text="Capture GPU Temperature",
                                              variable=state.enable_gpu_thermal_var, font=("Calibri", 14),
                                              command=state.mark_dirty)
    enable_gpu_thermal_switch.pack(pady=5, anchor='w')

    state.enable_cpu_thermal_var = tk.BooleanVar(value=state.enable_cpu_thermal)
    enable_cpu_thermal_switch = ctk.CTkSwitch(master=thermal_frame, text="Capture CPU Temperature",
                                              variable=state.enable_cpu_thermal_var, font=("Calibri", 14),
                                              command=state.mark_dirty)
    enable_cpu_thermal_switch.pack(pady=(5, 0), anchor='w')

    cpu_thermal_note = ctk.CTkLabel(master=thermal_frame, text="(requires admin, will auto-install driver)",
                                    font=("Calibri", 12), text_color="gray60")
    cpu_thermal_note.pack(pady=(0, 5), anchor='w', padx=(67, 0))  # Indent to align with switch text

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
    gpu_alert_header = ctk.CTkLabel(master=thermal_alerts_frame, text="GPU Alerts", font=("Calibri", 15, "bold"))
    gpu_alert_header.pack(pady=(5, 5), anchor='w')

    gpu_alert_row = ctk.CTkFrame(master=thermal_alerts_frame, fg_color="transparent")
    gpu_alert_row.pack(pady=5, fill='x')

    state.enable_gpu_temp_alert_var = tk.BooleanVar(value=state.enable_gpu_temp_alert)
    enable_gpu_temp_alert_switch = ctk.CTkSwitch(master=gpu_alert_row, text="Enable",
                                                  variable=state.enable_gpu_temp_alert_var, font=("Calibri", 14),
                                                  command=state.mark_dirty)
    enable_gpu_temp_alert_switch.pack(side='left', padx=(0, 20))

    gpu_warning_label = ctk.CTkLabel(master=gpu_alert_row, text="Warning:", font=("Calibri", 14))
    gpu_warning_label.pack(side='left', padx=(0, 5))

    state.gpu_temp_warning_threshold_var = tk.StringVar(value=str(state.gpu_temp_warning_threshold))
    gpu_warning_entry = ctk.CTkEntry(master=gpu_alert_row, textvariable=state.gpu_temp_warning_threshold_var,
                                      width=50, font=("Calibri", 14))
    gpu_warning_entry.pack(side='left', padx=(0, 3))
    gpu_warning_entry.bind("<KeyRelease>", state.mark_dirty)

    gpu_warning_unit = ctk.CTkLabel(master=gpu_alert_row, text="°C", font=("Calibri", 14))
    gpu_warning_unit.pack(side='left', padx=(0, 15))

    gpu_critical_label = ctk.CTkLabel(master=gpu_alert_row, text="Critical:", font=("Calibri", 14), text_color="#ff6b6b")
    gpu_critical_label.pack(side='left', padx=(0, 5))

    state.gpu_temp_critical_threshold_var = tk.StringVar(value=str(state.gpu_temp_critical_threshold))
    gpu_critical_entry = ctk.CTkEntry(master=gpu_alert_row, textvariable=state.gpu_temp_critical_threshold_var,
                                       width=50, font=("Calibri", 14))
    gpu_critical_entry.pack(side='left', padx=(0, 3))
    gpu_critical_entry.bind("<KeyRelease>", state.mark_dirty)

    gpu_critical_unit = ctk.CTkLabel(master=gpu_alert_row, text="°C", font=("Calibri", 14))
    gpu_critical_unit.pack(side='left')

    # CPU Temperature Alerts
    cpu_alert_header = ctk.CTkLabel(master=thermal_alerts_frame, text="CPU Alerts", font=("Calibri", 15, "bold"))
    cpu_alert_header.pack(pady=(15, 5), anchor='w')

    cpu_alert_row = ctk.CTkFrame(master=thermal_alerts_frame, fg_color="transparent")
    cpu_alert_row.pack(pady=5, fill='x')

    state.enable_cpu_temp_alert_var = tk.BooleanVar(value=state.enable_cpu_temp_alert)
    enable_cpu_temp_alert_switch = ctk.CTkSwitch(master=cpu_alert_row, text="Enable",
                                                  variable=state.enable_cpu_temp_alert_var, font=("Calibri", 14),
                                                  command=state.mark_dirty)
    enable_cpu_temp_alert_switch.pack(side='left', padx=(0, 20))

    cpu_warning_label = ctk.CTkLabel(master=cpu_alert_row, text="Warning:", font=("Calibri", 14))
    cpu_warning_label.pack(side='left', padx=(0, 5))

    state.cpu_temp_warning_threshold_var = tk.StringVar(value=str(state.cpu_temp_warning_threshold))
    cpu_warning_entry = ctk.CTkEntry(master=cpu_alert_row, textvariable=state.cpu_temp_warning_threshold_var,
                                      width=50, font=("Calibri", 14))
    cpu_warning_entry.pack(side='left', padx=(0, 3))
    cpu_warning_entry.bind("<KeyRelease>", state.mark_dirty)

    cpu_warning_unit = ctk.CTkLabel(master=cpu_alert_row, text="°C", font=("Calibri", 14))
    cpu_warning_unit.pack(side='left', padx=(0, 15))

    cpu_critical_label = ctk.CTkLabel(master=cpu_alert_row, text="Critical:", font=("Calibri", 14), text_color="#ff6b6b")
    cpu_critical_label.pack(side='left', padx=(0, 5))

    state.cpu_temp_critical_threshold_var = tk.StringVar(value=str(state.cpu_temp_critical_threshold))
    cpu_critical_entry = ctk.CTkEntry(master=cpu_alert_row, textvariable=state.cpu_temp_critical_threshold_var,
                                       width=50, font=("Calibri", 14))
    cpu_critical_entry.pack(side='left', padx=(0, 3))
    cpu_critical_entry.bind("<KeyRelease>", state.mark_dirty)

    cpu_critical_unit = ctk.CTkLabel(master=cpu_alert_row, text="°C", font=("Calibri", 14))
    cpu_critical_unit.pack(side='left')

    thermal_alerts_note = ctk.CTkLabel(master=thermal_alerts_frame,
                                       text="Each alert level triggers once per gaming session.",
                                       font=("Calibri", 11), text_color="gray60")
    thermal_alerts_note.pack(pady=(15, 0), anchor='w')

    # Start the live temperature update loop
    if TEMP_FUNCTIONS_AVAILABLE:
        # Initial update after a short delay (let UI finish building)
        state.root.after(500, _update_temperature_display)

    return {}
