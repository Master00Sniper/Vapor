# utils/__init__.py
# Shared utilities for Vapor application

from utils.constants import (
    base_dir,
    appdata_dir,
    SETTINGS_FILE,
    DEBUG_LOG_FILE,
    MAX_LOG_SIZE,
    TRAY_ICON_PATH,
    PROTECTED_PROCESSES,
)
from utils.logging import log
