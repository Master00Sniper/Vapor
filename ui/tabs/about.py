# ui/tabs/about.py
# About tab for the Vapor Settings UI.

import os
import customtkinter as ctk
from PIL import Image

from utils import base_dir
from ui.constants import add_button_press_effect

try:
    from updater import CURRENT_VERSION
except ImportError:
    CURRENT_VERSION = "Unknown"


def build_about_tab(parent_frame):
    """
    Build the About tab content.

    Args:
        parent_frame: The tab frame to build content in

    Returns:
        dict: References to widgets that need to be accessed elsewhere
    """
    about_scroll_frame = ctk.CTkScrollableFrame(master=parent_frame, fg_color="transparent")
    about_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

    about_title = ctk.CTkLabel(master=about_scroll_frame, text="Vapor - Open Beta Release", font=("Calibri", 29, "bold"))
    about_title.pack(pady=(10, 5), anchor='center')

    version_label = ctk.CTkLabel(master=about_scroll_frame, text=f"Version {CURRENT_VERSION}", font=("Calibri", 15))
    version_label.pack(pady=(0, 15), anchor='center')

    description_text = """Vapor is a free, open source utility designed to enhance your gaming experience on Windows. It detects when you launch a Steam game and optimizes your system by closing distracting apps. When you exit, Vapor relaunches everything so you can pick up where you left off.

Features include app management, audio controls, power plan switching, Game Mode, temperature monitoring with alerts, and session summaries."""

    description_label = ctk.CTkLabel(master=about_scroll_frame, text=description_text, font=("Calibri", 14),
                                     wraplength=450, justify="center")
    description_label.pack(pady=10, anchor='center')

    separator1 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
    separator1.pack(fill="x", padx=40, pady=15)

    developer_title = ctk.CTkLabel(master=about_scroll_frame, text="Developed by", font=("Calibri", 13))
    developer_title.pack(pady=(5, 0), anchor='center')

    developer_name = ctk.CTkLabel(master=about_scroll_frame, text="Greg Morton (@Master00Sniper)",
                                  font=("Calibri", 17, "bold"))
    developer_name.pack(pady=(0, 10), anchor='center')

    bio_text = """I'm a passionate gamer, Sr. Systems Administrator, wine enthusiast, and proud small winery owner. Vapor was born from my frustration with notifications interrupting epic gaming moments. I hope it enhances your sessions as much as it has mine."""

    bio_label = ctk.CTkLabel(master=about_scroll_frame, text=bio_text, font=("Calibri", 14),
                             wraplength=450, justify="center")
    bio_label.pack(pady=10, anchor='center')

    separator2 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
    separator2.pack(fill="x", padx=40, pady=15)

    donate_title = ctk.CTkLabel(master=about_scroll_frame, text="Support Development", font=("Calibri", 15, "bold"))
    donate_title.pack(pady=(5, 5), anchor='center')

    donate_label = ctk.CTkLabel(master=about_scroll_frame,
                                text="If Vapor has improved your gaming experience,\nconsider supporting development!",
                                font=("Calibri", 14), justify="center")
    donate_label.pack(pady=(5, 10), anchor='center')

    # Ko-fi button with icon
    kofi_frame = ctk.CTkFrame(master=about_scroll_frame, fg_color="transparent")
    kofi_frame.pack(pady=(0, 5), anchor='center')

    kofi_icon_path = os.path.join(base_dir, 'Images', 'ko-fi_icon.png')
    if os.path.exists(kofi_icon_path):
        kofi_icon = ctk.CTkImage(light_image=Image.open(kofi_icon_path), size=(24, 24))
        kofi_icon_label = ctk.CTkLabel(master=kofi_frame, image=kofi_icon, text="")
        kofi_icon_label.pack(side="left", padx=(0, 8))

    kofi_button = ctk.CTkButton(master=kofi_frame, text="Support Vapor's Development on Ko-fi",
                                command=lambda: os.startfile("https://ko-fi.com/master00sniper"),
                                corner_radius=10, fg_color="#2563eb", hover_color="#1d4ed8",
                                text_color="white", width=250, font=("Calibri", 14, "bold"))
    kofi_button.pack(side="left")
    add_button_press_effect(kofi_button)

    separator3 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
    separator3.pack(fill="x", padx=40, pady=15)

    contact_title = ctk.CTkLabel(master=about_scroll_frame, text="Contact & Connect", font=("Calibri", 15, "bold"))
    contact_title.pack(pady=(5, 10), anchor='center')

    email_label = ctk.CTkLabel(master=about_scroll_frame, text="Email: greg@mortonapps.com", font=("Calibri", 14))
    email_label.pack(pady=2, anchor='center')

    x_link_frame = ctk.CTkFrame(master=about_scroll_frame, fg_color="transparent")
    x_link_frame.pack(pady=2, anchor='center')

    x_icon_label = ctk.CTkLabel(master=x_link_frame, text="X: ", font=("Calibri", 14))
    x_icon_label.pack(side="left")

    x_link_label = ctk.CTkLabel(master=x_link_frame, text="x.com/master00sniper", font=("Calibri", 14, "underline"),
                                text_color="#1DA1F2", cursor="hand2")
    x_link_label.pack(side="left")
    x_link_label.bind("<Button-1>", lambda e: os.startfile("https://x.com/master00sniper"))

    x_handle_label = ctk.CTkLabel(master=x_link_frame, text="  -  @Master00Sniper", font=("Calibri", 14))
    x_handle_label.pack(side="left")

    separator4 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
    separator4.pack(fill="x", padx=40, pady=15)

    supporters_title = ctk.CTkLabel(master=about_scroll_frame, text="Vapor Supporters", font=("Calibri", 15, "bold"))
    supporters_title.pack(pady=(5, 5), anchor='center')

    supporters_label = ctk.CTkLabel(master=about_scroll_frame,
                                    text="To become a Vapor Supporter, click the Ko-fi link above to become a member!",
                                    font=("Calibri", 14), justify="center")
    supporters_label.pack(pady=(5, 10), anchor='center')

    separator5 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
    separator5.pack(fill="x", padx=40, pady=15)

    credits_title = ctk.CTkLabel(master=about_scroll_frame, text="Credits", font=("Calibri", 15, "bold"))
    credits_title.pack(pady=(5, 5), anchor='center')

    credits_frame = ctk.CTkFrame(master=about_scroll_frame, fg_color="transparent")
    credits_frame.pack(pady=2, anchor='center')

    credits_text_label = ctk.CTkLabel(master=credits_frame, text="Icons by ", font=("Calibri", 14))
    credits_text_label.pack(side="left")

    icons8_link_label = ctk.CTkLabel(master=credits_frame, text="Icons8", font=("Calibri", 14, "underline"),
                                     text_color="#1DA1F2", cursor="hand2")
    icons8_link_label.pack(side="left")
    icons8_link_label.bind("<Button-1>", lambda e: os.startfile("https://icons8.com"))

    separator6 = ctk.CTkFrame(master=about_scroll_frame, height=2, fg_color="gray50")
    separator6.pack(fill="x", padx=40, pady=15)

    copyright_label = ctk.CTkLabel(master=about_scroll_frame,
                                   text=f"(c) 2024-2026 Greg Morton (@Master00Sniper)",
                                   font=("Calibri", 12))
    copyright_label.pack(pady=(5, 2), anchor='center')

    license_label = ctk.CTkLabel(master=about_scroll_frame,
                                 text="Licensed under the GNU General Public License v3.0",
                                 font=("Calibri", 12), text_color="gray60")
    license_label.pack(pady=(0, 5), anchor='center')

    disclaimer_text = """This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GPL v3 license for details."""

    disclaimer_label = ctk.CTkLabel(master=about_scroll_frame, text=disclaimer_text, font=("Calibri", 11),
                                    wraplength=450, justify="center", text_color="gray50")
    disclaimer_label.pack(pady=(5, 20), anchor='center')

    return {}
