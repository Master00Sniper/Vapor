# ui/tabs/__init__.py
# Tab modules for the Vapor Settings UI.

from ui.tabs.notifications import build_notifications_tab
from ui.tabs.resources import build_resources_tab
from ui.tabs.thermal import build_thermal_tab
from ui.tabs.preferences import build_preferences_tab
from ui.tabs.help import build_help_tab
from ui.tabs.about import build_about_tab

__all__ = [
    'build_notifications_tab',
    'build_resources_tab',
    'build_thermal_tab',
    'build_preferences_tab',
    'build_help_tab',
    'build_about_tab'
]
