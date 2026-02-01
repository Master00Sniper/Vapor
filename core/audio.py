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

def find_game_pids(game_folder):
    """Find process IDs for executables running from the game folder."""
    if not game_folder:
        return []
    log(f"Scanning for game processes in: {game_folder}", "PROCESS")
    pids = []
    base_procs = []
    for attempt in range(10):
        for proc in psutil.process_iter(['pid', 'exe']):
            try:
                exe = proc.info['exe']
                if exe and os.path.exists(exe):
                    try:
                        if os.path.commonpath([exe, game_folder]) == game_folder:
                            base_procs.append(proc)
                    except ValueError:
                        pass
            except Exception:
                pass
        if base_procs:
            break
        log(f"No game processes found yet (attempt {attempt + 1}/10)...", "PROCESS")
        time.sleep(1)

    for proc in base_procs:
        pids.append(proc.pid)
        try:
            children = proc.children(recursive=True)
            for child in children:
                pids.append(child.pid)
        except Exception:
            pass

    pids = list(set(pids))
    if pids:
        log(f"Found {len(pids)} game process(es)", "PROCESS")
    else:
        log("No game processes found", "PROCESS")
    return pids


def set_game_volume(game_pids, level):
    """Set volume for game processes (0-100) with retry logic.

    Games can have multiple audio sessions that appear at different times,
    so we continue monitoring for new sessions after finding the first one.
    """
    if not game_pids:
        return
    log(f"Setting game volume to {level}% for {len(game_pids)} PID(s)...", "AUDIO")
    comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    try:
        level = max(0, min(100, level)) / 100.0
        max_attempts = 240  # 240 attempts x 0.5s = 120 seconds (2 min) max wait
        retry_delay = 0.5

        # Track sessions we've already set to avoid redundant operations
        set_session_ids = set()
        total_set_count = 0
        # After finding first session, continue checking for additional sessions
        stable_count = 0  # Count of consecutive polls with no new sessions
        stable_threshold = 6  # Stop after 6 consecutive polls (3 seconds) with no new sessions

        for attempt in range(max_attempts):
            sessions = AudioUtilities.GetAllSessions()
            new_set_count = 0

            for session in sessions:
                if session.ProcessId in game_pids:
                    # Create unique identifier for this session
                    session_id = (session.ProcessId, id(session._ctl))

                    if session_id not in set_session_ids:
                        if hasattr(session, 'SimpleAudioVolume'):
                            volume = session.SimpleAudioVolume
                            volume.SetMasterVolume(level, None)
                            set_session_ids.add(session_id)
                            new_set_count += 1
                            total_set_count += 1

            if new_set_count > 0:
                log(f"Game volume set for {new_set_count} new audio session(s) (total: {total_set_count})", "AUDIO")
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
