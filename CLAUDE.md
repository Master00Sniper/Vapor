# Vapor - Claude Code Instructions

## Git Workflow

- **IMPORTANT**: Use the branch name specified in the system instructions for the session
  - The branch name is assigned by the system (e.g., `claude/session-setup-abc123`)
  - Do NOT create your own branch name - always use what's provided
- **IMPORTANT**: At the start of each new session, ensure you're working from the latest `main` branch
  - Run `git fetch origin main && git reset --hard origin/main` if your branch is behind
  - This ensures you don't overwrite changes that were merged since the branch was created
- All PRs should target `main` (or `dev` if it exists)
- Do not push directly to `main`
- Use descriptive commit messages

## Build & Run

- Install dependencies: `pip install -r requirements.txt`
- Run from source: `python steam_game_detector.py`
- Build executable: Run `build_nuitka.ps1` (Windows only)
- Create release: Run `git_update.ps1` (pushes tag, GitHub Actions builds & releases)

## Release Notes

- **IMPORTANT**: When making changes to the Vapor application, update `RELEASE_NOTES.md`
- **Only include changes that affect users**: New features, UI changes, bug fixes, settings changes
- **Do NOT include**: Website changes, build script changes, CI/CD changes, documentation, CLAUDE.md updates
- Group changes under headings as appropriate:
  - `New Features` - Entirely new functionality that didn't exist before
  - `Improvements` - Enhancements to existing features (e.g., better UI, faster performance, more options)
  - `Bug Fixes` - Fixes to broken functionality
- Example: Adding a pulsing effect to the existing Save button is an **Improvement**, not a New Feature
- Keep adding to the existing release notes while the version in `updater.py` stays the same
- When the version in `updater.py` is incremented, start fresh release notes for the new version
- The release notes will be automatically included in GitHub releases

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
