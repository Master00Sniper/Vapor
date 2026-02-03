# Vapor - Claude Code Instructions

## Git Workflow

- **IMPORTANT**: Always use branch name `claude/dev-{sessionId}` for all work
  - Example: `claude/dev-OsNc6` where `OsNc6` is the current session ID
  - This keeps all Claude work on a consistent `dev` branch pattern
- All PRs should target `main` (or `dev` if it exists)
- Do not push directly to `main`
- Use descriptive commit messages

## Build & Run

- Install dependencies: `pip install -r requirements.txt`
- Run from source: `python steam_game_detector.py`
- Build executable: Run `build_nuitka.bat` (Windows only)

## Project Structure

- `steam_game_detector.py` - Main entry point
- `vapor_settings_ui.py` - Settings UI (CustomTkinter)
- `core/` - Core functionality (audio, Steam API, notifications)
- `utils/` - Utilities (logging, settings management)
- `platform_utils/` - Windows-specific utilities
- `Images/` - Application icons and assets
- `lib/` - External DLLs (LibreHardwareMonitor)

## Code Style

- This is a Windows-only Python application
- Uses CustomTkinter for the UI
- Follow existing code patterns and naming conventions
- Keep Windows API calls in `platform_utils/`

## Dependencies

- Python 3.x with Windows-specific packages (pywin32, pycaw, etc.)
- LibreHardwareMonitor for temperature monitoring
- CustomTkinter for modern UI elements
