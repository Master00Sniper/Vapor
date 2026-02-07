# ui/dialogs.py
# Vapor-styled dialog popups.

import os
import customtkinter as ctk

from utils import base_dir


def set_vapor_icon(window):
    """Set the Vapor icon on a window. Call this after window is created."""
    icon_path = os.path.join(base_dir, 'Images', 'exe_icon.ico')
    if not os.path.exists(icon_path):
        return

    def apply_icon():
        try:
            if window.winfo_exists():
                window.iconbitmap(icon_path)
        except Exception:
            pass

    # Try setting icon immediately
    try:
        window.iconbitmap(icon_path)
    except Exception:
        pass

    # CTkToplevel windows often need the icon set after they're fully rendered
    # Schedule multiple attempts to ensure it sticks
    try:
        window.after(10, apply_icon)
        window.after(50, apply_icon)
        window.after(100, apply_icon)
        window.after(200, apply_icon)
    except Exception:
        pass


def show_vapor_dialog(title, message, dialog_type="info", buttons=None, parent=None):
    """
    Show a Vapor-themed dialog popup that matches the app's style.

    Args:
        title: Dialog window title
        message: Message text to display
        dialog_type: "info", "warning", "error", or "question"
        buttons: List of button configs, e.g. [{"text": "Yes", "value": True, "color": "green"}, ...]
                 If None, defaults to a single "OK" button
        parent: Parent window (optional)

    Returns:
        The value associated with the clicked button, or None if closed
    """
    result = [None]  # Use list to allow modification in nested function

    # Create popup window - withdraw immediately to prevent any flash
    dialog = ctk.CTkToplevel(parent) if parent else ctk.CTk()
    dialog.withdraw()  # Hide immediately before window manager can display it

    # Calculate size based on message length
    width = 500
    height = 320 + (message.count('\n') * 12)
    height = min(height, 500)  # Cap max height

    # Set geometry while withdrawn
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    dialog.geometry(f"{width}x{height}+{x}+{y}")

    # Set icon while window is withdrawn
    icon_path = os.path.join(base_dir, 'Images', 'exe_icon.ico')
    if os.path.exists(icon_path):
        try:
            dialog.iconbitmap(icon_path)
        except Exception:
            pass

    dialog.title(f"Vapor - {title}")
    dialog.resizable(False, False)

    # Make dialog modal
    if parent:
        dialog.transient(parent)
    dialog.grab_set()

    # Main content frame (expandable)
    content_frame = ctk.CTkFrame(master=dialog, fg_color="transparent")
    content_frame.pack(fill="both", expand=True, padx=25, pady=(25, 10))

    # Title label with appropriate color based on type
    title_colors = {
        "info": ("white", None),
        "warning": ("orange", None),
        "error": ("#ff6b6b", None),
        "question": ("white", None)
    }
    title_color = title_colors.get(dialog_type, ("white", None))[0]

    title_label = ctk.CTkLabel(
        master=content_frame,
        text=title,
        font=("Calibri", 21, "bold"),
        text_color=title_color
    )
    title_label.pack(pady=(0, 15))

    # Message label
    message_label = ctk.CTkLabel(
        master=content_frame,
        text=message,
        font=("Calibri", 14),
        justify="left",
        wraplength=450
    )
    message_label.pack(pady=(0, 10))

    # Separator line above buttons (matching settings UI style)
    separator = ctk.CTkFrame(master=dialog, height=2, fg_color="gray50")
    separator.pack(fill="x", padx=40, pady=(10, 0))

    # Button frame at bottom (matching settings UI style)
    button_frame = ctk.CTkFrame(master=dialog, fg_color="transparent")
    button_frame.pack(pady=20, fill='x', padx=40)

    # Default buttons if none specified
    if buttons is None:
        buttons = [{"text": "OK", "value": True, "color": "green"}]

    def make_button_callback(value):
        def callback():
            result[0] = value
            dialog.destroy()
        return callback

    # Create buttons centered in frame
    buttons_container = ctk.CTkFrame(master=button_frame, fg_color="transparent")
    buttons_container.pack(anchor="center")

    for btn_config in buttons:
        btn_text = btn_config.get("text", "OK")
        btn_value = btn_config.get("value", None)
        btn_color = btn_config.get("color", "gray")

        # Map color names to actual colors with hover states
        color_map = {
            "green": ("#28a745", "#218838"),      # Positive/confirm actions
            "red": ("#c9302c", "#a02622"),        # Destructive actions
            "darkred": ("#8b0000", "#5c0000"),    # Very destructive actions
            "gray": ("#6c757d", "#5a6268"),       # Neutral/cancel actions
            "blue": ("#2563eb", "#1d4ed8"),       # Informational actions
            "orange": ("#e67e22", "#d35400")      # Warning/caution actions
        }
        fg_color, hover_color = color_map.get(btn_color, ("gray", "#555555"))

        btn = ctk.CTkButton(
            master=buttons_container,
            text=btn_text,
            command=make_button_callback(btn_value),
            width=150,
            height=36,
            corner_radius=10,
            fg_color=fg_color,
            hover_color=hover_color,
            font=("Calibri", 16)
        )
        btn.pack(side="left", padx=15)

    # Handle window close button (X)
    dialog.protocol("WM_DELETE_WINDOW", lambda: (result.__setitem__(0, None), dialog.destroy()))

    # Process pending events and show the window
    dialog.update_idletasks()
    dialog.deiconify()

    # Set icon AFTER deiconify to override CTkToplevel's internal icon setting
    icon_path = os.path.join(base_dir, 'Images', 'exe_icon.ico')
    if os.path.exists(icon_path):
        try:
            dialog.iconbitmap(icon_path)
        except Exception:
            pass

    dialog.lift()
    dialog.attributes('-topmost', True)
    dialog.after(100, lambda: dialog.attributes('-topmost', False))
    dialog.focus_force()

    # Wait for dialog to close
    if parent:
        dialog.wait_window()
    else:
        dialog.mainloop()

    return result[0]
