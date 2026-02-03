# Vapor

**Your Personal Gaming Assistant for Windows**

Vapor is a lightweight Windows utility that watches for Steam game launches and applies your preferred settings automatically—so you can jump straight into the action.

No more alt-tabbing to close chat apps, adjusting volume sliders, or switching power plans. Just configure Vapor once with your preferences, and it handles the routine stuff while you focus on playing.

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
1. Download the latest release from the [Releases](https://github.com/Master00Sniper/Vapor/releases) page
2. Move Vapor.exe to your preferred location
3. Double-click to start

### Run from Source
1. Clone the repository:
   ```
   git clone https://github.com/Master00Sniper/Vapor.git
   ```
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run:
   ```
   python steam_game_detector.py
   ```

## License

This project is licensed under the GNU General Public License v3.0 - See [LICENSE](LICENSE) for details.
