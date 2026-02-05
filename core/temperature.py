# core/temperature.py
# Temperature monitoring functionality for Vapor application

import os
import sys
import json
import time
import threading
import subprocess

from utils import log, base_dir, appdata_dir, TRAY_ICON_PATH
from platform_utils import is_admin

# =============================================================================
# Hardware Library Initialization
# =============================================================================

# NVIDIA GPU temperature via nvidia-ml-py
try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False

# AMD GPU temperature via pyadl
try:
    from pyadl import ADLManager
    PYADL_AVAILABLE = True
except Exception:
    # pyadl raises ADLError if no AMD GPU/driver found, not just ImportError
    PYADL_AVAILABLE = False

# CPU temperature via WMI (requires LibreHardwareMonitor or OpenHardwareMonitor running)
WMI_AVAILABLE = False
_wmi_import_error = None
try:
    import wmi
    # Test that WMI actually works by creating an instance
    _test_wmi = wmi.WMI()
    del _test_wmi
    WMI_AVAILABLE = True
except Exception as e:
    # Catch all exceptions - in compiled builds, may fail with COM errors, not just ImportError
    _wmi_import_error = str(e)

# HardwareMonitor package (PyPI) - handles LibreHardwareMonitor + PawnIO driver
# Note: This may fail in compiled builds if DLLs aren't bundled, falls back to manual DLL loading
HWMON_AVAILABLE = False
HWMON_COMPUTER = None
CPU_TEMP_ERRORS_LOGGED = False  # Only log WMI/fallback errors once
_hwmon_import_error = None
try:
    from HardwareMonitor.Hardware import Computer, IVisitor, IComputer, IHardware, IParameter, ISensor
    from HardwareMonitor.Hardware import HardwareType, SensorType
    HWMON_AVAILABLE = True
except Exception as e:
    # Catches ImportError, FileNotFoundException, and any .NET exceptions
    _hwmon_import_error = str(e)

# Fallback: LibreHardwareMonitorLib via pythonnet (bundled DLL approach)
LHM_AVAILABLE = False
LHM_COMPUTER = None
_lhm_import_error = None
if not HWMON_AVAILABLE:
    try:
        import clr
        import System
        from System.Reflection import Assembly

        # Determine frozen base directory (Nuitka)
        def get_frozen_base():
            return os.path.dirname(sys.executable)

        # Determine lib folder path
        if getattr(sys, 'frozen', False):
            lib_dir = os.path.join(get_frozen_base(), 'lib')
        else:
            lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib')

        lhm_dll_path = os.path.join(lib_dir, 'LibreHardwareMonitorLib.dll')

        # Fallback to root directory for backwards compatibility
        if not os.path.exists(lhm_dll_path):
            if getattr(sys, 'frozen', False):
                frozen_base = get_frozen_base()
                lhm_dll_path = os.path.join(frozen_base, 'LibreHardwareMonitorLib.dll')
                lib_dir = frozen_base
            else:
                lhm_dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'LibreHardwareMonitorLib.dll')
                lib_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        if os.path.exists(lhm_dll_path):
            # Add lib directory to assembly search path for dependencies
            System.AppDomain.CurrentDomain.AppendPrivatePath(lib_dir)

            # Pre-load dependencies that LibreHardwareMonitorLib needs
            for dep_dll in ['System.Memory.dll', 'System.Buffers.dll', 'HidSharp.dll']:
                dep_path = os.path.join(lib_dir, dep_dll)
                if os.path.exists(dep_path):
                    try:
                        Assembly.LoadFrom(dep_path)
                    except:
                        pass

            clr.AddReference(lhm_dll_path)
            from LibreHardwareMonitor.Hardware import Computer, HardwareType, SensorType
            LHM_AVAILABLE = True
        else:
            _lhm_import_error = f"DLL not found at {lhm_dll_path}"
    except Exception as e:
        _lhm_import_error = str(e)


# Visitor class for HardwareMonitor package (only defined if package available)
HardwareUpdateVisitor = None
if HWMON_AVAILABLE:
    class HardwareUpdateVisitor(IVisitor):
        """Visitor to update all hardware sensors."""
        __namespace__ = "VaporMonitor"

        def VisitComputer(self, computer: IComputer):
            computer.Traverse(self)

        def VisitHardware(self, hardware: IHardware):
            hardware.Update()
            for subHardware in hardware.SubHardware:
                subHardware.Update()

        def VisitParameter(self, parameter: IParameter):
            pass

        def VisitSensor(self, sensor: ISensor):
            pass


# =============================================================================
# Temperature Reading Functions
# =============================================================================

def get_gpu_temperature():
    """
    Get current GPU temperature in Celsius.
    Tries multiple methods: NVIDIA pynvml, AMD pyadl, nvidia-smi CLI, and WMI fallbacks.
    Returns None if temperature cannot be read.
    """
    # Try NVIDIA GPU first (pynvml library)
    if NVML_AVAILABLE:
        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                # Get temperature of first GPU (primary gaming GPU)
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                pynvml.nvmlShutdown()
                return temp
        except Exception as e:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
            # Don't log - will try fallbacks

    # Try AMD GPU (pyadl library)
    if PYADL_AVAILABLE:
        try:
            devices = ADLManager.getInstance().getDevices()
            if devices:
                # Get temperature of first GPU
                temp = devices[0].getCurrentTemperature()
                if temp is not None:
                    return int(temp)
        except Exception:
            pass  # Don't log - will try fallbacks

    # Fallback: Try nvidia-smi command line (works even if pynvml fails)
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            temp = int(result.stdout.strip().split('\n')[0])
            if 0 < temp < 150:
                return temp
    except Exception:
        pass  # nvidia-smi not available or failed

    # Fallback: Try WMI with LibreHardwareMonitor/OpenHardwareMonitor for GPU
    if WMI_AVAILABLE:
        for namespace in ["root\\LibreHardwareMonitor", "root\\OpenHardwareMonitor"]:
            try:
                w = wmi.WMI(namespace=namespace)
                sensors = w.Sensor()
                for sensor in sensors:
                    if sensor.SensorType == "Temperature" and "GPU" in sensor.Name:
                        if sensor.Value and sensor.Value > 0:
                            return int(sensor.Value)
            except Exception:
                pass  # Namespace not available

    return None


def get_cpu_temperature():
    """
    Get current CPU temperature in Celsius.
    Iterates through all CPU cores and returns the hottest temperature found.
    Tries HardwareMonitor package, LibreHardwareMonitor (bundled), and WMI fallbacks.
    Returns None if temperature cannot be read.
    """
    global HWMON_COMPUTER, LHM_COMPUTER

    # Try HardwareMonitor package first (handles PawnIO driver automatically)
    if HWMON_AVAILABLE and is_admin():
        try:
            from HardwareMonitor.Hardware import Computer, HardwareType, SensorType

            if HWMON_COMPUTER is None:
                log("Initializing HardwareMonitor Computer object...", "TEMP")
                HWMON_COMPUTER = Computer()
                HWMON_COMPUTER.IsCpuEnabled = True
                HWMON_COMPUTER.Open()
                # Use visitor pattern to update all hardware
                HWMON_COMPUTER.Accept(HardwareUpdateVisitor())
                log("HardwareMonitor initialized successfully", "TEMP")

            # Update all hardware using visitor
            HWMON_COMPUTER.Accept(HardwareUpdateVisitor())

            # Find the hottest CPU temperature across all cores
            max_temp = None
            for hardware in HWMON_COMPUTER.Hardware:
                if hardware.HardwareType == HardwareType.Cpu:
                    # Check all temperature sensors
                    for sensor in hardware.Sensors:
                        if sensor.SensorType == SensorType.Temperature:
                            try:
                                value = sensor.Value
                                if value is not None and float(value) > 0:
                                    temp = int(float(value))
                                    if max_temp is None or temp > max_temp:
                                        max_temp = temp
                            except Exception:
                                pass
                    # Check subhardware
                    for subhardware in hardware.SubHardware:
                        for sensor in subhardware.Sensors:
                            if sensor.SensorType == SensorType.Temperature:
                                try:
                                    value = sensor.Value
                                    if value is not None and float(value) > 0:
                                        temp = int(float(value))
                                        if max_temp is None or temp > max_temp:
                                            max_temp = temp
                                except Exception:
                                    pass
            if max_temp is not None:
                return max_temp
        except Exception as e:
            log(f"HardwareMonitor read failed: {e}", "TEMP")

    # Fallback: Try bundled LibreHardwareMonitorLib (requires admin privileges)
    if LHM_AVAILABLE and is_admin():
        try:
            from LibreHardwareMonitor.Hardware import Computer, HardwareType, SensorType

            if LHM_COMPUTER is None:
                log("Initializing LibreHardwareMonitor Computer object...", "TEMP")
                LHM_COMPUTER = Computer()
                LHM_COMPUTER.IsCpuEnabled = True
                LHM_COMPUTER.Open()
                # Single update cycle with brief delay
                for hardware in LHM_COMPUTER.Hardware:
                    hardware.Update()
                    for subhardware in hardware.SubHardware:
                        subhardware.Update()
                time.sleep(0.2)
                log("LibreHardwareMonitor initialized successfully", "TEMP")

            # Update all hardware
            for hardware in LHM_COMPUTER.Hardware:
                hardware.Update()
                for subhardware in hardware.SubHardware:
                    subhardware.Update()

            # Find the hottest CPU temperature across all cores
            max_temp = None
            for hardware in LHM_COMPUTER.Hardware:
                if hardware.HardwareType == HardwareType.Cpu:
                    # Check all temperature sensors
                    for sensor in hardware.Sensors:
                        if sensor.SensorType == SensorType.Temperature:
                            # Try multiple ways to get the value (pythonnet nullable handling)
                            try:
                                value = sensor.Value
                                # Handle .NET nullable - try GetValueOrDefault if available
                                if hasattr(value, 'GetValueOrDefault'):
                                    value = value.GetValueOrDefault()
                                elif hasattr(value, 'Value'):
                                    value = value.Value
                                if value is not None and float(value) > 0:
                                    temp = int(float(value))
                                    if max_temp is None or temp > max_temp:
                                        max_temp = temp
                            except Exception:
                                pass
                    # Check subhardware
                    for subhardware in hardware.SubHardware:
                        for sensor in subhardware.Sensors:
                            if sensor.SensorType == SensorType.Temperature:
                                try:
                                    value = sensor.Value
                                    if hasattr(value, 'GetValueOrDefault'):
                                        value = value.GetValueOrDefault()
                                    elif hasattr(value, 'Value'):
                                        value = value.Value
                                    if value is not None and float(value) > 0:
                                        temp = int(float(value))
                                        if max_temp is None or temp > max_temp:
                                            max_temp = temp
                                except Exception:
                                    pass
            if max_temp is not None:
                return max_temp
        except Exception as e:
            log(f"LibreHardwareMonitorLib read failed: {e}", "TEMP")

    # Fallback: Try WMI with external LibreHardwareMonitor/OpenHardwareMonitor
    global CPU_TEMP_ERRORS_LOGGED
    if WMI_AVAILABLE:
        # Try LibreHardwareMonitor WMI - find hottest CPU temp
        try:
            w = wmi.WMI(namespace="root\\LibreHardwareMonitor")
            sensors = w.Sensor()
            max_temp = None
            for sensor in sensors:
                if sensor.SensorType == "Temperature" and "CPU" in sensor.Name:
                    if sensor.Value and sensor.Value > 0:
                        temp = int(sensor.Value)
                        if max_temp is None or temp > max_temp:
                            max_temp = temp
            if max_temp is not None:
                return max_temp
        except Exception:
            pass  # WMI namespace not available

        # Try OpenHardwareMonitor WMI - find hottest CPU temp
        try:
            w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            sensors = w.Sensor()
            max_temp = None
            for sensor in sensors:
                if sensor.SensorType == "Temperature" and "CPU" in sensor.Name:
                    if sensor.Value and sensor.Value > 0:
                        temp = int(sensor.Value)
                        if max_temp is None or temp > max_temp:
                            max_temp = temp
            if max_temp is not None:
                return max_temp
        except Exception:
            pass  # WMI namespace not available

        # Fallback: Try Windows native thermal zone (requires admin)
        if is_admin():
            try:
                w = wmi.WMI(namespace="root\\wmi")
                temps = w.MSAcpi_ThermalZoneTemperature()
                if temps:
                    # Convert from decikelvin to Celsius: (temp / 10) - 273.15
                    for temp in temps:
                        if hasattr(temp, 'CurrentTemperature') and temp.CurrentTemperature:
                            celsius = (temp.CurrentTemperature / 10.0) - 273.15
                            if 0 < celsius < 150:  # Sanity check for valid temp range
                                return int(celsius)
            except Exception:
                pass  # Thermal zone not available

    # Fallback: Try PowerShell Get-CimInstance for thermal zone
    if is_admin():
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 'Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature | '
                 'Select-Object -ExpandProperty CurrentTemperature | Select-Object -First 1'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                # Convert from decikelvin to Celsius
                decikelvin = float(result.stdout.strip())
                celsius = (decikelvin / 10.0) - 273.15
                if 0 < celsius < 150:
                    return int(celsius)
        except Exception:
            pass  # PowerShell method failed

    # Fallback: Try wmic command for thermal zone
    if is_admin():
        try:
            result = subprocess.run(
                ['wmic', '/namespace:\\\\root\\wmi', 'path', 'MSAcpi_ThermalZoneTemperature',
                 'get', 'CurrentTemperature', '/value'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and 'CurrentTemperature=' in result.stdout:
                # Parse "CurrentTemperature=XXXXX" format
                for line in result.stdout.split('\n'):
                    if 'CurrentTemperature=' in line:
                        decikelvin = float(line.split('=')[1].strip())
                        celsius = (decikelvin / 10.0) - 273.15
                        if 0 < celsius < 150:
                            return int(celsius)
        except Exception:
            pass  # wmic method failed

    # Log once that CPU temp is unavailable
    if not CPU_TEMP_ERRORS_LOGGED:
        log("CPU temperature monitoring unavailable on this system", "TEMP")
        CPU_TEMP_ERRORS_LOGGED = True

    return None


# =============================================================================
# Temperature Alert Function
# =============================================================================

def show_temperature_alert(message, is_critical=False):
    """Display a high-priority temperature alert notification that can bypass Do Not Disturb.

    Uses the 'urgent' scenario to ensure the notification appears even when
    Windows Focus Assist / Do Not Disturb is enabled during gameplay.

    Args:
        message: The alert message to display
        is_critical: If True, treated as critical alert (text differs); sound is the same
    """
    import win11toast

    log(f"Showing temperature alert (critical={is_critical}): {message}", "ALERT")
    icon_path = os.path.abspath(TRAY_ICON_PATH)

    # Both warning and critical use the same reminder sound
    audio = {'src': 'ms-winsoundevent:Notification.Reminder'}

    win11toast.notify(body=message, app_id='Vapor - Streamline Gaming', scenario='urgent', icon=icon_path,
                      audio=audio)


# =============================================================================
# Temperature Tracker Class
# =============================================================================

class TemperatureTracker:
    """
    Tracks CPU and GPU temperatures during a gaming session.
    Records starting temperatures and maximum temperatures reached.
    Supports temperature alerts when thresholds are exceeded (warning and critical levels).
    """

    def __init__(self):
        self.start_cpu_temp = None
        self.start_gpu_temp = None
        self.max_cpu_temp = None
        self.max_gpu_temp = None
        self.last_cpu_temp = None  # Most recent CPU temp reading
        self.last_gpu_temp = None  # Most recent GPU temp reading
        self._stop_event = None  # Global stop event (Vapor quitting)
        self._internal_stop = None  # Internal stop event (game ended)
        self._thread = None
        self._monitoring = False
        self._enable_cpu = False
        self._enable_gpu = True
        # Alert settings (warning and critical thresholds)
        self._enable_cpu_alert = False
        self._cpu_warning_threshold = 85
        self._cpu_critical_threshold = 95
        self._enable_gpu_alert = False
        self._gpu_warning_threshold = 80
        self._gpu_critical_threshold = 90
        # Track which alerts have been triggered this session
        self._cpu_warning_triggered = False
        self._cpu_critical_triggered = False
        self._gpu_warning_triggered = False
        self._gpu_critical_triggered = False
        self._game_name = None

    def start_monitoring(self, stop_event, enable_cpu=False, enable_gpu=True,
                         enable_cpu_alert=False, cpu_warning_threshold=85, cpu_critical_threshold=95,
                         enable_gpu_alert=False, gpu_warning_threshold=80, gpu_critical_threshold=90,
                         game_name=None):
        """Start temperature monitoring in a background thread."""
        if self._monitoring:
            return

        self.start_cpu_temp = None
        self.start_gpu_temp = None
        self.max_cpu_temp = None
        self.max_gpu_temp = None
        self.last_cpu_temp = None
        self.last_gpu_temp = None
        self._stop_event = stop_event
        self._internal_stop = threading.Event()  # Create fresh event for this session
        self._monitoring = True
        self._enable_cpu = enable_cpu
        self._enable_gpu = enable_gpu
        # Alert settings (warning and critical thresholds)
        self._enable_cpu_alert = enable_cpu_alert
        self._cpu_warning_threshold = cpu_warning_threshold
        self._cpu_critical_threshold = cpu_critical_threshold
        self._enable_gpu_alert = enable_gpu_alert
        self._gpu_warning_threshold = gpu_warning_threshold
        self._gpu_critical_threshold = gpu_critical_threshold
        # Reset alert triggers for new session
        self._cpu_warning_triggered = False
        self._cpu_critical_triggered = False
        self._gpu_warning_triggered = False
        self._gpu_critical_triggered = False
        self._game_name = game_name

        # Only start monitoring if at least one thermal type is enabled
        if not enable_cpu and not enable_gpu:
            log("Temperature monitoring disabled (both CPU and GPU disabled)", "TEMP")
            self._monitoring = False
            return

        # Capture starting temperatures immediately
        if enable_cpu:
            self.start_cpu_temp = get_cpu_temperature()
            self.max_cpu_temp = self.start_cpu_temp
            if self.start_cpu_temp is not None:
                log(f"Starting CPU temp: {self.start_cpu_temp}°C", "TEMP")

        if enable_gpu:
            self.start_gpu_temp = get_gpu_temperature()
            self.max_gpu_temp = self.start_gpu_temp
            if self.start_gpu_temp is not None:
                log(f"Starting GPU temp: {self.start_gpu_temp}°C", "TEMP")

        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        enabled_types = []
        if enable_cpu:
            enabled_types.append("CPU")
        if enable_gpu:
            enabled_types.append("GPU")
        log(f"Temperature monitoring started ({', '.join(enabled_types)})", "TEMP")

    def stop_monitoring(self):
        """Stop temperature monitoring and return temperature data."""
        self._monitoring = False
        # Signal internal stop event to wake up the monitoring thread immediately
        if self._internal_stop:
            self._internal_stop.set()
        if self._thread:
            self._thread.join(timeout=0.5)  # Should be nearly instant now
            self._thread = None

        # Use last recorded temperatures from monitoring loop (more accurate than fresh read after game closes)
        end_cpu_temp = self.last_cpu_temp
        end_gpu_temp = self.last_gpu_temp

        log(f"Temperature monitoring stopped. Start CPU: {self.start_cpu_temp}°C, End CPU: {end_cpu_temp}°C, "
            f"Start GPU: {self.start_gpu_temp}°C, End GPU: {end_gpu_temp}°C", "TEMP")
        return {
            'start_cpu': self.start_cpu_temp,
            'start_gpu': self.start_gpu_temp,
            'end_cpu': end_cpu_temp,
            'end_gpu': end_gpu_temp,
            'max_cpu': self.max_cpu_temp,
            'max_gpu': self.max_gpu_temp
        }

    def _play_critical_alert_sound(self):
        """Play the critical alert sound if available."""
        try:
            import winsound
            # Look for sound file in several locations
            sound_locations = [
                os.path.join(base_dir, 'sounds', 'critical_alert.wav'),
                os.path.join(os.path.dirname(base_dir), 'sounds', 'critical_alert.wav'),
                os.path.join(appdata_dir, 'sounds', 'critical_alert.wav')
            ]
            for sound_path in sound_locations:
                if os.path.exists(sound_path):
                    log(f"Playing critical alert sound: {sound_path}", "ALERT")
                    winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    return
            # Fallback to system beep if no custom sound found
            log("Critical alert sound file not found (sounds/critical_alert.wav), using system beep", "ALERT")
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception as e:
            log(f"Error playing critical alert sound: {e}", "ALERT")

    def _monitor_loop(self):
        """Background loop that polls temperatures every 10 seconds."""
        poll_interval = 10  # seconds

        while self._monitoring:
            # Get current temperatures (only if enabled)
            cpu_temp = get_cpu_temperature() if self._enable_cpu else None
            gpu_temp = get_gpu_temperature() if self._enable_gpu else None

            # Save last readings for use when monitoring stops
            if cpu_temp is not None:
                self.last_cpu_temp = cpu_temp
            if gpu_temp is not None:
                self.last_gpu_temp = gpu_temp

            # Update max values
            if cpu_temp is not None:
                if self.max_cpu_temp is None or cpu_temp > self.max_cpu_temp:
                    self.max_cpu_temp = cpu_temp
                    log(f"New max CPU temp: {cpu_temp}°C", "TEMP")

            if gpu_temp is not None:
                if self.max_gpu_temp is None or gpu_temp > self.max_gpu_temp:
                    self.max_gpu_temp = gpu_temp
                    log(f"New max GPU temp: {gpu_temp}°C", "TEMP")

            # Check CPU temperature alerts (warning and critical levels)
            if self._enable_cpu_alert and cpu_temp is not None:
                game_info = f" while playing {self._game_name}" if self._game_name else ""
                # Check critical first (higher priority)
                if not self._cpu_critical_triggered and cpu_temp >= self._cpu_critical_threshold:
                    self._cpu_critical_triggered = True
                    self._cpu_warning_triggered = True  # Also mark warning as triggered
                    log(f"CPU CRITICAL alert: {cpu_temp}°C exceeds critical threshold of {self._cpu_critical_threshold}°C", "ALERT")
                    show_temperature_alert(f"CRITICAL ALERT - CPU Temperature: {cpu_temp}°C{game_info}. "
                                           f"Critical threshold of {self._cpu_critical_threshold}°C exceeded!",
                                           is_critical=True)
                # Check warning level
                elif not self._cpu_warning_triggered and cpu_temp >= self._cpu_warning_threshold:
                    self._cpu_warning_triggered = True
                    log(f"CPU warning alert: {cpu_temp}°C exceeds warning threshold of {self._cpu_warning_threshold}°C", "ALERT")
                    show_temperature_alert(f"CPU Temperature Warning: {cpu_temp}°C{game_info}. "
                                           f"Warning threshold of {self._cpu_warning_threshold}°C exceeded.")

            # Check GPU temperature alerts (warning and critical levels)
            if self._enable_gpu_alert and gpu_temp is not None:
                game_info = f" while playing {self._game_name}" if self._game_name else ""
                # Check critical first (higher priority)
                if not self._gpu_critical_triggered and gpu_temp >= self._gpu_critical_threshold:
                    self._gpu_critical_triggered = True
                    self._gpu_warning_triggered = True  # Also mark warning as triggered
                    log(f"GPU CRITICAL alert: {gpu_temp}°C exceeds critical threshold of {self._gpu_critical_threshold}°C", "ALERT")
                    show_temperature_alert(f"CRITICAL ALERT - GPU Temperature: {gpu_temp}°C{game_info}. "
                                           f"Critical threshold of {self._gpu_critical_threshold}°C exceeded!",
                                           is_critical=True)
                # Check warning level
                elif not self._gpu_warning_triggered and gpu_temp >= self._gpu_warning_threshold:
                    self._gpu_warning_triggered = True
                    log(f"GPU warning alert: {gpu_temp}°C exceeds warning threshold of {self._gpu_warning_threshold}°C", "ALERT")
                    show_temperature_alert(f"GPU Temperature Warning: {gpu_temp}°C{game_info}. "
                                           f"Warning threshold of {self._gpu_warning_threshold}°C exceeded.")

            # Wait for next poll or stop event (internal event wakes immediately when game ends)
            if self._internal_stop:
                if self._internal_stop.wait(poll_interval):
                    break
            elif self._stop_event:
                if self._stop_event.wait(poll_interval):
                    break
            else:
                time.sleep(poll_interval)


# Global temperature tracker instance
temperature_tracker = TemperatureTracker()


# =============================================================================
# Temperature History Logging
# =============================================================================

# Directory for temperature history logs
TEMP_HISTORY_DIR = os.path.join(appdata_dir, 'temp_history')
os.makedirs(TEMP_HISTORY_DIR, exist_ok=True)


def get_temp_history_path(app_id):
    """Get the path to the temperature history file for a specific game."""
    return os.path.join(TEMP_HISTORY_DIR, f'{app_id}_temp_history.json')


def load_temp_history(app_id):
    """Load temperature history for a specific game. Returns dict with lifetime max temps."""
    history_path = get_temp_history_path(app_id)
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading temp history for app {app_id}: {e}", "TEMP")
    return {
        'app_id': app_id,
        'game_name': None,
        'lifetime_max_cpu': None,
        'lifetime_max_gpu': None,
        'sessions': []
    }


def save_temp_history(app_id, game_name, max_cpu, max_gpu):
    """Save temperature data for a game session and update lifetime maximums."""
    history = load_temp_history(app_id)

    # Update game name if we have it
    if game_name:
        history['game_name'] = game_name

    # Update lifetime maximums
    if max_cpu is not None:
        if history['lifetime_max_cpu'] is None or max_cpu > history['lifetime_max_cpu']:
            history['lifetime_max_cpu'] = max_cpu
            log(f"New lifetime max CPU temp for {game_name}: {max_cpu}°C", "TEMP")

    if max_gpu is not None:
        if history['lifetime_max_gpu'] is None or max_gpu > history['lifetime_max_gpu']:
            history['lifetime_max_gpu'] = max_gpu
            log(f"New lifetime max GPU temp for {game_name}: {max_gpu}°C", "TEMP")

    # Add session record
    session_record = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'max_cpu': max_cpu,
        'max_gpu': max_gpu
    }
    history['sessions'].append(session_record)

    # Keep only last 100 sessions to prevent file from growing too large
    if len(history['sessions']) > 100:
        history['sessions'] = history['sessions'][-100:]

    # Save to file
    history_path = get_temp_history_path(app_id)
    try:
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=2)
        log(f"Saved temp history for {game_name} (AppID: {app_id})", "TEMP")
    except Exception as e:
        log(f"Error saving temp history: {e}", "TEMP")

    return history


def get_lifetime_max_temps(app_id):
    """Get lifetime maximum temperatures for a specific game."""
    history = load_temp_history(app_id)
    return {
        'lifetime_max_cpu': history.get('lifetime_max_cpu'),
        'lifetime_max_gpu': history.get('lifetime_max_gpu')
    }
