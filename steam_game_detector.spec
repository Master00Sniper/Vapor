# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all
from PyInstaller.building.datastruct import Tree

a = Analysis(
    ['steam_game_detector.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Add the UI script as data
a.datas += [('vapor_settings_ui.py', 'vapor_settings_ui.py', 'DATA')]

# Add all files from the 'Images' directory
a.datas += Tree('Images', prefix='Images')

# Collect everything for customtkinter (datas, binaries, hiddenimports)
datas, binaries, hiddenimports = collect_all('customtkinter')
a.datas += [(dest, src, 'DATA') for dest, src in datas]
a.binaries += [(dest, src, 'BINARY') for dest, src in binaries]
a.hiddenimports += hiddenimports

# Collect for Pillow (PIL)
datas, binaries, hiddenimports = collect_all('PIL')
a.datas += [(dest, src, 'DATA') for dest, src in datas]
a.binaries += [(dest, src, 'BINARY') for dest, src in binaries]
a.hiddenimports += hiddenimports

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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Hide console window since this is a tray app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Images/tray_icon.ico'
)