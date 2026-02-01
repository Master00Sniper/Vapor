# platform_utils/__init__.py
# Platform-specific utilities for Vapor application

from platform_utils.windows import is_admin
from platform_utils.pawnio import (
    is_winget_available,
    is_pawnio_installed,
    clear_pawnio_cache,
    get_pawnio_installer_path,
    install_pawnio_silent,
    install_pawnio_with_elevation,
    run_pawnio_installer,
)
