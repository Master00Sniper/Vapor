# core/notifications.py
# Notification and popup functionality for Vapor application

import os
import threading
import winreg

import win11toast

from utils import appdata_dir, base_dir, TRAY_ICON_PATH, log
from core.steam_api import get_preloaded_game_details, get_preloaded_header_image, get_cached_header_image_path


# =============================================================================
# Popup Window Management
# =============================================================================

# Track open popup windows for cleanup on quit
_open_popups = []
_open_popups_lock = threading.Lock()


def register_popup(popup):
    """Register a popup window for cleanup on quit."""
    with _open_popups_lock:
        _open_popups.append(popup)


def unregister_popup(popup):
    """Unregister a popup window when it's closed."""
    with _open_popups_lock:
        if popup in _open_popups:
            _open_popups.remove(popup)


def close_all_popups():
    """Close all registered popup windows.

    Note: Popups created in daemon threads may cause Tcl errors if we try to
    close them from the main thread. We catch all exceptions since daemon
    threads will be killed anyway when the main program exits.
    """
    with _open_popups_lock:
        for popup in _open_popups[:]:  # Copy list to avoid modification during iteration
            try:
                # Try to check if popup still exists and close it
                if popup.winfo_exists():
                    popup.quit()  # Stop mainloop
                    popup.destroy()
            except Exception:
                # Ignore Tcl thread errors - daemon threads will die with main thread
                pass
        _open_popups.clear()


# =============================================================================
# Windows Notification Check
# =============================================================================

# File to track if user dismissed the notification warning
NOTIFICATION_WARNING_DISMISSED_FILE = os.path.join(appdata_dir, 'notification_warning_dismissed')


def are_windows_notifications_enabled():
    """
    Check if Windows notifications are enabled and not blocked by Do Not Disturb.
    Returns tuple: (notifications_enabled, reason_string)
    """
    try:
        # Check 1: Main notification toggle
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
            value, _ = winreg.QueryValueEx(key, "ToastEnabled")
            winreg.CloseKey(key)
            if value == 0:
                return False, "notifications_disabled"
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Check 2: Newer notification settings path
        try:
            key_path2 = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path2)
            try:
                value, _ = winreg.QueryValueEx(key, "NOC_GLOBAL_SETTING_TOASTS_ENABLED")
                if value == 0:
                    winreg.CloseKey(key)
                    return False, "notifications_disabled"
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Check 3: Windows 11 Do Not Disturb via CloudStore
        # The data contains the profile name as UTF-16LE after a binary header
        # We search for the byte patterns directly:
        # - b'U\x00n\x00r\x00e\x00s\x00t\x00r\x00i\x00c\x00t\x00e\x00d' = Unrestricted (DND OFF)
        # - b'P\x00r\x00i\x00o\x00r\x00i\x00t\x00y\x00O\x00n\x00l\x00y' = PriorityOnly (DND ON)
        # - b'A\x00l\x00a\x00r\x00m\x00s\x00O\x00n\x00l\x00y' = AlarmsOnly (DND ON)
        try:
            base_path = r"Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base_path)

            # Find the quiethourssettings key (has GUID prefix)
            i = 0
            settings_key_name = None
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    if 'quiethourssettings' in subkey_name.lower() and 'profile' not in subkey_name.lower():
                        settings_key_name = subkey_name
                        break
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)

            if settings_key_name:
                # Read the nested subkey with the actual Data
                full_path = f"{base_path}\\{settings_key_name}\\windows.data.donotdisturb.quiethourssettings"
                try:
                    dnd_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, full_path)
                    data, _ = winreg.QueryValueEx(dnd_key, "Data")
                    winreg.CloseKey(dnd_key)

                    # Search for profile name patterns in the raw bytes
                    # UTF-16LE encoding means each ASCII char is followed by \x00
                    if b'U\x00n\x00r\x00e\x00s\x00t\x00r\x00i\x00c\x00t\x00e\x00d' in data:
                        # DND is OFF - notifications are enabled
                        pass
                    elif b'P\x00r\x00i\x00o\x00r\x00i\x00t\x00y\x00O\x00n\x00l\x00y' in data:
                        return False, "do_not_disturb"
                    elif b'A\x00l\x00a\x00r\x00m\x00s\x00O\x00n\x00l\x00y' in data:
                        return False, "do_not_disturb"
                except FileNotFoundError:
                    pass
                except Exception:
                    pass
        except FileNotFoundError:
            pass
        except Exception:
            pass

        return True, "enabled"
    except Exception:
        return True, "enabled"


def was_notification_warning_dismissed():
    """Check if user has previously dismissed the notification warning."""
    return os.path.exists(NOTIFICATION_WARNING_DISMISSED_FILE)


def mark_notification_warning_dismissed():
    """Mark that user has dismissed the notification warning."""
    try:
        with open(NOTIFICATION_WARNING_DISMISSED_FILE, 'w') as f:
            f.write('dismissed')
    except Exception:
        pass


def show_notification_warning_popup(reason="notifications_disabled"):
    """
    Show a styled popup warning about Windows notifications being disabled.
    Uses CustomTkinter to match the settings UI style.

    Args:
        reason: Either "notifications_disabled" or "do_not_disturb"
    """
    import customtkinter as ctk

    # Create popup window
    popup = ctk.CTk()
    popup.withdraw()  # Hide while setting up to avoid icon flash

    # Register popup for cleanup on quit
    register_popup(popup)

    def on_close():
        unregister_popup(popup)
        popup.destroy()

    popup.protocol("WM_DELETE_WINDOW", on_close)

    if reason == "do_not_disturb":
        popup.title("Vapor - Do Not Disturb Enabled")
        title_text = "Do Not Disturb is Enabled"
        message_text = """Vapor uses Windows notifications to keep you informed about:

  *  When Vapor starts monitoring your games
  *  Playtime summaries after gaming sessions
  *  App updates and other important messages

Windows "Do Not Disturb" (Focus) mode is currently on, so you
won't see these messages. Vapor will still function normally.

To see Vapor notifications, either:
  *  Turn off Do Not Disturb in the system tray
  *  Add Vapor to your priority notifications list"""
    else:
        popup.title("Vapor - Notifications Disabled")
        title_text = "Windows Notifications Disabled"
        message_text = """Vapor uses Windows notifications to keep you informed about:

  *  When Vapor starts monitoring your games
  *  Playtime summaries after gaming sessions
  *  App updates and other important messages

Your Windows notifications appear to be turned off, so you
won't see these messages. Vapor will still function normally.

To enable notifications, go to:
Windows Settings > System > Notifications"""

    popup.geometry("500x340")
    popup.resizable(False, False)

    # Center on screen
    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()
    x = (screen_width - 500) // 2
    y = (screen_height - 340) // 2
    popup.geometry(f"500x340+{x}+{y}")

    # Set window icon
    icon_path = os.path.join(base_dir, 'Images', 'exe_icon.ico')
    if os.path.exists(icon_path):
        try:
            popup.iconbitmap(icon_path)
        except Exception:
            pass

    # Bring window to front and give it focus
    popup.lift()
    popup.attributes('-topmost', True)
    popup.after(100, lambda: popup.attributes('-topmost', False))
    popup.focus_force()

    # Title
    title_label = ctk.CTkLabel(
        master=popup,
        text=title_text,
        font=("Calibri", 20, "bold")
    )
    title_label.pack(pady=(25, 15))

    # Message
    message_label = ctk.CTkLabel(
        master=popup,
        text=message_text,
        font=("Calibri", 12),
        justify="left",
        wraplength=450
    )
    message_label.pack(pady=(0, 20), padx=25)

    # Button frame
    button_frame = ctk.CTkFrame(master=popup, fg_color="transparent")
    button_frame.pack(pady=(0, 25))

    def on_ok():
        unregister_popup(popup)
        popup.destroy()

    def on_dont_show_again():
        mark_notification_warning_dismissed()
        unregister_popup(popup)
        popup.destroy()

    ok_button = ctk.CTkButton(
        master=button_frame,
        text="OK",
        command=on_ok,
        width=120,
        height=35,
        corner_radius=10,
        fg_color="green",
        hover_color="#228B22",
        font=("Calibri", 14)
    )
    ok_button.pack(side="left", padx=10)

    dont_show_button = ctk.CTkButton(
        master=button_frame,
        text="Don't Show Again",
        command=on_dont_show_again,
        width=150,
        height=35,
        corner_radius=10,
        fg_color="gray",
        hover_color="#555555",
        font=("Calibri", 14)
    )
    dont_show_button.pack(side="left", padx=10)

    popup.deiconify()  # Show window now that icon is set
    popup.mainloop()


def check_and_warn_notifications():
    """
    Check if Windows notifications are disabled and show warning if needed.
    Only shows warning once unless user clicks OK (vs Don't Show Again).
    """
    if was_notification_warning_dismissed():
        log("Notification warning previously dismissed - skipping check", "INIT")
        return

    enabled, reason = are_windows_notifications_enabled()
    if not enabled:
        log(f"Windows notifications blocked (reason: {reason}) - showing warning", "INIT")
        show_notification_warning_popup(reason)
    else:
        log("Windows notifications are enabled", "INIT")


# =============================================================================
# Toast Notifications
# =============================================================================

def show_notification(message):
    """Display a Windows toast notification."""
    log(f"Showing notification: {message}", "NOTIFY")
    icon_path = os.path.abspath(TRAY_ICON_PATH)
    win11toast.notify(body=message, app_id='Vapor - Streamline Gaming', duration='short', icon=icon_path,
                      audio={'silent': 'true'})


def show_brief_summary(session_data):
    """Display a brief toast notification with session summary."""
    hours = session_data['hours']
    minutes = session_data['minutes']
    game_name = session_data['game_name']
    closed_apps_count = session_data['closed_apps_count']
    max_cpu_temp = session_data.get('max_cpu_temp')
    max_gpu_temp = session_data.get('max_gpu_temp')

    # Build playtime string
    if hours == 0:
        playtime_str = f"{minutes} minutes"
    elif hours == 1:
        playtime_str = f"{hours} hour and {minutes} minutes"
    else:
        playtime_str = f"{hours} hours and {minutes} minutes"

    # Build temperature string
    temp_parts = []
    if max_cpu_temp is not None:
        temp_parts.append(f"CPU: {max_cpu_temp}°C")
    if max_gpu_temp is not None:
        temp_parts.append(f"GPU: {max_gpu_temp}°C")

    if temp_parts:
        temp_str = f" Max temps: {', '.join(temp_parts)}."
        log(f"Max temperatures - {', '.join(temp_parts)}", "GAME")
    else:
        temp_str = ""

    message = f"You played {game_name} for {playtime_str}. Vapor closed {closed_apps_count} apps when you started.{temp_str}"
    show_notification(message)


# =============================================================================
# Session Summary Popup
# =============================================================================

def show_detailed_summary(session_data):
    """Display a detailed popup window with session statistics."""
    import customtkinter as ctk
    from PIL import Image

    app_id = session_data.get('app_id', 0)
    game_name = session_data['game_name']
    hours = session_data['hours']
    minutes = session_data['minutes']
    seconds = session_data['seconds']
    closed_apps_count = session_data['closed_apps_count']
    closed_apps_list = session_data.get('closed_apps_list', [])
    start_cpu_temp = session_data.get('start_cpu_temp')
    start_gpu_temp = session_data.get('start_gpu_temp')
    max_cpu_temp = session_data.get('max_cpu_temp')
    max_gpu_temp = session_data.get('max_gpu_temp')
    lifetime_max_cpu = session_data.get('lifetime_max_cpu')
    lifetime_max_gpu = session_data.get('lifetime_max_gpu')

    # Run popup in a separate thread to avoid blocking
    def show_popup():
        # Get pre-loaded game details (developer, metacritic, etc.)
        game_details = get_preloaded_game_details()

        popup = ctk.CTk()
        popup.withdraw()  # Hide while setting up to avoid icon flash
        popup.title("Vapor - Game Session Details")

        # Register popup for cleanup on quit
        register_popup(popup)

        def on_close():
            unregister_popup(popup)
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", on_close)

        # Window dimensions - similar to settings window, use screen-based height
        window_width = 550
        screen_height = popup.winfo_screenheight()
        # Use 70% of screen height, clamped between 600 and 850
        window_height = int(screen_height * 0.70)
        window_height = max(600, min(window_height, 850))

        popup.geometry(f"{window_width}x{window_height}")
        popup.resizable(False, False)

        # Center on screen
        screen_width = popup.winfo_screenwidth()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        popup.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Set window icon
        icon_path = os.path.join(base_dir, 'Images', 'exe_icon.ico')
        if os.path.exists(icon_path):
            try:
                popup.iconbitmap(icon_path)
            except Exception:
                pass

        # Bring window to front and give it focus
        popup.lift()
        popup.attributes('-topmost', True)
        popup.after(100, lambda: popup.attributes('-topmost', False))
        popup.focus_force()

        # IMPORTANT: Pack bottom bar FIRST so it reserves space at the bottom
        bottom_bar = ctk.CTkFrame(master=popup, fg_color="transparent")
        bottom_bar.pack(side="bottom", fill="x")

        # Separator above button bar
        sep_bottom = ctk.CTkFrame(master=bottom_bar, height=2, fg_color="gray50")
        sep_bottom.pack(fill="x", padx=40, pady=(10, 0))

        # Button container
        button_container = ctk.CTkFrame(master=bottom_bar, fg_color="transparent")
        button_container.pack(pady=15)

        ok_button = ctk.CTkButton(
            master=button_container,
            text="OK",
            command=on_close,
            width=150,
            height=35,
            corner_radius=10,
            fg_color="green",
            hover_color="#228B22",
            font=("Calibri", 15)
        )
        ok_button.pack()

        # Content frame (fills remaining space above bottom bar)
        content_frame = ctk.CTkFrame(master=popup, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=15, pady=(20, 10))

        # Title
        title_label = ctk.CTkLabel(
            master=content_frame,
            text="Game Session Details",
            font=("Calibri", 22, "bold")
        )
        title_label.pack(pady=(0, 5))

        # Game name
        game_label = ctk.CTkLabel(
            master=content_frame,
            text=game_name,
            font=("Calibri", 17),
            text_color="gray70"
        )
        game_label.pack(pady=(0, 10))

        # Game header image (try pre-loaded first, fall back to cache)
        pil_image = get_preloaded_header_image()
        if pil_image is None and app_id:
            # Fallback: load from cache if pre-loaded image not available
            cached_image_path = get_cached_header_image_path(app_id)
            if cached_image_path and os.path.exists(cached_image_path):
                try:
                    pil_image = Image.open(cached_image_path)
                    aspect_ratio = pil_image.height / pil_image.width
                    new_width = 400
                    new_height = int(new_width * aspect_ratio)
                    pil_image = pil_image.resize((new_width, new_height), Image.LANCZOS)
                except Exception as e:
                    log(f"Failed to load cached game header image: {e}", "NOTIFY")
                    pil_image = None

        if pil_image is not None:
            try:
                new_width = pil_image.width
                new_height = pil_image.height
                ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image,
                                         size=(new_width, new_height))
                image_label = ctk.CTkLabel(master=content_frame, image=ctk_image, text="")
                image_label.image = ctk_image  # Keep reference to prevent garbage collection
                image_label.pack(pady=(5, 10))
            except Exception as e:
                log(f"Failed to display game header image: {e}", "NOTIFY")

        # Separator
        sep1 = ctk.CTkFrame(master=content_frame, height=2, fg_color="gray50")
        sep1.pack(fill="x", padx=20, pady=5)

        # Stats frame using grid for alignment
        stats_frame = ctk.CTkFrame(master=content_frame, fg_color="transparent")
        stats_frame.pack(pady=10, padx=20, fill="x")

        # Time Played
        ctk.CTkLabel(master=stats_frame, text="Time Played:", font=("Calibri", 14, "bold"),
                     anchor="w").grid(row=0, column=0, sticky="w", pady=3)
        time_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
        ctk.CTkLabel(master=stats_frame, text=time_str, font=("Calibri", 14),
                     anchor="e").grid(row=0, column=1, sticky="e", pady=3)

        # Apps Closed
        ctk.CTkLabel(master=stats_frame, text="Apps Closed:", font=("Calibri", 14, "bold"),
                     anchor="w").grid(row=1, column=0, sticky="w", pady=3)
        ctk.CTkLabel(master=stats_frame, text=str(closed_apps_count), font=("Calibri", 14),
                     anchor="e").grid(row=1, column=1, sticky="e", pady=3)

        stats_frame.grid_columnconfigure(1, weight=1)

        # Show closed apps list if any
        if closed_apps_list:
            apps_list_frame = ctk.CTkFrame(master=content_frame, fg_color="transparent")
            apps_list_frame.pack(pady=(0, 5), padx=40, fill="x")

            # Format app names nicely (remove .exe extension)
            app_names = [app.replace('.exe', '').replace('.EXE', '') for app in closed_apps_list]
            apps_text = ", ".join(app_names[:8])  # Limit to first 8 apps
            if len(app_names) > 8:
                apps_text += f" (+{len(app_names) - 8} more)"

            apps_list_label = ctk.CTkLabel(
                master=apps_list_frame,
                text=apps_text,
                font=("Calibri", 12),
                text_color="gray60",
                wraplength=400
            )
            apps_list_label.pack(anchor="w")

        # Game Info section (from Steam Store API)
        if game_details:
            # Separator before game info
            sep_info = ctk.CTkFrame(master=content_frame, height=2, fg_color="gray50")
            sep_info.pack(fill="x", padx=20, pady=5)

            info_frame = ctk.CTkFrame(master=content_frame, fg_color="transparent")
            info_frame.pack(pady=5, padx=20, fill="x")

            info_row = 0

            # Developer
            developers = game_details.get('developers', [])
            if developers:
                ctk.CTkLabel(master=info_frame, text="Developer:", font=("Calibri", 14, "bold"),
                             anchor="w").grid(row=info_row, column=0, sticky="w", pady=2)
                ctk.CTkLabel(master=info_frame, text=", ".join(developers[:2]), font=("Calibri", 14),
                             anchor="e").grid(row=info_row, column=1, sticky="e", pady=2)
                info_row += 1

            # Publisher (only if different from developer)
            publishers = game_details.get('publishers', [])
            if publishers and publishers != developers:
                ctk.CTkLabel(master=info_frame, text="Publisher:", font=("Calibri", 14, "bold"),
                             anchor="w").grid(row=info_row, column=0, sticky="w", pady=2)
                ctk.CTkLabel(master=info_frame, text=", ".join(publishers[:2]), font=("Calibri", 14),
                             anchor="e").grid(row=info_row, column=1, sticky="e", pady=2)
                info_row += 1

            # Release Date
            release_date = game_details.get('release_date')
            if release_date and release_date != 'Unknown':
                ctk.CTkLabel(master=info_frame, text="Released:", font=("Calibri", 14, "bold"),
                             anchor="w").grid(row=info_row, column=0, sticky="w", pady=2)
                ctk.CTkLabel(master=info_frame, text=release_date, font=("Calibri", 14),
                             anchor="e").grid(row=info_row, column=1, sticky="e", pady=2)
                info_row += 1

            # Metacritic Score
            metacritic_score = game_details.get('metacritic_score')
            if metacritic_score:
                ctk.CTkLabel(master=info_frame, text="Metacritic:", font=("Calibri", 14, "bold"),
                             anchor="w").grid(row=info_row, column=0, sticky="w", pady=2)
                # Color code the score
                if metacritic_score >= 75:
                    score_color = "#66CC33"  # Green
                elif metacritic_score >= 50:
                    score_color = "#FFCC33"  # Yellow
                else:
                    score_color = "#FF0000"  # Red
                ctk.CTkLabel(master=info_frame, text=str(metacritic_score), font=("Calibri", 14, "bold"),
                             text_color=score_color, anchor="e").grid(row=info_row, column=1, sticky="e", pady=2)
                info_row += 1

            info_frame.grid_columnconfigure(1, weight=1)

        # Separator
        sep2 = ctk.CTkFrame(master=content_frame, height=2, fg_color="gray50")
        sep2.pack(fill="x", padx=20, pady=5)

        # Temperature section
        temp_title = ctk.CTkLabel(
            master=content_frame,
            text="Temperatures",
            font=("Calibri", 15, "bold")
        )
        temp_title.pack(pady=(5, 3))

        # Subtitle explaining lifetime max
        temp_subtitle = ctk.CTkLabel(
            master=content_frame,
            text=f"Lifetime Max = highest recorded temperature for {game_name}",
            font=("Calibri", 12),
            text_color="gray50"
        )
        temp_subtitle.pack(pady=(0, 8))

        temp_frame = ctk.CTkFrame(master=content_frame, fg_color="transparent")
        temp_frame.pack(pady=5, padx=20, fill="x")

        has_temps = False

        # Column headers - changed "Lifetime" to "Lifetime Max"
        ctk.CTkLabel(master=temp_frame, text="", font=("Calibri", 12),
                     anchor="w").grid(row=0, column=0, sticky="w", pady=3)
        ctk.CTkLabel(master=temp_frame, text="Start", font=("Calibri", 12, "bold"),
                     text_color="gray60").grid(row=0, column=1, sticky="e", pady=3, padx=(15, 0))
        ctk.CTkLabel(master=temp_frame, text="Session Max", font=("Calibri", 12, "bold"),
                     text_color="gray60").grid(row=0, column=2, sticky="e", pady=3, padx=(15, 0))
        ctk.CTkLabel(master=temp_frame, text="Lifetime Max", font=("Calibri", 12, "bold"),
                     text_color="#FFD700").grid(row=0, column=3, sticky="e", pady=3, padx=(15, 0))

        # CPU temps
        if start_cpu_temp is not None or max_cpu_temp is not None or lifetime_max_cpu is not None:
            has_temps = True
            ctk.CTkLabel(master=temp_frame, text="CPU:", font=("Calibri", 14, "bold"),
                         anchor="w").grid(row=1, column=0, sticky="w", pady=3)

            start_text = f"{start_cpu_temp}°C" if start_cpu_temp is not None else "N/A"
            max_text = f"{max_cpu_temp}°C" if max_cpu_temp is not None else "N/A"
            lifetime_text = f"{lifetime_max_cpu}°C" if lifetime_max_cpu is not None else "N/A"

            ctk.CTkLabel(master=temp_frame, text=start_text,
                         font=("Calibri", 13)).grid(row=1, column=1, sticky="e", pady=3, padx=(15, 0))
            ctk.CTkLabel(master=temp_frame, text=max_text,
                         font=("Calibri", 13)).grid(row=1, column=2, sticky="e", pady=3, padx=(15, 0))
            ctk.CTkLabel(master=temp_frame, text=lifetime_text,
                         font=("Calibri", 13), text_color="#FFD700").grid(row=1, column=3, sticky="e", pady=3, padx=(15, 0))

        # GPU temps
        if start_gpu_temp is not None or max_gpu_temp is not None or lifetime_max_gpu is not None:
            has_temps = True
            row = 2 if (start_cpu_temp is not None or max_cpu_temp is not None or lifetime_max_cpu is not None) else 1
            ctk.CTkLabel(master=temp_frame, text="GPU:", font=("Calibri", 14, "bold"),
                         anchor="w").grid(row=row, column=0, sticky="w", pady=3)

            start_text = f"{start_gpu_temp}°C" if start_gpu_temp is not None else "N/A"
            max_text = f"{max_gpu_temp}°C" if max_gpu_temp is not None else "N/A"
            lifetime_text = f"{lifetime_max_gpu}°C" if lifetime_max_gpu is not None else "N/A"

            ctk.CTkLabel(master=temp_frame, text=start_text,
                         font=("Calibri", 13)).grid(row=row, column=1, sticky="e", pady=3, padx=(15, 0))
            ctk.CTkLabel(master=temp_frame, text=max_text,
                         font=("Calibri", 13)).grid(row=row, column=2, sticky="e", pady=3, padx=(15, 0))
            ctk.CTkLabel(master=temp_frame, text=lifetime_text,
                         font=("Calibri", 13), text_color="#FFD700").grid(row=row, column=3, sticky="e", pady=3, padx=(15, 0))

        # No temps available message
        if not has_temps:
            ctk.CTkLabel(
                master=temp_frame,
                text="Temperature monitoring not enabled",
                font=("Calibri", 13),
                text_color="gray60"
            ).grid(row=0, column=0, columnspan=4, pady=10)

        temp_frame.grid_columnconfigure(3, weight=1)

        popup.deiconify()  # Show window now that icon is set
        popup.mainloop()

    # Run in a thread to avoid blocking the main monitoring loop
    threading.Thread(target=show_popup, daemon=True).start()
    log(f"Showing detailed summary for {game_name}", "NOTIFY")
