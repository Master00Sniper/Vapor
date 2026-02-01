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


def set_game_volume(game_pids, level, game_folder=None):
    """Set volume for game processes (0-100) with retry logic.

    Games can have multiple audio sessions that appear at different times,
    so we continue monitoring for new sessions after finding the first one.

    If game_folder is provided, will dynamically discover new child processes
    that spawn during the monitoring period.
    """
    if not game_pids and not game_folder:
        return
    log(f"Setting game volume to {level}% for {len(game_pids)} PID(s)...", "AUDIO")
    comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    try:
        target_level = max(0, min(100, level)) / 100.0
        max_attempts = 240  # 240 attempts x 0.5s = 120 seconds (2 min) max wait
        retry_delay = 0.5

        # Track sessions we've already set using their stable Identifier
        set_session_ids = set()
        total_set_count = 0
        # After finding first session, continue checking for additional sessions
        stable_count = 0  # Count of consecutive polls with no new sessions
        stable_threshold = 6  # Stop after 6 consecutive polls (3 seconds) with no new sessions

        # Keep track of all known PIDs (will be updated if game_folder provided)
        known_pids = set(game_pids)

        for attempt in range(max_attempts):
            # Refresh PIDs to catch newly spawned child processes
            if game_folder and attempt % 2 == 0:  # Refresh every second (every 2 attempts)
                new_pids = _get_game_pids_from_folder(game_folder)
                if new_pids - known_pids:
                    log(f"Discovered {len(new_pids - known_pids)} new game process(es)", "AUDIO")
                    known_pids.update(new_pids)

            sessions = AudioUtilities.GetAllSessions()
            new_set_count = 0

            for session in sessions:
                if session.ProcessId in known_pids:
                    # Use the session's stable Identifier property
                    session_id = session.Identifier

                    if session_id and session_id not in set_session_ids:
                        if hasattr(session, 'SimpleAudioVolume') and session.SimpleAudioVolume:
                            try:
                                volume = session.SimpleAudioVolume
                                volume.SetMasterVolume(target_level, None)
                                set_session_ids.add(session_id)
                                new_set_count += 1
                                total_set_count += 1
                                log(f"Set volume for session {session.ProcessId} to {level}%", "AUDIO")
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
                    if attempt % 10 == 0:  # Log every 5 seconds instead of every attempt
                        log(f"No audio sessions found yet (attempt {attempt + 1}/{max_attempts})...", "AUDIO")
                else:
                    log("No audio sessions found after all attempts", "AUDIO")

            time.sleep(retry_delay)
    except Exception as e:
        log(f"Failed to set game volume: {e}", "ERROR")
    finally:
        comtypes.CoUninitialize()
