# Building Vapor with Nuitka

Nuitka compiles Python to C, then to a native executable. This results in fewer antivirus false positives compared to PyInstaller.

## Prerequisites

### 1. Install a C Compiler

**Option A: Visual Studio Build Tools (Recommended)**

1. Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Run the installer
3. Select "Desktop development with C++"
4. Install (requires ~6GB disk space)

**Option B: Let Nuitka download MinGW64 (Easier)**

If you don't have a C compiler, Nuitka will offer to download MinGW64 automatically on first run. Just say "yes" when prompted.

### 2. Install Nuitka

```bash
pip install nuitka ordered-set zstandard
```

### 3. Install Vapor Dependencies

```bash
pip install -r requirements.txt
```

## Building

### Simple Method

Run the batch file:
```bash
build_nuitka.bat
```

### Manual Method

```bash
python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=Images/exe_icon.ico ^
    --output-filename=Vapor.exe ^
    --output-dir=dist ^
    --enable-plugin=tk-inter ^
    --include-data-dir=Images=Images ^
    --include-data-dir=lib=lib ^
    --include-data-dir=sounds=sounds ^
    --include-data-files=vapor_settings_ui.py=vapor_settings_ui.py ^
    --include-data-files=updater.py=updater.py ^
    --include-data-files=install_pawnio.ps1=install_pawnio.ps1 ^
    steam_game_detector.py
```

## Build Times

| Build Type | Time |
|------------|------|
| First build | 15-30 minutes |
| Subsequent builds | 5-10 minutes |

Nuitka caches compiled modules, so subsequent builds are faster.

## Output

The compiled executable will be at: `dist/Vapor.exe`

## Troubleshooting

### "No C compiler found"
- Install Visual Studio Build Tools, or
- Let Nuitka download MinGW64 when prompted

### Module not found errors
Add the missing module with:
```bash
--include-module=module_name
```

### DLL not found at runtime
Add the DLL with:
```bash
--include-data-files=path/to/file.dll=file.dll
```

### Build runs out of memory
Try building without `--onefile` first to test, then add it back.

## Comparison: PyInstaller vs Nuitka

| Aspect | PyInstaller | Nuitka |
|--------|-------------|--------|
| Build time | ~2 minutes | ~15-30 minutes |
| Exe size | ~50 MB | ~30-40 MB |
| AV false positives | Common | Rare |
| Startup time | Slower | Faster |
| Runtime performance | Normal | 10-30% faster |
