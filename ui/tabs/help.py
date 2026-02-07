# ui/tabs/help.py
# Help tab for the Vapor Settings UI.
# Includes how-to guides, troubleshooting, reset options, bug reporting, and uninstall.

import os
import shutil
import subprocess
import sys
import time
import tkinter as tk
import customtkinter as ctk
import psutil
import requests

from utils import log as debug_log, appdata_dir, SETTINGS_FILE
from platform_utils import is_admin, is_pawnio_installed
from ui.dialogs import show_vapor_dialog
import ui.state as state

try:
    from updater import CURRENT_VERSION
except ImportError:
    CURRENT_VERSION = "Unknown"


def build_help_tab(parent_frame):
    """
    Build the Help tab content.

    Args:
        parent_frame: The tab frame to build content in

    Returns:
        dict: References to widgets that need to be accessed elsewhere
    """
    help_scroll_frame = ctk.CTkScrollableFrame(master=parent_frame, fg_color="transparent")
    help_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

    help_title = ctk.CTkLabel(master=help_scroll_frame, text="Help, Support & Bug Reports", font=("Calibri", 25, "bold"))
    help_title.pack(pady=(10, 5), anchor='center')

    help_description = ctk.CTkLabel(master=help_scroll_frame,
                                    text="Get help with Vapor, troubleshoot issues, and submit bug reports.",
                                    font=("Calibri", 14), text_color="gray60")
    help_description.pack(pady=(0, 15), anchor='center')

    help_sep1 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
    help_sep1.pack(fill="x", padx=40, pady=10)

    # =========================================================================
    # How Vapor Works Section
    # =========================================================================
    how_title = ctk.CTkLabel(master=help_scroll_frame, text="How Vapor Works", font=("Calibri", 17, "bold"))
    how_title.pack(pady=(10, 10), anchor='center')

    how_text = """Vapor runs quietly in your system tray and monitors Steam for game launches. When you start
a Steam game, Vapor automatically:

  *  Closes notification apps (like Discord, Slack, Teams) to prevent interruptions
  *  Closes resource-heavy apps (like browsers, cloud sync) to free up RAM and CPU
  *  Adjusts your audio levels (if enabled)
  *  Switches your power plan (if enabled)
  *  Enables Windows Game Mode (if enabled)
  *  Monitors GPU and CPU temperatures with customizable alerts (if enabled)

When you exit your game, Vapor reverses these changes, relaunches your closed apps, and
displays a detailed session summary showing your playtime and performance stats."""

    how_label = ctk.CTkLabel(master=help_scroll_frame, text=how_text, font=("Calibri", 14),
                             wraplength=580, justify="left")
    how_label.pack(pady=10, padx=(40, 10), anchor='w')

    help_sep2 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
    help_sep2.pack(fill="x", padx=40, pady=15)

    # =========================================================================
    # Keyboard Shortcuts Section
    # =========================================================================
    shortcuts_title = ctk.CTkLabel(master=help_scroll_frame, text="Keyboard Shortcuts", font=("Calibri", 17, "bold"))
    shortcuts_title.pack(pady=(10, 10), anchor='center')

    shortcuts_text = """Ctrl + Alt + K  -  Manually close all selected notification and resource apps

This hotkey works independently of game detection. When enabled in the Notifications
or Resources tab, pressing this combination will immediately close all toggled apps
in that category. This is useful for quickly silencing distractions before a meeting,
stream, or any focus session - even when you're not gaming."""

    shortcuts_label = ctk.CTkLabel(master=help_scroll_frame, text=shortcuts_text, font=("Calibri", 14),
                                   wraplength=580, justify="left")
    shortcuts_label.pack(pady=10, padx=(40, 10), anchor='w')

    help_sep3 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
    help_sep3.pack(fill="x", padx=40, pady=15)

    # =========================================================================
    # Temperature Monitoring Section
    # =========================================================================
    thermal_help_title = ctk.CTkLabel(master=help_scroll_frame, text="Temperature Monitoring", font=("Calibri", 17, "bold"))
    thermal_help_title.pack(pady=(10, 10), anchor='center')

    thermal_help_text = """Vapor can monitor your GPU and CPU temperatures while gaming and alert you if
they reach dangerous levels:

  *  GPU Monitoring: Works out of the box - no additional setup required
  *  CPU Monitoring: Requires administrator privileges and the PawnIO driver
     (Vapor will automatically install this when you enable CPU monitoring)
  *  Temperature Alerts: Set custom warning and critical thresholds in the Thermal tab
     to receive notifications when your hardware gets too hot

Temperature data is also included in your post-game session summary, showing peak
temperatures reached during your gaming session."""

    thermal_help_label = ctk.CTkLabel(master=help_scroll_frame, text=thermal_help_text, font=("Calibri", 14),
                                       wraplength=580, justify="left")
    thermal_help_label.pack(pady=10, padx=(40, 10), anchor='w')

    help_sep3b = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
    help_sep3b.pack(fill="x", padx=40, pady=15)

    # =========================================================================
    # Troubleshooting Section
    # =========================================================================
    trouble_title = ctk.CTkLabel(master=help_scroll_frame, text="Troubleshooting", font=("Calibri", 17, "bold"))
    trouble_title.pack(pady=(10, 10), anchor='center')

    trouble_text = """If Vapor isn't working as expected, try these steps:

  *  Make sure Steam is running before launching games
  *  Check that the apps you want managed are toggled ON in the Notifications/Resources tabs
  *  Ensure Vapor is running (look for the icon in your system tray)
  *  Try clicking "Reset Settings File" or "Reset All Data" below to restore default settings

If issues persist, submit a bug report below with logs attached."""

    trouble_label = ctk.CTkLabel(master=help_scroll_frame, text=trouble_text, font=("Calibri", 14),
                                 wraplength=580, justify="left")
    trouble_label.pack(pady=10, padx=(40, 10), anchor='w')

    help_sep4 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
    help_sep4.pack(fill="x", padx=40, pady=15)

    # =========================================================================
    # Reset Settings Section
    # =========================================================================
    reset_title = ctk.CTkLabel(master=help_scroll_frame, text="Reset Settings", font=("Calibri", 17, "bold"))
    reset_title.pack(pady=(10, 5), anchor='center')

    reset_hint = ctk.CTkLabel(master=help_scroll_frame,
                              text="Use \"Reset Settings\" if Vapor is behaving unexpectedly or you want to start fresh.\n"
                                   "Use \"Reset All Data\" to completely clear all Vapor data including temperature\n"
                                   "history and cached game images. Both options will restart Vapor automatically.",
                              font=("Calibri", 13), text_color="gray60", justify="center")
    reset_hint.pack(pady=(0, 10), anchor='center')

    def reset_settings_and_restart():
        """Delete settings file and restart Vapor."""
        debug_log("Reset settings requested", "Reset")
        response = show_vapor_dialog(
            title="Reset Settings",
            message="This will delete all settings and restart Vapor.\n\n"
                    "Your settings will be reset to defaults.\n"
                    "Are you sure?",
            dialog_type="warning",
            buttons=[
                {"text": "Reset & Restart", "value": True, "color": "orange"},
                {"text": "Cancel", "value": False, "color": "gray"}
            ],
            parent=state.root
        )

        if response:
            debug_log("User confirmed reset settings", "Reset")
            try:
                if os.path.exists(SETTINGS_FILE):
                    os.remove(SETTINGS_FILE)
                    debug_log(f"Deleted settings file: {SETTINGS_FILE}", "Reset")
            except Exception as e:
                debug_log(f"Error deleting settings: {e}", "Reset")

            # Start a new instance of Vapor before shutting down
            debug_log("Restarting Vapor after settings reset", "Reset")
            try:
                executable = sys.executable
                debug_log(f"Starting new Vapor instance: {executable}", "Reset")
                subprocess.Popen([executable], creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
                debug_log("New Vapor instance started", "Reset")
            except Exception as e:
                debug_log(f"Failed to restart Vapor: {e}", "Reset")

            # Terminate the current instance
            if state.main_pid:
                try:
                    debug_log(f"Terminating main Vapor process (PID: {state.main_pid})", "Reset")
                    main_process = psutil.Process(state.main_pid)
                    main_process.terminate()
                    debug_log("Main process terminated", "Reset")
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    debug_log(f"Could not terminate: {e}", "Reset")
            state.root.destroy()
        else:
            debug_log("User cancelled reset settings", "Reset")

    def reset_all_data_and_restart():
        """Delete settings file, temperature data, and cached images, then restart Vapor."""
        debug_log("Reset all data requested", "Reset")
        response = show_vapor_dialog(
            title="Reset All Data",
            message="This will delete ALL Vapor data including:\n\n"
                    "• All settings\n"
                    "• All temperature history\n"
                    "• Lifetime max temperatures for all games\n"
                    "• All cached game images\n\n"
                    "This cannot be undone. Vapor will restart with\n"
                    "fresh defaults. Are you sure?",
            dialog_type="warning",
            buttons=[
                {"text": "Delete All & Restart", "value": True, "color": "red"},
                {"text": "Cancel", "value": False, "color": "gray"}
            ],
            parent=state.root
        )

        if response:
            debug_log("User confirmed reset all data", "Reset")
            try:
                if os.path.exists(SETTINGS_FILE):
                    os.remove(SETTINGS_FILE)
                    debug_log(f"Deleted settings file: {SETTINGS_FILE}", "Reset")
            except Exception as e:
                debug_log(f"Error deleting settings: {e}", "Reset")

            temp_history_dir = os.path.join(appdata_dir, 'temp_history')
            try:
                if os.path.exists(temp_history_dir):
                    shutil.rmtree(temp_history_dir)
                    debug_log(f"Deleted temp history folder: {temp_history_dir}", "Reset")
            except Exception as e:
                debug_log(f"Error deleting temp history: {e}", "Reset")

            images_dir = os.path.join(appdata_dir, 'images')
            try:
                if os.path.exists(images_dir):
                    shutil.rmtree(images_dir)
                    debug_log(f"Deleted images folder: {images_dir}", "Reset")
            except Exception as e:
                debug_log(f"Error deleting images: {e}", "Reset")

            # Start a new instance of Vapor before shutting down
            debug_log("Restarting Vapor after all data reset", "Reset")
            try:
                executable = sys.executable
                debug_log(f"Starting new Vapor instance: {executable}", "Reset")
                subprocess.Popen([executable], creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
                debug_log("New Vapor instance started", "Reset")
            except Exception as e:
                debug_log(f"Failed to restart Vapor: {e}", "Reset")

            # Terminate the current instance
            if state.main_pid:
                try:
                    debug_log(f"Terminating main Vapor process (PID: {state.main_pid})", "Reset")
                    main_process = psutil.Process(state.main_pid)
                    main_process.terminate()
                    debug_log("Main process terminated", "Reset")
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    debug_log(f"Could not terminate: {e}", "Reset")
            state.root.destroy()
        else:
            debug_log("User cancelled reset all data", "Reset")

    reset_buttons_frame = ctk.CTkFrame(master=help_scroll_frame, fg_color="transparent")
    reset_buttons_frame.pack(pady=(5, 20), anchor='center')

    rebuild_button = ctk.CTkButton(master=reset_buttons_frame, text="Reset Settings",
                                   command=reset_settings_and_restart, corner_radius=10,
                                   fg_color="#e67e22", hover_color="#d35400", text_color="white", width=160,
                                   font=("Calibri", 14))
    rebuild_button.pack(side='left', padx=5)

    reset_all_button = ctk.CTkButton(master=reset_buttons_frame, text="Delete All Data",
                                     command=reset_all_data_and_restart, corner_radius=10,
                                     fg_color="#c9302c", hover_color="#a02622", text_color="white", width=160,
                                     font=("Calibri", 14))
    reset_all_button.pack(side='left', padx=5)

    # =========================================================================
    # Bug Report Section
    # =========================================================================
    help_sep5 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
    help_sep5.pack(fill="x", padx=40, pady=15)

    bug_report_title = ctk.CTkLabel(master=help_scroll_frame, text="Report a Bug", font=("Calibri", 17, "bold"))
    bug_report_title.pack(pady=(10, 5), anchor='center')

    bug_report_hint = ctk.CTkLabel(master=help_scroll_frame,
                                   text="Found a bug? Let us know! Your report will be submitted to GitHub Issues.",
                                   font=("Calibri", 13), text_color="gray60")
    bug_report_hint.pack(pady=(0, 10), anchor='center')

    bug_title_label = ctk.CTkLabel(master=help_scroll_frame, text="Title (brief summary)", font=("Calibri", 14))
    bug_title_label.pack(pady=(5, 2), anchor='center')

    bug_title_entry = ctk.CTkEntry(master=help_scroll_frame, width=400, height=32, font=("Calibri", 13),
                                   placeholder_text="e.g., App crashes when starting a game")
    bug_title_entry.pack(pady=(0, 10), anchor='center')

    bug_desc_label = ctk.CTkLabel(master=help_scroll_frame,
                                  text="Description (steps to reproduce, expected vs actual behavior)",
                                  font=("Calibri", 14))
    bug_desc_label.pack(pady=(5, 2), anchor='center')

    bug_desc_textbox = ctk.CTkTextbox(master=help_scroll_frame, width=400, height=120, font=("Calibri", 13),
                                      wrap="word")
    bug_desc_textbox.pack(pady=(0, 10), anchor='center')

    checkbox_frame = ctk.CTkFrame(master=help_scroll_frame, fg_color="transparent")
    checkbox_frame.pack(pady=(5, 5), anchor='center')

    include_system_info_var = ctk.BooleanVar(value=True)
    system_info_checkbox = ctk.CTkCheckBox(master=checkbox_frame,
                                            text="Include system information (OS, Vapor version, Python version)",
                                            variable=include_system_info_var, font=("Calibri", 13))
    system_info_checkbox.pack(pady=(0, 8), anchor='w')

    include_logs_var = ctk.BooleanVar(value=True)
    logs_checkbox = ctk.CTkCheckBox(master=checkbox_frame, text="Include recent logs (last 250 lines)",
                                     variable=include_logs_var, font=("Calibri", 13))
    logs_checkbox.pack(pady=(0, 3), anchor='w')

    logs_disclaimer = ctk.CTkLabel(master=help_scroll_frame,
                                   text="Your Windows username is redacted from logs, but other folder names\n"
                                        "in paths where Vapor is running may be visible in the public report.",
                                   font=("Calibri", 12), text_color="gray50")
    logs_disclaimer.pack(pady=(0, 10), anchor='center')

    bug_status_label = ctk.CTkLabel(master=help_scroll_frame, text="", font=("Calibri", 13))
    bug_status_label.pack(pady=(0, 5), anchor='center')

    def get_system_info():
        """Collect system information for bug reports."""
        import platform
        info_lines = [
            f"- **Vapor Version**: {CURRENT_VERSION}",
            f"- **OS**: {platform.system()} {platform.release()} ({platform.version()})",
            f"- **Python**: {platform.python_version()}",
            f"- **Architecture**: {platform.machine()}",
        ]
        try:
            info_lines.append(f"- **Running as Admin**: {'Yes' if is_admin() else 'No'}")
        except:
            pass
        try:
            info_lines.append(f"- **PawnIO Driver**: {'Installed' if is_pawnio_installed() else 'Not installed'}")
        except:
            pass
        try:
            result = subprocess.run(['wmic', 'cpu', 'get', 'name'], capture_output=True, text=True, timeout=5)
            cpu_lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip() and line.strip() != 'Name']
            if cpu_lines:
                info_lines.append(f"- **CPU**: {cpu_lines[0]}")
        except:
            pass
        try:
            result = subprocess.run(['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                                    capture_output=True, text=True, timeout=5)
            gpu_lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip() and line.strip() != 'Name']
            if gpu_lines:
                info_lines.append(f"- **GPU**: {', '.join(gpu_lines)}")
        except:
            pass
        try:
            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024 ** 3)
            info_lines.append(f"- **RAM**: {total_gb:.1f} GB")
        except:
            pass
        return '\n'.join(info_lines)

    def sanitize_logs(log_content):
        """Redact Windows usernames from log content."""
        import re
        pattern = r'(C:[/\\][Uu]sers[/\\])([^/\\]+)([/\\])'
        sanitized = re.sub(pattern, r'\1[REDACTED]\3', log_content)
        return sanitized

    def get_recent_logs(num_lines=250):
        """Read the last N lines from the Vapor log file."""
        log_file = os.path.join(appdata_dir, 'vapor_logs.log')
        if not os.path.exists(log_file):
            return None
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            recent_lines = lines[-num_lines:] if len(lines) > num_lines else lines
            log_content = ''.join(recent_lines).strip()
            return sanitize_logs(log_content)
        except Exception as e:
            debug_log(f"Failed to read logs for bug report: {e}", "BugReport")
            return None

    submit_start_time = [0]

    def submit_bug_report():
        """Submit bug report to GitHub Issues via proxy."""
        submit_bug_button.configure(state="disabled", fg_color="gray50")
        submit_start_time[0] = time.time()

        def re_enable_button():
            submit_bug_button.configure(state="normal", fg_color="#2563eb")

        def schedule_re_enable():
            elapsed = time.time() - submit_start_time[0]
            remaining = max(0, 5.0 - elapsed)
            state.root.after(int(remaining * 1000), re_enable_button)

        title = bug_title_entry.get().strip()
        description = bug_desc_textbox.get("1.0", "end-1c").strip()

        if not title:
            bug_status_label.configure(text="Please enter a title for your bug report.", text_color="#ff6b6b")
            schedule_re_enable()
            return

        if not description:
            bug_status_label.configure(text="Please describe the bug.", text_color="#ff6b6b")
            schedule_re_enable()
            return

        body_parts = ["## Description", description]

        if include_system_info_var.get():
            body_parts.append("\n## System Information")
            body_parts.append(get_system_info())

        if include_logs_var.get():
            recent_logs = get_recent_logs(250)
            if recent_logs:
                body_parts.append("\n## Recent Logs")
                body_parts.append("<details>")
                body_parts.append("<summary>Click to expand logs (last 250 lines)</summary>")
                body_parts.append("")
                body_parts.append("```")
                body_parts.append(recent_logs)
                body_parts.append("```")
                body_parts.append("</details>")

        body_parts.append("\n---")
        body_parts.append("*Submitted via Vapor Settings UI*")

        issue_body = '\n'.join(body_parts)

        bug_status_label.configure(text="Submitting...", text_color="gray60")
        state.root.update()

        try:
            proxy_url = "https://vapor-proxy.mortonapps.com/repos/Master00Sniper/Vapor/issues"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Vapor-BugReport/1.0",
                "X-Vapor-Auth": "ombxslvdyyqvlkiiogwmjlkpocwqufaa",
                "Content-Type": "application/json"
            }
            payload = {"title": f"[Bug Report] {title}", "body": issue_body}
            response = requests.post(proxy_url, headers=headers, json=payload, timeout=15)

            if response.status_code == 201:
                issue_data = response.json()
                issue_number = issue_data.get('number', 'N/A')
                bug_status_label.configure(text=f"Bug report submitted successfully! (Issue #{issue_number})",
                                           text_color="#4ade80")
                bug_title_entry.delete(0, 'end')
                bug_desc_textbox.delete("1.0", "end")
                debug_log(f"Bug report submitted: Issue #{issue_number}", "BugReport")
            else:
                error_msg = f"Failed to submit (HTTP {response.status_code})"
                bug_status_label.configure(text=error_msg, text_color="#ff6b6b")
                debug_log(f"Bug report failed: {error_msg} - {response.text}", "BugReport")
        except requests.exceptions.Timeout:
            bug_status_label.configure(text="Request timed out. Please try again.", text_color="#ff6b6b")
            debug_log("Bug report failed: Timeout", "BugReport")
        except requests.exceptions.RequestException as e:
            bug_status_label.configure(text="Network error. Please check your connection.", text_color="#ff6b6b")
            debug_log(f"Bug report failed: {e}", "BugReport")
        except Exception as e:
            bug_status_label.configure(text="An error occurred. Please try again.", text_color="#ff6b6b")
            debug_log(f"Bug report failed: {e}", "BugReport")

        schedule_re_enable()

    submit_bug_button = ctk.CTkButton(master=help_scroll_frame, text="Submit Bug Report", command=submit_bug_report,
                                      corner_radius=10, fg_color="#2563eb", hover_color="#1d4ed8",
                                      text_color="white", width=180, font=("Calibri", 14))
    submit_bug_button.pack(pady=(5, 20), anchor='center')

    # =========================================================================
    # Uninstall Section
    # =========================================================================
    help_sep6 = ctk.CTkFrame(master=help_scroll_frame, height=2, fg_color="gray50")
    help_sep6.pack(fill="x", padx=40, pady=15)

    uninstall_title = ctk.CTkLabel(master=help_scroll_frame, text="Uninstall Vapor", font=("Calibri", 17, "bold"))
    uninstall_title.pack(pady=(10, 5), anchor='center')

    uninstall_hint = ctk.CTkLabel(master=help_scroll_frame,
                                  text="Completely remove Vapor and all associated data from your system.",
                                  font=("Calibri", 13), text_color="gray60")
    uninstall_hint.pack(pady=(0, 10), anchor='center')

    def uninstall_vapor():
        """Delete all Vapor data and close the application."""
        debug_log("Uninstall Vapor requested", "Uninstall")
        response = show_vapor_dialog(
            title="Uninstall Vapor",
            message="This will delete ALL Vapor data including:\n\n"
                    "• All settings\n"
                    "• All temperature history\n"
                    "• All cached game images\n"
                    "• All log files\n\n"
                    "After Vapor closes, you will need to manually delete\n"
                    "Vapor.exe to complete the uninstallation.\n\n"
                    "Are you sure you want to uninstall?",
            dialog_type="warning",
            buttons=[
                {"text": "Uninstall", "value": True, "color": "darkred"},
                {"text": "Cancel", "value": False, "color": "green"}
            ],
            parent=state.root
        )

        if response:
            debug_log("User confirmed uninstall", "Uninstall")
            try:
                if os.path.exists(appdata_dir):
                    shutil.rmtree(appdata_dir)
                    debug_log(f"Deleted Vapor data folder: {appdata_dir}", "Uninstall")
            except Exception as e:
                debug_log(f"Error deleting Vapor data folder: {e}", "Uninstall")

            show_vapor_dialog(
                title="Uninstall Complete",
                message="Vapor data has been deleted.\n\n"
                        "To complete the uninstallation, please delete\n"
                        "Vapor.exe from your system.",
                dialog_type="info",
                buttons=[{"text": "OK", "value": True, "color": "green"}],
                parent=state.root
            )

            debug_log("Stopping Vapor after uninstall", "Uninstall")
            if state.main_pid:
                try:
                    debug_log(f"Terminating main Vapor process (PID: {state.main_pid})", "Uninstall")
                    main_process = psutil.Process(state.main_pid)
                    main_process.terminate()
                    debug_log("Main process terminated", "Uninstall")
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    debug_log(f"Could not terminate: {e}", "Uninstall")
            state.root.destroy()
        else:
            debug_log("User cancelled uninstall", "Uninstall")

    uninstall_button = ctk.CTkButton(master=help_scroll_frame, text="Uninstall Vapor", command=uninstall_vapor,
                                     corner_radius=10, fg_color="#8b0000", hover_color="#5c0000",
                                     text_color="white", width=180, font=("Calibri", 14))
    uninstall_button.pack(pady=(5, 30), anchor='center')

    return {}
