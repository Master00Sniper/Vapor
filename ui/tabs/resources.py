# ui/tabs/resources.py
# Resources tab for the Vapor Settings UI.

import os
import tkinter as tk
import customtkinter as ctk
from PIL import Image

from ui.constants import BUILT_IN_RESOURCE_APPS
import ui.state as state


def build_resources_tab(parent_frame):
    """
    Build the Resources tab content.

    Args:
        parent_frame: The tab frame to build content in

    Returns:
        dict: References to widgets that need to be accessed elsewhere
    """
    res_scroll_frame = ctk.CTkScrollableFrame(master=parent_frame, fg_color="transparent")
    res_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

    resource_title = ctk.CTkLabel(master=res_scroll_frame, text="Resource Management", font=("Calibri", 25, "bold"))
    resource_title.pack(pady=(10, 5), anchor='center')

    res_description = ctk.CTkLabel(master=res_scroll_frame,
                                   text="Control which resource-intensive apps are closed to free up system resources during gaming.",
                                   font=("Calibri", 13), text_color="gray60")
    res_description.pack(pady=(0, 15), anchor='center')

    res_sep1 = ctk.CTkFrame(master=res_scroll_frame, height=2, fg_color="gray50")
    res_sep1.pack(fill="x", padx=40, pady=10)

    res_behavior_title = ctk.CTkLabel(master=res_scroll_frame, text="Behavior Settings", font=("Calibri", 17, "bold"))
    res_behavior_title.pack(pady=(10, 10), anchor='center')

    resource_options_frame = ctk.CTkFrame(master=res_scroll_frame, fg_color="transparent")
    resource_options_frame.pack(pady=10, padx=20)

    resource_close_startup_label = ctk.CTkLabel(master=resource_options_frame,
                                                text="Close Apps When Game Starts:",
                                                font=("Calibri", 14))
    resource_close_startup_label.grid(row=0, column=0, pady=8, padx=10, sticky='w')

    state.resource_close_startup_var = tk.StringVar(value="Enabled" if state.resource_close_on_startup else "Disabled")
    ctk.CTkRadioButton(master=resource_options_frame, text="Enabled", variable=state.resource_close_startup_var,
                       value="Enabled", font=("Calibri", 14), command=state.mark_dirty).grid(row=0, column=1, pady=8, padx=15)
    ctk.CTkRadioButton(master=resource_options_frame, text="Disabled", variable=state.resource_close_startup_var,
                       value="Disabled", font=("Calibri", 14), command=state.mark_dirty).grid(row=0, column=2, pady=8, padx=15)

    resource_close_hotkey_label = ctk.CTkLabel(master=resource_options_frame,
                                               text="Close Apps With Hotkey (Ctrl+Alt+K):", font=("Calibri", 14))
    resource_close_hotkey_label.grid(row=1, column=0, pady=8, padx=10, sticky='w')

    state.resource_close_hotkey_var = tk.StringVar(value="Enabled" if state.resource_close_on_hotkey else "Disabled")
    ctk.CTkRadioButton(master=resource_options_frame, text="Enabled", variable=state.resource_close_hotkey_var,
                       value="Enabled", font=("Calibri", 14), command=state.mark_dirty).grid(row=1, column=1, pady=8, padx=15)
    ctk.CTkRadioButton(master=resource_options_frame, text="Disabled", variable=state.resource_close_hotkey_var,
                       value="Disabled", font=("Calibri", 14), command=state.mark_dirty).grid(row=1, column=2, pady=8, padx=15)

    resource_relaunch_exit_label = ctk.CTkLabel(master=resource_options_frame,
                                                text="Relaunch Apps When Game Ends:",
                                                font=("Calibri", 14))
    resource_relaunch_exit_label.grid(row=2, column=0, pady=8, padx=10, sticky='w')

    state.resource_relaunch_exit_var = tk.StringVar(value="Enabled" if state.resource_relaunch_on_exit else "Disabled")
    ctk.CTkRadioButton(master=resource_options_frame, text="Enabled", variable=state.resource_relaunch_exit_var,
                       value="Enabled", font=("Calibri", 14), command=state.mark_dirty).grid(row=2, column=1, pady=8, padx=15)
    ctk.CTkRadioButton(master=resource_options_frame, text="Disabled", variable=state.resource_relaunch_exit_var,
                       value="Disabled", font=("Calibri", 14), command=state.mark_dirty).grid(row=2, column=2, pady=8, padx=15)

    res_sep2 = ctk.CTkFrame(master=res_scroll_frame, height=2, fg_color="gray50")
    res_sep2.pack(fill="x", padx=40, pady=15)

    resource_apps_subtitle = ctk.CTkLabel(master=res_scroll_frame, text="Select Apps to Manage",
                                          font=("Calibri", 17, "bold"))
    resource_apps_subtitle.pack(pady=(10, 5), anchor='center')

    res_apps_hint = ctk.CTkLabel(master=res_scroll_frame,
                                 text="Toggle the resource-heavy apps you want Vapor to close during gaming sessions.",
                                 font=("Calibri", 12), text_color="gray60")
    res_apps_hint.pack(pady=(0, 10), anchor='center')

    resource_app_frame = ctk.CTkFrame(master=res_scroll_frame, fg_color="transparent")
    resource_app_frame.pack(pady=10, padx=10)

    resource_left_column = ctk.CTkFrame(master=resource_app_frame, fg_color="transparent")
    resource_left_column.pack(side="left", padx=10)

    resource_middle_column = ctk.CTkFrame(master=resource_app_frame, fg_color="transparent")
    resource_middle_column.pack(side="left", padx=10)

    resource_right_column = ctk.CTkFrame(master=resource_app_frame, fg_color="transparent")
    resource_right_column.pack(side="left", padx=10)

    # Browsers column (indices 0-3)
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
            ctk.CTkLabel(master=row_frame, text="*", font=("Calibri", 15)).pack(side="left", padx=5)

        var = tk.BooleanVar(value=display_name in state.selected_resource_apps)
        state.resource_switch_vars[display_name] = var
        switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14),
                               command=state.mark_dirty)
        switch.pack(side="left")

    # Cloud/Media column (indices 4-7)
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
            ctk.CTkLabel(master=row_frame, text="*", font=("Calibri", 15)).pack(side="left", padx=5)

        var = tk.BooleanVar(value=display_name in state.selected_resource_apps)
        state.resource_switch_vars[display_name] = var
        switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14),
                               command=state.mark_dirty)
        switch.pack(side="left")

    # Gaming Utilities column (indices 8-11)
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
            ctk.CTkLabel(master=row_frame, text="*", font=("Calibri", 15)).pack(side="left", padx=5)

        var = tk.BooleanVar(value=display_name in state.selected_resource_apps)
        state.resource_switch_vars[display_name] = var
        switch = ctk.CTkSwitch(master=row_frame, text=display_name, variable=var, font=("Calibri", 14),
                               command=state.mark_dirty)
        switch.pack(side="left")

    def on_resource_all_apps_toggle():
        """Toggle all resource apps on/off."""
        toggle_state = resource_all_apps_var.get()
        for var in state.resource_switch_vars.values():
            var.set(toggle_state)
        state.mark_dirty()

    resource_all_apps_var = tk.BooleanVar(value=all(display_name in state.selected_resource_apps for display_name in
                                                    [app['display_name'] for app in BUILT_IN_RESOURCE_APPS]))

    resource_all_apps_switch = ctk.CTkSwitch(master=res_scroll_frame, text="Toggle All Apps",
                                             variable=resource_all_apps_var,
                                             command=on_resource_all_apps_toggle, font=("Calibri", 14))
    resource_all_apps_switch.pack(pady=10, anchor='center')

    res_sep3 = ctk.CTkFrame(master=res_scroll_frame, height=2, fg_color="gray50")
    res_sep3.pack(fill="x", padx=40, pady=15)

    res_custom_title = ctk.CTkLabel(master=res_scroll_frame, text="Custom Processes", font=("Calibri", 17, "bold"))
    res_custom_title.pack(pady=(10, 5), anchor='center')

    custom_resource_label = ctk.CTkLabel(master=res_scroll_frame,
                                         text="Add additional processes to close (comma-separated, e.g.: MyApp1.exe, MyApp2.exe)",
                                         font=("Calibri", 12), text_color="gray60")
    custom_resource_label.pack(pady=(0, 10), anchor='center')

    custom_resource_entry = ctk.CTkEntry(master=res_scroll_frame, width=550, font=("Calibri", 14),
                                         placeholder_text="e.g., Spotify.exe, OBS64.exe, vlc.exe")
    custom_resource_entry.insert(0, ','.join(state.custom_resource_processes))
    custom_resource_entry.pack(pady=(0, 20), anchor='center')
    custom_resource_entry.bind("<KeyRelease>", state.mark_dirty)

    # Store reference in state for save function
    state.custom_resource_entry = custom_resource_entry

    return {
        'custom_resource_entry': custom_resource_entry,
        'resource_all_apps_var': resource_all_apps_var
    }
