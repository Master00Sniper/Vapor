# utils/constants.py
# Shared constants and paths for Vapor application

import os
import sys

# =============================================================================
# Path Configuration
# =============================================================================

# Base directory - handles both frozen (PyInstaller) and script execution
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# AppData directory for persistent user data
appdata_dir = os.path.join(os.getenv('APPDATA'), 'Vapor')
os.makedirs(appdata_dir, exist_ok=True)

# =============================================================================
# File Paths
# =============================================================================

SETTINGS_FILE = os.path.join(appdata_dir, 'vapor_settings.json')
DEBUG_LOG_FILE = os.path.join(appdata_dir, 'vapor_logs.log')
TRAY_ICON_PATH = os.path.join(base_dir, 'Images', 'tray_icon.png')

# =============================================================================
# Logging Configuration
# =============================================================================

# Maximum log file size (5 MB) - will be truncated when exceeded
MAX_LOG_SIZE = 5 * 1024 * 1024

# =============================================================================
# Protected Processes
# =============================================================================

# System processes that should never be terminated (safety protection)
PROTECTED_PROCESSES = {
    # Windows core
    'explorer.exe', 'svchost.exe', 'csrss.exe', 'wininit.exe', 'winlogon.exe',
    'services.exe', 'lsass.exe', 'smss.exe', 'dwm.exe', 'taskhostw.exe',
    'sihost.exe', 'fontdrvhost.exe', 'ctfmon.exe', 'conhost.exe', 'dllhost.exe',
    'runtimebroker.exe', 'searchhost.exe', 'startmenuexperiencehost.exe',
    'shellexperiencehost.exe', 'textinputhost.exe', 'applicationframehost.exe',
    'systemsettings.exe', 'securityhealthservice.exe', 'securityhealthsystray.exe',
    # System utilities
    'taskmgr.exe', 'cmd.exe', 'powershell.exe', 'regedit.exe', 'mmc.exe',
    # Windows Defender / Security
    'msmpeng.exe', 'mssense.exe', 'nissrv.exe', 'securityhealthhost.exe',
    # Critical services
    'spoolsv.exe', 'wuauserv.exe', 'audiodg.exe',
    # Vapor itself
    'vapor.exe',
}
