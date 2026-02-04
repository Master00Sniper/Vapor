# vapor_settings_ui.py
# Settings interface for Vapor - allows users to configure app management, audio, power, and more.
# This is a thin wrapper that handles single instance check and path setup,
# then delegates to the modular UI code in ui/app.py.

import os
import sys

# =============================================================================
# Single Instance Check
# =============================================================================

import win32event
import win32api
import winerror

# Prevent multiple settings windows from opening
mutex = win32event.CreateMutex(None, True, "Vapor_Settings_SingleInstance_Mutex")
if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
    print("Settings window is already open. Exiting.")
    sys.exit(0)

# =============================================================================
# Path Configuration
# =============================================================================

if getattr(sys, 'frozen', False):
    if hasattr(sys, '_MEIPASS'):
        application_path = sys._MEIPASS
    else:
        application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(application_path)
sys.path.append(application_path)

# =============================================================================
# Launch Settings UI
# =============================================================================

from ui.app import run_settings_ui

if __name__ == "__main__":
    run_settings_ui()
