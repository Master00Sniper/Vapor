# ui/tabs/notifications.py
# Notifications tab for the Vapor Settings UI.

import os
import tkinter as tk
import customtkinter as ctk
from PIL import Image

from ui.constants import BUILT_IN_APPS
import ui.state as state
from ui.state import configure_fast_scroll


def build_notifications_tab(parent_frame):
    """
    Build the Notifications tab content.

    Args:
        parent_frame: The tab frame to build content in

    Returns:
        dict: References to widgets that need to be accessed elsewhere
    """
    notif_scroll_frame = ctk.CTkScrollableFrame(master=parent_frame, fg_color="transparent")
    notif_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
    configure_fast_scroll(notif_scroll_frame)

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

    state.close_startup_var = tk.StringVar(value="Enabled" if state.close_on_startup else "Disabled")
    ctk.CTkRadioButton(master=options_frame, text="Enabled", variable=state.close_startup_var, value="Enabled",
                       font=("Calibri", 14), command=state.mark_dirty).grid(row=0, column=1, pady=8, padx=15)
    ctk.CTkRadioButton(master=options_frame, text="Disabled", variable=state.close_startup_var, value="Disabled",
                       font=("Calibri", 14), command=state.mark_dirty).grid(row=0, column=2, pady=8, padx=15)

    close_hotkey_label = ctk.CTkLabel(master=options_frame, text="Close Apps With Hotkey (Ctrl+Alt+K):",
                                      font=("Calibri", 14))
    close_hotkey_label.grid(row=1, column=0, pady=8, padx=10, sticky='w')

    state.close_hotkey_var = tk.StringVar(value="Enabled" if state.close_on_hotkey else "Disabled")
    ctk.CTkRadioButton(master=options_frame, text="Enabled", variable=state.close_hotkey_var, value="Enabled",
                       font=("Calibri", 14), command=state.mark_dirty).grid(row=1, column=1, pady=8, padx=15)
    ctk.CTkRadioButton(master=options_frame, text="Disabled", variable=state.close_hotkey_var, value="Disabled",
                       font=("Calibri", 14), command=state.mark_dirty).grid(row=1, column=2, pady=8, padx=15)

    relaunch_exit_label = ctk.CTkLabel(master=options_frame, text="Relaunch Apps When Game Ends:",
                                       font=("Calibri", 14))
    relaunch_exit_label.grid(row=2, column=0, pady=8, padx=10, sticky='w')

    state.relaunch_exit_var = tk.StringVar(value="Enabled" if state.relaunch_on_exit else "Disabled")
    ctk.CTkRadioButton(master=options_frame, text="Enabled", variable=state.relaunch_exit_var, value="Enabled",
                       font=("Calibri", 14), command=state.mark_dirty).grid(row=2, column=1, pady=8, padx=15)
    ctk.CTkRadioButton(master=options_frame, text="Disabled", variable=state.relaunch_exit_var, value="Disabled",
                       font=("Calibri", 14), command=state.mark_dirty).grid(row=2, column=2, pady=8, padx=15)

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

    # Build app switches - first 4 in left column
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

        var = tk.BooleanVar(value=display_name in state.selected_notification_apps)
        state.switch_vars[display_name] = var
        switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14),
                               command=state.mark_dirty)
        switch.pack(side="left")

    # Remaining apps in right column
    for i in range(4, len(BUILT_IN_APPS)):
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

        var = tk.BooleanVar(value=display_name in state.selected_notification_apps)
        state.switch_vars[display_name] = var
        switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14),
                               command=state.mark_dirty)
        switch.pack(side="left")

    def on_all_apps_toggle():
        """Toggle all notification apps on/off."""
        toggle_state = all_apps_var.get()
        for var in state.switch_vars.values():
            var.set(toggle_state)
        state.mark_dirty()

    all_apps_var = tk.BooleanVar(value=all(display_name in state.selected_notification_apps for display_name in
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
                                placeholder_text="e.g., Viber.exe, Skype.exe, Zoom.exe")
    custom_entry.insert(0, ','.join(state.custom_processes))
    custom_entry.pack(pady=(0, 20), anchor='center')
    custom_entry.bind("<KeyRelease>", state.mark_dirty)

    # Store reference in state for save function
    state.custom_entry = custom_entry

    return {
        'custom_entry': custom_entry,
        'all_apps_var': all_apps_var
    }
