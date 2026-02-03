# Vapor

**Your Personal Gaming Assistant for Windows**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![GitHub release](https://img.shields.io/github/v/release/Master00Sniper/Vapor)](https://github.com/Master00Sniper/Vapor/releases)

Vapor is a lightweight Windows utility that watches for Steam game launches and applies your preferred settings automatically—so you can jump straight into the action.

No more alt-tabbing to close chat apps, adjusting volume sliders, or switching power plans. Just configure Vapor once with your preferences, and it handles the routine stuff while you focus on playing.

🌐 **Website:** [vapor.mortonapps.com](https://vapor.mortonapps.com)

## You're in Control

Vapor only does what you tell it to. Every feature is optional and configurable—it simply automates the clicks and toggles you'd normally do yourself. Think of it as a personal assistant that knows your pre-game ritual.

Worried about apps losing unsaved work? Vapor asks apps to close gracefully (just like clicking the X button), giving them time to save before your session starts. When you're done playing, it can relaunch everything right where you left off.

## Features

### Pause Distracting Apps
Temporarily close chat apps (Discord, WhatsApp, Telegram) and background programs (OneDrive, Wallpaper Engine) when gaming starts—then bring them back when you're done.

### Audio Adjustments
Set your preferred system and game volumes automatically. No more blasting menu music or straining to hear footsteps.

### Power Profile Switching
Activate high-performance mode during gameplay and switch back to balanced afterward.

### Temperature Monitoring
Keep an eye on CPU and GPU temps with optional alerts if things get too warm.

### Session Summaries
See a quick recap after each session—playtime, which apps were paused, and temperature stats.

### Hotkey Support
Press Ctrl+Alt+K anytime to manually trigger app management.

### Game Mode Toggle
Automatically enable Windows Game Mode when you play.

## Transparent & Lightweight

Vapor uses the same standard Windows features available to any app: reading Steam's public registry to detect games, managing processes like Task Manager does, and adjusting audio/power settings through normal Windows interfaces. It runs quietly in your system tray and checks for updates automatically.

No kernel drivers. No system modifications. No surprises.

## Requirements

- Windows 10 or 11
- Steam installed

## Installation

### Download (Recommended)
1. Download `Vapor.exe` from the [latest release](https://github.com/Master00Sniper/Vapor/releases/latest)
2. Move Vapor.exe to your preferred location
3. Double-click to start

### Run from Source
1. Clone the repository:
   ```bash
   git clone https://github.com/Master00Sniper/Vapor.git
   cd Vapor
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run:
   ```bash
   python steam_game_detector.py
   ```

### Build Executable
To build Vapor.exe yourself:
1. Install build dependencies:
   ```bash
   pip install nuitka ordered-set zstandard
   ```
2. Run the build script (requires Visual Studio Build Tools):
   ```powershell
   .\build_nuitka.ps1
   ```
3. Find the executable at `dist/Vapor.exe`

## Privacy

Vapor collects minimal anonymous usage statistics (app version, OS type, random installation ID) to help understand how many people use it. No personal data is ever collected. You can disable this in Settings > Preferences.

See our [Privacy Policy](https://vapor.mortonapps.com/policies.html) for details.

## Support

- ☕ [Support on Ko-fi](https://ko-fi.com/master00sniper)
- 🐛 [Report issues](https://github.com/Master00Sniper/Vapor/issues)

## License

This project is licensed under the GNU General Public License v3.0 - see [LICENSE](LICENSE) for details.
