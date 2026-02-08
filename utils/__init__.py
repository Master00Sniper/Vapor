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
    GAME_STARTED_SIGNAL_FILE,
)
from utils.logging import log
from utils.settings import (
    DEFAULT_SETTINGS,
    load_settings,
    save_settings,
    create_default_settings,
    get_setting,
    set_setting,
)
