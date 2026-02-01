# core/__init__.py
# Core functionality modules for Vapor application

from core.temperature import (
    # Hardware availability flags
    NVML_AVAILABLE,
    PYADL_AVAILABLE,
    WMI_AVAILABLE,
    HWMON_AVAILABLE,
    LHM_AVAILABLE,
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
