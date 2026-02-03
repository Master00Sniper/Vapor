## What's New in v0.3.4

### Improved Compatibility
- **Reduced Antivirus False Positives** - Switched build system from PyInstaller to Nuitka, which should significantly reduce Windows Defender and other antivirus false positive detections

### Improvements
- **Better Usage Tracking** - Added periodic telemetry heartbeat for more accurate daily active user counts (anonymous, no personal data collected)
- **Ko-fi Support** - Added donation link in the About page and website for those who want to support development

### Bug Fixes
- Fixed admin restart functionality when enabling CPU temperature monitoring
- Fixed settings UI launch issues
- Fixed auto-update process to work correctly with new build system
- Various internal stability improvements for long-running sessions
