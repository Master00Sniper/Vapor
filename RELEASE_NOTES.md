## What's New in v0.3.7

### New Features

- Live temperature display on Thermal tab shows current GPU and CPU temps, updated every second

### Improvements

- Faster startup when running as admin: UAC prompt now appears before splash screen instead of after
- Settings window automatically saves and closes when a game starts (reduces resource usage during gaming)
- Telemetry opt-out option is now hidden behind a Konami code easter egg (up up down down left right left right on Preferences tab)
- All notification and resource apps are now toggled off by default (users opt-in to which apps they want managed)
- Automatic cleanup of leftover temp folders from previous sessions
- Temperature alerts now require 3 consecutive readings above threshold before triggering (prevents false alarms from momentary spikes)

### Bug Fixes

- Fixed fuzzy taskbar icon by adding higher resolution sizes (up to 256x256) to the application icon
- Fixed CPU temperature monitoring not working in compiled builds
- Fixed popup dialogs briefly flashing before appearing
- Fixed CPU temperature popup dialogs cutting off text at the edges
- Fixed driver installation progress window briefly showing a white background
- Fixed telemetry confirmation popup buttons being slightly squished
- Fixed "Reset Settings" and "Delete All Data" buttons not restarting Vapor after reset
- Fixed WMI temperature fallback failing in compiled builds due to missing module path
- Fixed game session details and settings windows overflowing the screen at high DPI scaling (e.g., 125% zoom)
