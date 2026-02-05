# ui/constants.py
# Constants and built-in app definitions for the Settings UI.

import os
from utils import base_dir

# =============================================================================
# Button Press Effect
# =============================================================================

def add_button_press_effect(button, border_width=2, border_color="#1a1a1a"):
    """
    Add a visual press effect to a CTkButton using a dark border.

    On press: adds a dark border to create an "inset" look
    On release: removes the border

    Args:
        button: CTkButton instance
        border_width: Width of the pressed border (default 2px)
        border_color: Color of the pressed border (default dark gray)
    """
    # Store original border settings
    original_border_width = button.cget('border_width')
    original_border_color = button.cget('border_color')

    def on_press(event):
        try:
            button.configure(border_width=border_width, border_color=border_color)
        except Exception:
            pass

    def on_release(event):
        try:
            button.configure(border_width=original_border_width, border_color=original_border_color)
        except Exception:
            pass

    # Bind events - use add="+" to not override existing bindings
    button.bind("<Button-1>", on_press, add="+")
    button.bind("<ButtonRelease-1>", on_release, add="+")
    button.bind("<Leave>", on_release, add="+")


# Tab names - standardized to 16 characters for consistent tab widths
TAB_NOTIFICATIONS = " Notifications  "  # 13 chars centered in 16
TAB_RESOURCES     = "   Resources    "  # 9 chars centered in 16
TAB_THERMAL       = "    Thermal     "  # 7 chars centered in 16
TAB_PREFERENCES   = "  Preferences   "  # 11 chars centered in 16
TAB_HELP          = "      Help      "  # 4 chars centered in 16
TAB_ABOUT         = "     About      "  # 5 chars centered in 16

# Notification/messaging apps that can be closed during gaming
BUILT_IN_APPS = [
    {'display_name': 'WhatsApp', 'processes': ['WhatsApp.Root.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'whatsapp_icon.png')},
    {'display_name': 'Discord', 'processes': ['Discord.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'discord_icon.png')},
    {'display_name': 'Telegram', 'processes': ['Telegram.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'telegram_icon.png')},
    {'display_name': 'Microsoft Teams', 'processes': ['ms-teams.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'teams_icon.png')},
    {'display_name': 'Facebook Messenger', 'processes': ['Messenger.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'messenger_icon.png')},
    {'display_name': 'Slack', 'processes': ['slack.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'slack_icon.png')},
    {'display_name': 'Signal', 'processes': ['Signal.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'signal_icon.png')},
    {'display_name': 'WeChat', 'processes': ['WeChat.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'wechat_icon.png')}
]

# Resource-heavy apps organized by category
BUILT_IN_RESOURCE_APPS = [
    # Browsers (indices 0-3)
    {'display_name': 'Chrome', 'processes': ['chrome.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'chrome_icon.png')},
    {'display_name': 'Firefox', 'processes': ['firefox.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'firefox_icon.png')},
    {'display_name': 'Edge', 'processes': ['msedge.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'edge_icon.png')},
    {'display_name': 'Opera', 'processes': ['opera.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'opera_icon.png')},
    # Cloud/Media (indices 4-7)
    {'display_name': 'Spotify', 'processes': ['spotify.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'spotify_icon.png')},
    {'display_name': 'OneDrive', 'processes': ['OneDrive.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'onedrive_icon.png')},
    {'display_name': 'Google Drive', 'processes': ['GoogleDriveFS.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'googledrive_icon.png')},
    {'display_name': 'Dropbox', 'processes': ['Dropbox.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'dropbox_icon.png')},
    # Gaming Utilities (indices 8-11)
    {'display_name': 'Wallpaper Engine', 'processes': ['wallpaper64.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'wallpaperengine_icon.png')},
    {'display_name': 'iCUE', 'processes': ['iCUE.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'icue_icon.png')},
    {'display_name': 'Razer Synapse', 'processes': ['RazerCentralService.exe', 'Razer Synapse 3.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'razer_icon.png')},
    {'display_name': 'NZXT CAM', 'processes': ['NZXT CAM.exe'],
     'icon_path': os.path.join(base_dir, 'Images', 'nzxtcam_icon.png')}
]
