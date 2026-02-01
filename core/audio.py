# core/audio.py
# Audio control functionality for Vapor application

import os
import time

import comtypes
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from pycaw.constants import CLSID_MMDeviceEnumerator, EDataFlow, ERole
from pycaw.pycaw import IMMDeviceEnumerator
import psutil

from utils import log


# =============================================================================
# System Volume Control
# =============================================================================

def set_system_volume(level):
    """Set system master volume (0-100)."""
    log(f"Setting system volume to {level}%...", "AUDIO")
    comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    try:
        level = max(0, min(100, level)) / 100.0

        device_enumerator = comtypes.CoCreateInstance(
            CLSID_MMDeviceEnumerator,
            IMMDeviceEnumerator,
            comtypes.CLSCTX_ALL
        )

        default_device = device_enumerator.GetDefaultAudioEndpoint(
            EDataFlow.eRender.value,
            ERole.eMultimedia.value
        )

        interface = default_device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)

        volume.SetMasterVolumeLevelScalar(level, None)
        log(f"System volume set to {int(level * 100)}%", "AUDIO")
    except Exception as e:
        log(f"Failed to set system volume: {e}", "ERROR")
    finally:
        comtypes.CoUninitialize()


# =============================================================================
# Game Audio Control
# =============================================================================

def _get_game_pids_from_folder(game_folder):
    """Get all PIDs for processes running from the game folder (including children)."""
    pids = set()
    for proc in psutil.process_iter(['pid', 'exe']):
        try:
            exe = proc.info['exe']
            if exe and os.path.exists(exe):
                try:
                    if os.path.commonpath([exe, game_folder]) == game_folder:
                        pids.add(proc.pid)
                        # Also add all child processes
                        try:
                            for child in proc.children(recursive=True):
                                pids.add(child.pid)
                        except Exception:
                            pass
                except ValueError:
                    pass
        except Exception:
            pass
    return pids


def _get_sibling_pids(pid):
    """Get all sibling PIDs (processes with the same parent) for a given PID.

    Excludes Steam-related processes to avoid setting volume on Steam client
    components when Steam is the parent process of the game.
    """
    # Steam processes to exclude from sibling matching
    STEAM_PROCESS_NAMES = {
        'steam.exe', 'steamwebhelper.exe', 'steamservice.exe',
        'steamerrorreporter.exe', 'steamwebhelper', 'steam'
    }

    siblings = set()
    try:
        proc = psutil.Process(pid)
        parent = proc.parent()
        if parent:
            # Add all children of parent (siblings including self)
            for sibling in parent.children(recursive=False):
                # Skip Steam-related processes
                try:
                    sibling_name = sibling.name().lower()
                    if sibling_name in STEAM_PROCESS_NAMES:
                        continue
                except Exception:
                    pass

                siblings.add(sibling.pid)
                # Also add children of siblings (for Electron helper processes)
                try:
                    for child in sibling.children(recursive=True):
                        # Also skip Steam processes in children
                        try:
                            child_name = child.name().lower()
                            if child_name in STEAM_PROCESS_NAMES:
                                continue
                        except Exception:
                            pass
                        siblings.add(child.pid)
                except Exception:
                    pass
    except Exception:
        pass
    return siblings


def find_game_pids(game_folder):
    """Find process IDs for executables running from the game folder."""
    if not game_folder:
        return []
    log(f"Scanning for game processes in: {game_folder}", "PROCESS")

    for attempt in range(10):
        pids = _get_game_pids_from_folder(game_folder)
        if pids:
            log(f"Found {len(pids)} game process(es)", "PROCESS")
            return list(pids)
        log(f"No game processes found yet (attempt {attempt + 1}/10)...", "PROCESS")
        time.sleep(1)

    log("No game processes found", "PROCESS")
    return []


def set_game_volume(game_pids, level, game_folder=None, game_name=None):
    """Set volume for game processes (0-100) with retry logic.

    Games can have multiple audio sessions that appear at different times,
    so we continue monitoring for new sessions after finding the first one.

    If game_folder is provided, will dynamically discover new child processes
    that spawn during the monitoring period.

    If game_name is provided, will also match audio sessions by display name
    (useful for Electron apps where audio comes from helper processes).
    """
    if not game_pids and not game_folder:
        return
    log(f"Setting game volume to {level}% for {len(game_pids)} PID(s)...", "AUDIO")
    if game_name:
        log(f"Also matching audio sessions by name: {game_name}", "AUDIO")
    comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    try:
        target_level = max(0, min(100, level)) / 100.0
        max_attempts = 480  # 480 attempts x 0.25s = 120 seconds (2 min) max wait
        retry_delay = 0.25

        # Track sessions we've already set using their stable Identifier
        set_session_ids = set()
        total_set_count = 0
        # After finding first session, continue checking for additional sessions
        stable_count = 0  # Count of consecutive polls with no new sessions
        stable_threshold = 4  # Stop after 4 consecutive polls (1 second) with no new sessions

        # Keep track of all known PIDs (will be updated if game_folder provided)
        known_pids = set(game_pids)

        # Expand to include siblings of initial PIDs (helps with Electron apps)
        for pid in list(known_pids):
            sibling_pids = _get_sibling_pids(pid)
            known_pids.update(sibling_pids)
        if len(known_pids) > len(game_pids):
            log(f"Expanded to {len(known_pids)} PIDs (including siblings)", "AUDIO")

        # Normalize game name for matching
        game_name_lower = game_name.lower() if game_name else None

        for attempt in range(max_attempts):
            # Refresh PIDs to catch newly spawned child processes
            if game_folder and attempt % 4 == 0:  # Refresh every second (every 4 attempts)
                new_pids = _get_game_pids_from_folder(game_folder)
                if new_pids - known_pids:
                    log(f"Discovered {len(new_pids - known_pids)} new game process(es)", "AUDIO")
                    known_pids.update(new_pids)

            sessions = AudioUtilities.GetAllSessions()
            new_set_count = 0

            # Log all audio sessions on first attempt for debugging
            if attempt == 0:
                log(f"All audio sessions found:", "AUDIO")
                for s in sessions:
                    if s.ProcessId == 0:
                        continue
                    try:
                        pname = s.Process.name() if s.Process else "?"
                    except:
                        pname = "?"
                    log(f"  - PID {s.ProcessId}: {pname} (DisplayName: {s.DisplayName})", "AUDIO")

            for session in sessions:
                # Skip system sounds (ProcessId 0)
                if session.ProcessId == 0:
                    continue

                # Get process name for matching and logging
                process_name = None
                try:
                    if session.Process:
                        process_name = session.Process.name()
                except Exception:
                    pass

                # Match by PID
                is_match = session.ProcessId in known_pids

                # Also try to match by process name if game_name provided
                if not is_match and game_name_lower and process_name:
                    proc_name_lower = process_name.lower().replace('.exe', '')
                    # Match if process name contains game name or vice versa
                    if game_name_lower in proc_name_lower or proc_name_lower in game_name_lower:
                        is_match = True
                        log(f"Matched session by process name: {process_name} (PID {session.ProcessId})", "AUDIO")

                # Also try DisplayName if available
                if not is_match and game_name_lower and session.DisplayName:
                    display_lower = session.DisplayName.lower()
                    if game_name_lower in display_lower or display_lower in game_name_lower:
                        is_match = True
                        log(f"Matched session by display name: {session.DisplayName} (PID {session.ProcessId})", "AUDIO")

                if is_match:
                    # Always use ProcessId for tracking to ensure uniqueness
                    # (multiple processes can share the same session.Identifier)
                    session_id = f"pid_{session.ProcessId}"

                    if session_id not in set_session_ids:
                        if hasattr(session, 'SimpleAudioVolume') and session.SimpleAudioVolume:
                            try:
                                vol_interface = session.SimpleAudioVolume
                                vol_interface.SetMasterVolume(target_level, None)
                                set_session_ids.add(session_id)
                                new_set_count += 1
                                total_set_count += 1
                                display_info = f" [{process_name}]" if process_name else ""
                                log(f"Set volume for PID {session.ProcessId}{display_info} to {level}%", "AUDIO")

                                # Expand known_pids to include siblings of matched process
                                # This helps catch Electron helper processes with separate audio
                                sibling_pids = _get_sibling_pids(session.ProcessId)
                                if sibling_pids - known_pids:
                                    log(f"Adding {len(sibling_pids - known_pids)} sibling process(es) to search", "AUDIO")
                                    known_pids.update(sibling_pids)
                            except Exception as e:
                                log(f"Failed to set volume for session {session.ProcessId}: {e}", "AUDIO")

            if new_set_count > 0:
                log(f"Configured {new_set_count} new audio session(s) (total: {total_set_count})", "AUDIO")
                stable_count = 0  # Reset stability counter when we find new sessions
            elif total_set_count > 0:
                # We've set at least one session, now waiting to see if more appear
                stable_count += 1
                if stable_count >= stable_threshold:
                    log(f"Audio sessions stable - {total_set_count} total session(s) configured", "AUDIO")
                    break
            else:
                # No sessions found yet
                if attempt < max_attempts - 1:
                    if attempt % 20 == 0:  # Log every 5 seconds instead of every attempt
                        log(f"No audio sessions found yet (attempt {attempt + 1}/{max_attempts})...", "AUDIO")
                else:
                    log("No audio sessions found after all attempts", "AUDIO")

            time.sleep(retry_delay)
    except Exception as e:
        log(f"Failed to set game volume: {e}", "ERROR")
    finally:
        comtypes.CoUninitialize()
