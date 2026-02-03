@echo off
REM Debug build - WITH CONSOLE to see errors
echo Building Vapor with console enabled for debugging...
echo.

python -m nuitka ^
    --standalone ^
    --onefile ^
    --msvc=latest ^
    --windows-icon-from-ico=Images/exe_icon.ico ^
    --output-filename=Vapor_Debug.exe ^
    --output-dir=dist ^
    --enable-plugin=tk-inter ^
    --include-data-dir=Images=Images ^
    --include-data-dir=lib=lib ^
    --include-data-dir=sounds=sounds ^
    --include-data-files=install_pawnio.ps1=install_pawnio.ps1 ^
    --include-module=vapor_settings_ui ^
    --include-module=updater ^
    --include-module=core ^
    --include-module=utils ^
    --include-module=platform_utils ^
    --include-module=win32gui ^
    --include-module=win32con ^
    --include-module=win32event ^
    --include-module=win32api ^
    --include-module=win32file ^
    --include-module=win32timezone ^
    --include-module=win32com ^
    --include-module=win32com.client ^
    --include-module=comtypes ^
    --include-module=comtypes.client ^
    --include-module=pycaw ^
    --include-module=pycaw.pycaw ^
    --include-module=customtkinter ^
    --include-module=PIL ^
    --include-module=PIL.Image ^
    --include-module=PIL.ImageTk ^
    --include-module=keyboard ^
    --include-module=pystray ^
    --include-module=watchdog ^
    --include-module=watchdog.observers ^
    --include-module=win11toast ^
    --include-module=psutil ^
    --include-module=requests ^
    --include-module=certifi ^
    --include-module=pynvml ^
    --include-module=pyadl ^
    --include-module=wmi ^
    --include-module=clr ^
    --include-module=pythonnet ^
    --include-module=HardwareMonitor ^
    --include-package-data=HardwareMonitor ^
    --include-package-data=customtkinter ^
    steam_game_detector.py

echo.
echo Debug build complete: dist\Vapor_Debug.exe
echo Run it from command prompt to see errors.
pause
