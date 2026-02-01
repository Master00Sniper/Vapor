# platform/pawnio.py
# PawnIO driver management for CPU temperature monitoring

import os
import sys
import time
import ctypes
import subprocess

from utils.logging import log
from utils.constants import base_dir
from platform.windows import is_admin

# =============================================================================
# Cache Configuration
# =============================================================================

# Cache for PawnIO installation status (to avoid repeated slow winget calls)
_pawnio_installed_cache = None
_pawnio_cache_time = 0
PAWNIO_CACHE_DURATION = 60  # Cache for 60 seconds


# =============================================================================
# Winget Utilities
# =============================================================================

def is_winget_available():
    """
    Check if Windows Package Manager (winget) is available on this system.

    Returns:
        bool: True if winget is available and working
    """
    try:
        result = subprocess.run(
            ['winget', '--version'],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        available = result.returncode == 0
        if available:
            log(f"Winget available: {result.stdout.strip()}", "PAWNIO")
        return available
    except Exception as e:
        log(f"Winget check failed: {e}", "PAWNIO")
        return False


# =============================================================================
# PawnIO Detection
# =============================================================================

def is_pawnio_installed(use_cache=True):
    """
    Check if PawnIO driver is installed.

    Args:
        use_cache: If True, uses cached result if still valid (default: True)

    Returns:
        bool: True if PawnIO is installed
    """
    global _pawnio_installed_cache, _pawnio_cache_time

    # Return cached result if still valid
    if use_cache and _pawnio_installed_cache is not None:
        if time.time() - _pawnio_cache_time < PAWNIO_CACHE_DURATION:
            log(f"Using cached PawnIO status: {_pawnio_installed_cache}", "PAWNIO")
            return _pawnio_installed_cache

    log("Checking PawnIO installation via winget...", "PAWNIO")
    try:
        # Try both possible package IDs (namazso.PawnIO and PawnIO.PawnIO)
        result = subprocess.run(
            ['winget', 'list', '--id', 'namazso.PawnIO'],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        installed = 'PawnIO' in result.stdout

        if not installed:
            # Try alternate ID
            result = subprocess.run(
                ['winget', 'list', '--id', 'PawnIO.PawnIO'],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            installed = 'PawnIO' in result.stdout

        log(f"PawnIO installed: {installed}", "PAWNIO")

        # Update cache
        _pawnio_installed_cache = installed
        _pawnio_cache_time = time.time()

        return installed
    except Exception as e:
        log(f"PawnIO check error: {e}", "PAWNIO")
        return False


def clear_pawnio_cache():
    """Clear the PawnIO installation cache (call after installation attempts)."""
    global _pawnio_installed_cache, _pawnio_cache_time
    _pawnio_installed_cache = None
    _pawnio_cache_time = 0
    log("PawnIO cache cleared", "PAWNIO")


# =============================================================================
# PawnIO Installation
# =============================================================================

def get_pawnio_installer_path():
    """
    Get the path to the PawnIO installer PowerShell script.

    Returns:
        str: Full path to install_pawnio.ps1
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.join(sys._MEIPASS, 'install_pawnio.ps1')
    else:
        # Running as script - use base_dir
        return os.path.join(base_dir, 'install_pawnio.ps1')


def install_pawnio_silent():
    """
    Install PawnIO driver silently (requires existing admin privileges).

    Returns:
        bool: True if installation succeeded
    """
    script_path = get_pawnio_installer_path()

    if not os.path.exists(script_path):
        log(f"PawnIO installer not found: {script_path}", "PAWNIO")
        return False

    log("Installing PawnIO silently...", "PAWNIO")
    try:
        result = subprocess.run(
            [
                'powershell.exe',
                '-ExecutionPolicy', 'Bypass',
                '-WindowStyle', 'Hidden',
                '-File', script_path,
                '-Silent'
            ],
            capture_output=True,
            timeout=120,  # 2 minute timeout for winget install
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        success = result.returncode == 0
        if success:
            log("PawnIO installed successfully", "PAWNIO")
            clear_pawnio_cache()
        else:
            log(f"PawnIO installation failed: {result.stderr}", "PAWNIO")
        return success
    except subprocess.TimeoutExpired:
        log("PawnIO installation timed out", "PAWNIO")
        return False
    except Exception as e:
        log(f"PawnIO installation error: {e}", "PAWNIO")
        return False


def install_pawnio_with_elevation(progress_callback=None):
    """
    Install PawnIO driver with UAC elevation prompt if needed.

    Args:
        progress_callback: Optional function(message, progress_pct) to update UI

    Returns:
        bool: True if installation succeeded
    """
    log("Starting PawnIO installation with elevation...", "PAWNIO")
    log(f"Running as admin: {is_admin()}", "PAWNIO")

    # Check if winget is available
    if not is_winget_available():
        log("Winget not available - cannot install PawnIO", "PAWNIO")
        if progress_callback:
            progress_callback("Error: Windows Package Manager (winget) not found", 0)
        return False

    # Check if already installed
    if is_pawnio_installed(use_cache=False):
        log("PawnIO already installed", "PAWNIO")
        if progress_callback:
            progress_callback("PawnIO is already installed", 100)
        return True

    script_path = get_pawnio_installer_path()
    log(f"Using installer script: {script_path}", "PAWNIO")

    if not os.path.exists(script_path):
        log(f"Installer script not found: {script_path}", "PAWNIO")
        if progress_callback:
            progress_callback("Error: Installation script not found", 0)
        return False

    if progress_callback:
        progress_callback("Installing PawnIO driver...", 25)

    try:
        if is_admin():
            # Already admin - run directly
            log("Running installer directly (already admin)", "PAWNIO")
            success = install_pawnio_silent()
        else:
            # Need elevation - use ShellExecuteW with runas
            log("Requesting elevation for installation", "PAWNIO")
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                "powershell.exe",
                f'-ExecutionPolicy Bypass -WindowStyle Hidden -File "{script_path}" -Silent',
                os.path.dirname(script_path),
                0  # SW_HIDE
            )
            # ShellExecuteW returns > 32 on success
            if result > 32:
                # Wait a bit for installation to complete
                if progress_callback:
                    progress_callback("Installation in progress...", 50)
                time.sleep(5)
                clear_pawnio_cache()
                success = is_pawnio_installed(use_cache=False)
            else:
                log(f"ShellExecuteW failed: {result}", "PAWNIO")
                success = False

        if success:
            log("PawnIO installation completed successfully", "PAWNIO")
            if progress_callback:
                progress_callback("Installation complete!", 100)
        else:
            log("PawnIO installation failed", "PAWNIO")
            if progress_callback:
                progress_callback("Installation failed", 0)

        return success

    except Exception as e:
        log(f"PawnIO installation error: {e}", "PAWNIO")
        if progress_callback:
            progress_callback(f"Error: {e}", 0)
        return False


def run_pawnio_installer():
    """
    Run the PawnIO installer script with admin privileges (legacy function).

    This launches the installer asynchronously and returns immediately.
    For synchronous installation with feedback, use install_pawnio_with_elevation().

    Returns:
        bool: True if installer was launched successfully
    """
    script_path = get_pawnio_installer_path()

    if not os.path.exists(script_path):
        log(f"PawnIO installer not found: {script_path}", "PAWNIO")
        return False

    try:
        # Run PowerShell script elevated
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            "powershell.exe",
            f'-ExecutionPolicy Bypass -File "{script_path}"',
            os.path.dirname(script_path),
            1  # SW_SHOWNORMAL
        )

        if result > 32:
            log("PawnIO installer launched successfully", "PAWNIO")
            clear_pawnio_cache()
            return True
        else:
            log(f"Failed to launch PawnIO installer: {result}", "PAWNIO")
            return False
    except Exception as e:
        log(f"Error launching PawnIO installer: {e}", "PAWNIO")
        return False
