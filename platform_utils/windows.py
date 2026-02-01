# platform_utils/windows.py
# Windows-specific platform utilities for Vapor application

import ctypes


def is_admin():
    """
    Check if the current process has administrator privileges.

    Returns:
        bool: True if running with admin rights, False otherwise
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False
