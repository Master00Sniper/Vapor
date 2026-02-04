# ui/restart.py
# Functions for restarting Vapor with optional elevation.

import os
import sys
import ctypes
import psutil

from utils import log as debug_log
from platform_utils import is_admin


def restart_vapor(main_pid, require_admin=False, delay_seconds=3):
    """
    Restart the main Vapor process.

    Args:
        main_pid: PID of the main Vapor process to terminate before restart
        require_admin: If True and not already admin, will request elevation.
                      If False, restarts without elevation prompt.
        delay_seconds: Seconds to wait before starting new process (default 3).
                      Use longer delays after driver installations.

    Uses a delayed start via PowerShell to avoid MEI folder cleanup errors.
    The caller is responsible for cleanly exiting after this function returns.
    """
    debug_log(f"Restarting Vapor (main_pid={main_pid}, require_admin={require_admin}, delay={delay_seconds}s)", "Restart")

    # Check if main_pid is our own process - if so, don't terminate it
    # We'll exit cleanly after launching the new process, which allows
    # PyInstaller to properly clean up the MEI folder
    current_pid = os.getpid()
    should_terminate_main = main_pid and main_pid != current_pid

    if should_terminate_main:
        try:
            debug_log(f"Terminating main process {main_pid}", "Restart")
            main_process = psutil.Process(main_pid)
            main_process.terminate()
            main_process.wait(timeout=5)  # Wait for process to terminate
            debug_log("Main process terminated", "Restart")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
            debug_log(f"Could not terminate main process: {e}", "Restart")
    else:
        debug_log(f"main_pid {main_pid} is current process {current_pid} - will exit cleanly after launch", "Restart")

    # Determine the executable path
    # Use VAPOR_EXE_PATH if available (passed from main process)
    vapor_exe_from_env = os.environ.get('VAPOR_EXE_PATH', '')
    executable = None
    args_part = ""
    working_dir = None

    if vapor_exe_from_env and os.path.exists(vapor_exe_from_env):
        # Use the path passed from the main Vapor process
        executable = vapor_exe_from_env
        working_dir = os.path.dirname(executable)
        debug_log(f"Using VAPOR_EXE_PATH: {executable}", "Restart")
    elif getattr(sys, 'frozen', False):
        # Fallback: try to find Vapor.exe
        # For Nuitka, sys.argv[0] should be the actual Vapor.exe path
        if not hasattr(sys, '_MEIPASS') and os.path.exists(sys.argv[0]):
            executable = sys.argv[0]
            working_dir = os.path.dirname(executable)
            debug_log(f"Using sys.argv[0] for Nuitka: {executable}", "Restart")
        else:
            # PyInstaller fallback: try common locations
            possible_paths = [
                os.path.join(os.path.dirname(os.path.dirname(sys.executable)), 'Vapor.exe'),
                os.path.join(os.getcwd(), 'Vapor.exe'),
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    executable = path
                    working_dir = os.path.dirname(executable)
                    break
        if not executable:
            debug_log("ERROR: Could not find Vapor.exe for restart", "Restart")
            return False
    else:
        # Running from Python - use pythonw.exe to avoid console window
        python_dir = os.path.dirname(sys.executable)
        pythonw_exe = os.path.join(python_dir, 'pythonw.exe')
        if os.path.exists(pythonw_exe):
            executable = pythonw_exe
        else:
            executable = sys.executable
        # For Python mode, use the actual source directory (not temp MEI folder)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level from ui/ to get to the main directory
        main_dir = os.path.dirname(script_dir)
        main_script = os.path.join(main_dir, 'steam_game_detector.py')
        args_part = f' -ArgumentList \\"{main_script}\\"'
        working_dir = main_dir

    debug_log(f"Executable: {executable}", "Restart")
    debug_log(f"Working dir: {working_dir}", "Restart")
    debug_log(f"Already admin: {is_admin()}", "Restart")

    # Log PyInstaller-related environment and paths for debugging
    debug_log(f"sys.executable: {sys.executable}", "Restart")
    debug_log(f"sys.frozen: {getattr(sys, 'frozen', False)}", "Restart")
    debug_log(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}", "Restart")
    debug_log(f"ENV _MEIPASS: {os.environ.get('_MEIPASS', 'N/A')}", "Restart")
    debug_log(f"ENV _MEIPASS2: {os.environ.get('_MEIPASS2', 'N/A')}", "Restart")
    debug_log(f"ENV VAPOR_EXE_PATH: {os.environ.get('VAPOR_EXE_PATH', 'N/A')}", "Restart")
    debug_log(f"TEMP dir: {os.environ.get('TEMP', 'N/A')}", "Restart")
    debug_log(f"Current PID: {os.getpid()}", "Restart")

    try:
        # Use PowerShell's Start-Process with -Verb RunAs to force UAC elevation
        # This creates a clean process through the Windows security subsystem
        # even when already running as admin (will show UAC prompt)
        ps_command = f'Start-Sleep -Seconds {delay_seconds}; Start-Process -FilePath \\"{executable}\\" -Verb RunAs{args_part}'
        debug_log(f"PowerShell command: {ps_command}", "Restart")
        debug_log(f"Using PowerShell Start-Process with -Verb RunAs (require_admin={require_admin}, is_admin={is_admin()})", "Restart")
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "open",  # Use "open" here since PowerShell's -Verb RunAs handles elevation
            "powershell.exe",
            f'-WindowStyle Hidden -Command "{ps_command}"',
            working_dir,
            0  # SW_HIDE
        )
        debug_log(f"ShellExecuteW result: {result} (success if > 32)", "Restart")
        return result > 32
    except Exception as e:
        debug_log(f"Restart failed: {e}", "Restart")
        return False


# Backwards-compatible alias
def restart_vapor_as_admin(main_pid):
    """Restart Vapor with admin privileges. Use restart_vapor() for more control."""
    return restart_vapor(main_pid, require_admin=True)
