# ui/tabs/preferences.py
# Preferences tab for the Vapor Settings UI.
# Includes general settings, audio, power management, game mode, and Konami code easter egg.

import tkinter as tk
import customtkinter as ctk

import ui.state as state
from ui.state import configure_fast_scroll
from ui.constants import TAB_PREFERENCES
from ui.dialogs import show_vapor_dialog


def _shake_window(callback=None):
    """Shake the window briefly as visual feedback."""
    root = state.root
    original_x = root.winfo_x()
    original_y = root.winfo_y()
    shake_distance = 8
    shake_speed = 30  # milliseconds between movements

    shake_sequence = [
        (shake_distance, 0), (-shake_distance, 0),
        (shake_distance, 0), (-shake_distance, 0),
        (0, 0)  # Return to original position
    ]

    def do_shake(index=0):
        if index < len(shake_sequence):
            dx, dy = shake_sequence[index]
            root.geometry(f"+{original_x + dx}+{original_y + dy}")
            root.after(shake_speed, lambda: do_shake(index + 1))
        else:
            # Ensure window is back to original position
            root.geometry(f"+{original_x}+{original_y}")
            if callback:
                callback()

    do_shake()


def _reveal_hidden_toggles():
    """Reveal the debug toggle and telemetry opt-out after shake animation."""
    state._easter_egg_revealed[0] = True
    state.debug_mode_switch.pack(pady=5, anchor='w', after=state.startup_switch)
    state.telemetry_frame.pack(pady=5, anchor='w')
    state.telemetry_switch.pack(side="left")
    state.telemetry_hint.pack(pady=(0, 5), anchor='w', padx=(48, 0))


def _check_konami(event):
    """Check if the Konami code sequence is being entered on Preferences tab."""
    if state._easter_egg_revealed[0]:
        return  # Already revealed, no need to check

    # Only respond when Preferences tab is active
    try:
        if state.tabview.get() != TAB_PREFERENCES:
            state._konami_index[0] = 0  # Reset if not on preferences tab
            return
    except Exception:
        return

    key = event.keysym
    expected = state._konami_sequence[state._konami_index[0]]

    if key == expected:
        state._konami_index[0] += 1
        if state._konami_index[0] >= len(state._konami_sequence):
            # Konami code complete - shake window then reveal hidden toggles
            state._konami_index[0] = 0
            _shake_window(callback=_reveal_hidden_toggles)
    else:
        # Reset sequence on wrong key
        state._konami_index[0] = 0


def build_preferences_tab(parent_frame):
    """
    Build the Preferences tab content.

    Args:
        parent_frame: The tab frame to build content in

    Returns:
        dict: References to widgets that need to be accessed elsewhere
    """
    pref_scroll_frame = ctk.CTkScrollableFrame(master=parent_frame, fg_color="transparent")
    pref_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
    configure_fast_scroll(pref_scroll_frame)

    preferences_title = ctk.CTkLabel(master=pref_scroll_frame, text="Preferences", font=("Calibri", 25, "bold"))
    preferences_title.pack(pady=(10, 5), anchor='center')

    pref_description = ctk.CTkLabel(master=pref_scroll_frame,
                                    text="Customize Vapor's behavior, audio settings, and power management options.",
                                    font=("Calibri", 13), text_color="gray60")
    pref_description.pack(pady=(0, 15), anchor='center')

    pref_sep1 = ctk.CTkFrame(master=pref_scroll_frame, height=2, fg_color="gray50")
    pref_sep1.pack(fill="x", padx=40, pady=10)

    # =========================================================================
    # General Settings Section
    # =========================================================================
    general_title = ctk.CTkLabel(master=pref_scroll_frame, text="General Settings", font=("Calibri", 17, "bold"))
    general_title.pack(pady=(10, 10), anchor='center')

    general_frame = ctk.CTkFrame(master=pref_scroll_frame, fg_color="transparent")
    general_frame.pack(pady=5, padx=40, anchor='center')

    state.launch_settings_on_start_var = tk.BooleanVar(value=state.launch_settings_on_start)
    launch_settings_on_start_switch = ctk.CTkSwitch(master=general_frame, text="Open Settings Window on Vapor Start",
                                                    variable=state.launch_settings_on_start_var, font=("Calibri", 14),
                                                    command=state.mark_dirty)
    launch_settings_on_start_switch.pack(pady=5, anchor='w')

    state.playtime_summary_var = tk.BooleanVar(value=state.enable_playtime_summary)
    playtime_summary_switch = ctk.CTkSwitch(master=general_frame, text="Show Playtime Summary After Gaming",
                                            variable=state.playtime_summary_var, font=("Calibri", 14),
                                            command=state.mark_dirty)
    playtime_summary_switch.pack(pady=5, anchor='w')

    # Playtime summary mode selection (Brief vs Detailed)
    summary_mode_frame = ctk.CTkFrame(master=general_frame, fg_color="transparent")
    summary_mode_frame.pack(pady=(0, 5), anchor='w', padx=(30, 0))

    summary_mode_label = ctk.CTkLabel(master=summary_mode_frame, text="Summary Style:",
                                      font=("Calibri", 13))
    summary_mode_label.pack(side="left", padx=(0, 10))

    state.playtime_summary_mode_var = tk.StringVar(value=state.playtime_summary_mode)
    ctk.CTkRadioButton(master=summary_mode_frame, text="Brief", variable=state.playtime_summary_mode_var,
                       value="brief", font=("Calibri", 13), command=state.mark_dirty).pack(side="left", padx=10)
    ctk.CTkRadioButton(master=summary_mode_frame, text="Detailed", variable=state.playtime_summary_mode_var,
                       value="detailed", font=("Calibri", 13), command=state.mark_dirty).pack(side="left", padx=10)

    state.startup_var = tk.BooleanVar(value=state.launch_at_startup)
    state.startup_switch = ctk.CTkSwitch(master=general_frame, text="Launch Vapor at System Startup",
                                         variable=state.startup_var, font=("Calibri", 14), command=state.mark_dirty)
    state.startup_switch.pack(pady=5, anchor='w')

    state.debug_mode_var = tk.BooleanVar(value=state.enable_debug_mode)
    state.debug_mode_switch = ctk.CTkSwitch(master=general_frame, text="Enable Debug Console Window",
                                            variable=state.debug_mode_var, font=("Calibri", 14),
                                            command=state.mark_dirty)
    # Debug switch is hidden by default - revealed by Konami code easter egg

    # Bind Konami code key events to root window
    state.root.bind('<Up>', _check_konami)
    state.root.bind('<Down>', _check_konami)
    state.root.bind('<Left>', _check_konami)
    state.root.bind('<Right>', _check_konami)

    # Telemetry toggle with description (hidden by default)
    state.telemetry_frame = ctk.CTkFrame(master=general_frame, fg_color="transparent")
    # telemetry_frame.pack(pady=5, anchor='w')  # Don't pack initially

    state.enable_telemetry_var = tk.BooleanVar(value=state.enable_telemetry)

    def on_telemetry_toggle():
        """Show confirmation dialog when user tries to disable telemetry."""
        if not state.enable_telemetry_var.get():
            # User is trying to turn off telemetry - show confirmation
            response = show_vapor_dialog(
                title="Disable Usage Statistics?",
                message="Anonymous usage statistics help the developer understand\n"
                        "how many people are using Vapor.\n\n"
                        "No personal data is ever collected - only:\n"
                        "• App start and heartbeat events\n"
                        "• Vapor version number\n"
                        "• Operating system type\n"
                        "• A random installation ID\n\n"
                        "Are you sure you want to disable this?",
                dialog_type="info",
                buttons=[
                    {"text": "Leave It On", "value": False, "color": "green"},
                    {"text": "Stop Sending", "value": True, "color": "red"}
                ],
                parent=state.root
            )
            if not response:
                # User chose to leave it on - revert the toggle
                state.enable_telemetry_var.set(True)
                return  # No change was made
        state.mark_dirty()

    state.telemetry_switch = ctk.CTkSwitch(master=state.telemetry_frame, text="Send Anonymous Usage Statistics",
                                           variable=state.enable_telemetry_var, font=("Calibri", 14),
                                           command=on_telemetry_toggle)
    # Telemetry switch is hidden by default - revealed by Konami code easter egg

    state.telemetry_hint = ctk.CTkLabel(master=general_frame,
                                        text="No personal data is collected. Only used to see how many people use Vapor.",
                                        font=("Calibri", 11), text_color="gray50")
    # telemetry_hint.pack hidden by default

    # =========================================================================
    # Audio Settings Section
    # =========================================================================
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

    # System Volume column
    system_audio_column = ctk.CTkFrame(master=audio_frame, fg_color="transparent")
    system_audio_column.pack(side="left", padx=40)

    system_audio_label = ctk.CTkLabel(master=system_audio_column, text="System Volume", font=("Calibri", 15, "bold"))
    system_audio_label.pack(anchor='center')

    state.system_audio_slider_var = tk.IntVar(value=state.system_audio_level)
    system_audio_slider = ctk.CTkSlider(master=system_audio_column, from_=0, to=100, number_of_steps=100,
                                        variable=state.system_audio_slider_var, width=180)
    system_audio_slider.pack(pady=5, anchor='center')

    system_current_value_label = ctk.CTkLabel(master=system_audio_column, text=f"{state.system_audio_level}%",
                                              font=("Calibri", 14))
    system_current_value_label.pack(anchor='center')

    def update_system_audio_label(value):
        """Update the system audio percentage display."""
        system_current_value_label.configure(text=f"{int(value)}%")
        state.mark_dirty()

    system_audio_slider.configure(command=update_system_audio_label)

    state.enable_system_audio_var = tk.BooleanVar(value=state.enable_system_audio)
    enable_system_audio_switch = ctk.CTkSwitch(master=system_audio_column, text="Enable",
                                               variable=state.enable_system_audio_var,
                                               font=("Calibri", 14), command=state.mark_dirty)
    enable_system_audio_switch.pack(pady=8, anchor='center')

    # Game Volume column
    game_audio_column = ctk.CTkFrame(master=audio_frame, fg_color="transparent")
    game_audio_column.pack(side="left", padx=40)

    game_audio_label = ctk.CTkLabel(master=game_audio_column, text="Game Volume", font=("Calibri", 15, "bold"))
    game_audio_label.pack(anchor='center')

    state.game_audio_slider_var = tk.IntVar(value=state.game_audio_level)
    game_audio_slider = ctk.CTkSlider(master=game_audio_column, from_=0, to=100, number_of_steps=100,
                                      variable=state.game_audio_slider_var, width=180)
    game_audio_slider.pack(pady=5, anchor='center')

    game_current_value_label = ctk.CTkLabel(master=game_audio_column, text=f"{state.game_audio_level}%",
                                            font=("Calibri", 14))
    game_current_value_label.pack(anchor='center')

    def update_game_audio_label(value):
        """Update the game audio percentage display."""
        game_current_value_label.configure(text=f"{int(value)}%")
        state.mark_dirty()

    game_audio_slider.configure(command=update_game_audio_label)

    state.enable_game_audio_var = tk.BooleanVar(value=state.enable_game_audio)
    enable_game_audio_switch = ctk.CTkSwitch(master=game_audio_column, text="Enable",
                                             variable=state.enable_game_audio_var,
                                             font=("Calibri", 14), command=state.mark_dirty)
    enable_game_audio_switch.pack(pady=8, anchor='center')

    # Note about exclusive audio mode
    audio_note = ctk.CTkLabel(master=pref_scroll_frame,
                              text="Note: Some games use exclusive audio mode and won't reflect changes\n"
                                   "in Windows Volume Mixer. Vapor will still set the volume for these\n"
                                   "games, but further adjustments require restarting the game.",
                              font=("Calibri", 12), text_color="gray50", justify="center", wraplength=400)
    audio_note.pack(pady=(15, 5), anchor='center')

    # =========================================================================
    # Power Management Section
    # =========================================================================
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

    # During Gaming column
    during_power_column = ctk.CTkFrame(master=power_frame, fg_color="transparent")
    during_power_column.pack(side="left", padx=40)

    during_power_label = ctk.CTkLabel(master=during_power_column, text="While Gaming", font=("Calibri", 15, "bold"))
    during_power_label.pack(anchor='center')

    state.during_power_var = tk.StringVar(value=state.during_power_plan)
    during_power_combobox = ctk.CTkComboBox(master=during_power_column,
                                            values=["High Performance", "Balanced", "Power saver"],
                                            variable=state.during_power_var, width=160, command=lambda _: state.mark_dirty())
    during_power_combobox.pack(pady=5, anchor='center')

    state.enable_during_power_var = tk.BooleanVar(value=state.enable_during_power)
    enable_during_power_switch = ctk.CTkSwitch(master=during_power_column, text="Enable",
                                               variable=state.enable_during_power_var,
                                               font=("Calibri", 14), command=state.mark_dirty)
    enable_during_power_switch.pack(pady=8, anchor='center')

    # After Gaming column
    after_power_column = ctk.CTkFrame(master=power_frame, fg_color="transparent")
    after_power_column.pack(side="left", padx=40)

    after_power_label = ctk.CTkLabel(master=after_power_column, text="After Gaming", font=("Calibri", 15, "bold"))
    after_power_label.pack(anchor='center')

    state.after_power_var = tk.StringVar(value=state.after_power_plan)
    after_power_combobox = ctk.CTkComboBox(master=after_power_column,
                                           values=["High Performance", "Balanced", "Power saver"],
                                           variable=state.after_power_var, width=160, command=lambda _: state.mark_dirty())
    after_power_combobox.pack(pady=5, anchor='center')

    state.enable_after_power_var = tk.BooleanVar(value=state.enable_after_power)
    enable_after_power_switch = ctk.CTkSwitch(master=after_power_column, text="Enable",
                                              variable=state.enable_after_power_var,
                                              font=("Calibri", 14), command=state.mark_dirty)
    enable_after_power_switch.pack(pady=8, anchor='center')

    # =========================================================================
    # Game Mode Section
    # =========================================================================
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

    state.enable_game_mode_start_var = tk.BooleanVar(value=state.enable_game_mode_start)
    enable_game_mode_start_switch = ctk.CTkSwitch(master=game_mode_frame, text="Enable Game Mode When Game Starts",
                                                  variable=state.enable_game_mode_start_var, font=("Calibri", 14),
                                                  command=state.mark_dirty)
    enable_game_mode_start_switch.pack(pady=5, anchor='w')

    state.enable_game_mode_end_var = tk.BooleanVar(value=state.enable_game_mode_end)
    enable_game_mode_end_switch = ctk.CTkSwitch(master=game_mode_frame, text="Disable Game Mode When Game Ends",
                                                variable=state.enable_game_mode_end_var, font=("Calibri", 14),
                                                command=state.mark_dirty)
    enable_game_mode_end_switch.pack(pady=5, anchor='w')

    return {}
