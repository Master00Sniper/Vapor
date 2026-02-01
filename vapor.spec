# vapor.spec

# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from PyInstaller.building.datastruct import Tree

# Collect HardwareMonitor package data (includes LibreHardwareMonitorLib.dll and dependencies)
hardwaremonitor_datas = []
try:
    hardwaremonitor_datas += collect_data_files('HardwareMonitor')
except Exception:
    pass
try:
    hardwaremonitor_datas += collect_data_files('pylibrehardwaremonitorlib')
except Exception:
    pass

a = Analysis(
    ['steam_game_detector.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('vapor_settings_ui.py', '.'),
        ('updater.py', '.'),
        # PawnIO driver installer script for CPU temperature monitoring
        ('install_pawnio.ps1', '.'),
        # Fallback: Bundled LibreHardwareMonitor DLLs (if lib/ folder exists)
        # Download from: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases
    ] + hardwaremonitor_datas,
    hiddenimports=[
        # Windows API
        'win32gui', 'win32con', 'win32event', 'winerror', 'win32api', 'winreg',
        'win32file', 'win32timezone', 'win32com', 'win32com.client',
        'win32com.server', 'win32com.universal',
        # Audio
        'comtypes', 'comtypes.gen', 'comtypes.client', 'comtypes.server',
        'pycaw', 'pycaw.constants', 'pycaw.pycaw', 'pycaw.utils',
        # UI
        'customtkinter', 'tkinter', 'tkinter.filedialog',
        'PIL', 'PIL._tkinter_finder', 'PIL.Image', 'PIL.ImageTk',
        # Other
        'keyboard', 'pystray',
        'watchdog', 'watchdog.observers', 'watchdog.events',
        'win11toast', 'psutil', 'requests', 'certifi', 'urllib3',
        # Temperature monitoring
        'pynvml',  # NVIDIA GPU temps
        'pyadl',   # AMD GPU temps
        'wmi',     # WMI fallback
        'clr', 'pythonnet',  # LibreHardwareMonitor for CPU temps (fallback)
        'HardwareMonitor', 'HardwareMonitor.Hardware',  # CPU temps via PyPI package
    ] + collect_submodules('customtkinter') + collect_submodules('pycaw') + collect_submodules('comtypes') + collect_submodules('HardwareMonitor'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Add all files from the 'Images' directory
a.datas += Tree('Images', prefix='Images')

# Add lib/ folder with LibreHardwareMonitor DLLs (fallback for CPU temps)
import os
if os.path.exists('lib'):
    a.datas += Tree('lib', prefix='lib')

# Add sound files for critical temperature alerts
if os.path.exists('sounds'):
    a.datas += Tree('sounds', prefix='sounds')

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Vapor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,  # Use default _MEI folder in temp directory
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Images/exe_icon.ico',
    uac_admin=False
)