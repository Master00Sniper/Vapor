# ui/dialogs.py
# Vapor-styled dialog popups.

import ctypes
import os
import sys
import tkinter as tk
import customtkinter as ctk

from utils import base_dir


def set_dark_title_bar(window):
    """Set the Windows title bar to dark mode. Only works on Windows 10/11."""
    if sys.platform != 'win32':
        return

    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 10 20H1+)
        # For older Windows 10, use attribute 19
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:
        pass  # Silently fail on non-Windows or older Windows


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

    # Calculate size based on message length
    width = 500
    height = 320 + (message.count('\n') * 12)
    height = min(height, 500)  # Cap max height

    # Use plain tkinter Toplevel for full control - withdraw BEFORE it can render
    # CTkToplevel causes a flash because its __init__ does too much before we can hide it
    if parent:
        dialog = tk.Toplevel(parent)
    else:
        dialog = ctk.CTk()
    dialog.withdraw()  # Hide immediately - this works because tk.Toplevel is simpler

    # Calculate center position
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    dialog.geometry(f"{width}x{height}+{x}+{y}")

    # Set dark theme background to match CTk style
    dialog.configure(bg='#2b2b2b')

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

    # Process all pending events to ensure content is laid out
    dialog.update_idletasks()

    # Now show the window - using plain tk.Toplevel means no flash
    dialog.deiconify()
    set_dark_title_bar(dialog)  # Apply dark title bar after window is shown
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
