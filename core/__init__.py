# core/__init__.py
# Core functionality modules for Vapor application

from core.temperature import (
    # Hardware availability flags
    NVML_AVAILABLE,
    PYADL_AVAILABLE,
    WMI_AVAILABLE,
    _wmi_import_error,
    HWMON_AVAILABLE,
    _hwmon_import_error,
    LHM_AVAILABLE,
    _lhm_import_error,
    # Temperature functions
    get_gpu_temperature,
    get_cpu_temperature,
    show_temperature_alert,
    # Temperature tracker
    TemperatureTracker,
    temperature_tracker,
    # Temperature history
    TEMP_HISTORY_DIR,
    get_temp_history_path,
    load_temp_history,
    save_temp_history,
    get_lifetime_max_temps,
)

from core.audio import (
    set_system_volume,
    find_game_pids,
    set_game_volume,
)

from core.steam_api import (
    # Registry access
    get_running_steam_app_id,
    # Steam Store API
    get_game_name,
    get_game_header_image,
    get_game_store_details,
    # Game details preloading
    preload_game_details,
    get_preloaded_game_details,
    # Header image caching
    HEADER_IMAGE_CACHE_DIR,
    get_cached_header_image_path,
    cache_game_header_image,
    preload_header_image,
    get_preloaded_header_image,
    # Session popup preparation
    warmup_customtkinter,
    prepare_session_popup,
)

from core.steam_filesystem import (
    DEFAULT_STEAM_PATH,
    get_steam_path,
    get_library_folders,
    get_game_folder,
)

from core.notifications import (
    # Popup management
    register_popup,
    unregister_popup,
    close_all_popups,
    # Windows notification check
    NOTIFICATION_WARNING_DISMISSED_FILE,
    are_windows_notifications_enabled,
    was_notification_warning_dismissed,
    mark_notification_warning_dismissed,
    show_notification_warning_popup,
    check_and_warn_notifications,
    # Toast notifications
    show_notification,
    show_brief_summary,
    show_detailed_summary,
)
