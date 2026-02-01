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
    """Set volume for game processes (0-100) with retry logic."""
    if not game_pids:
        return
    log(f"Setting game volume to {level}% for {len(game_pids)} PID(s)...", "AUDIO")
    comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    try:
        level = max(0, min(100, level)) / 100.0
        max_attempts = 240  # 240 attempts x 0.5s = 120 seconds (2 min) max wait
        retry_delay = 0.5

        for attempt in range(max_attempts):
            sessions = AudioUtilities.GetAllSessions()
            set_count = 0
            for session in sessions:
                if session.ProcessId in game_pids:
                    if hasattr(session, 'SimpleAudioVolume'):
                        volume = session.SimpleAudioVolume
                        volume.SetMasterVolume(level, None)
                        set_count += 1

            if set_count > 0:
                log(f"Game volume set for {set_count} audio session(s)", "AUDIO")
                break
            else:
                if attempt < max_attempts - 1:
                    log(f"No audio sessions found (attempt {attempt + 1}/{max_attempts})...", "AUDIO")
                    time.sleep(retry_delay)
                else:
                    log("No audio sessions found after all attempts", "AUDIO")
    except Exception as e:
        log(f"Failed to set game volume: {e}", "ERROR")
    finally:
        comtypes.CoUninitialize()
