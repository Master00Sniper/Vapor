# core/steam_api.py
# Steam Store API integration and game data caching

import os
import threading
import winreg

import requests

from utils import appdata_dir, log


# =============================================================================
# Steam Registry Access
# =============================================================================

def get_running_steam_app_id():
    """Get the AppID of currently running Steam game (0 if none)."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        app_id, _ = winreg.QueryValueEx(key, "RunningAppID")
        winreg.CloseKey(key)
        return int(app_id)
    except:
        return 0


# =============================================================================
# Steam Store API
# =============================================================================

def get_game_name(app_id):
    """Fetch game name from Steam API for given AppID."""
    if app_id == 0:
        return "No game running"
    log(f"Fetching game name for AppID {app_id} from Steam API...", "STEAM")
    try:
        url = f"http://store.steampowered.com/api/appdetails?appids={app_id}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if response.status_code == 200 and str(app_id) in data and data[str(app_id)]["success"]:
            name = data[str(app_id)]["data"]["name"]
            log(f"Game name resolved: {name}", "STEAM")
            return name
    except Exception as e:
        log(f"Failed to fetch game name: {e}", "ERROR")
    return "Unknown"


def get_game_header_image(app_id):
    """Fetch game header image URL from Steam API for given AppID."""
    if app_id == 0:
        return None
    try:
        url = f"http://store.steampowered.com/api/appdetails?appids={app_id}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if response.status_code == 200 and str(app_id) in data and data[str(app_id)]["success"]:
            header_image = data[str(app_id)]["data"].get("header_image")
            if header_image:
                log(f"Got header image URL for AppID {app_id}", "STEAM")
                return header_image
    except Exception as e:
        log(f"Failed to fetch game header image: {e}", "ERROR")
    return None


def get_game_store_details(app_id):
    """Fetch game details from Steam Store API.

    Returns dict with: developers, publishers, release_date, recommendations, website
    """
    if app_id == 0:
        return None
    try:
        url = f"http://store.steampowered.com/api/appdetails?appids={app_id}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if response.status_code == 200 and str(app_id) in data and data[str(app_id)]["success"]:
            game_data = data[str(app_id)]["data"]

            details = {
                'developers': game_data.get('developers', []),
                'publishers': game_data.get('publishers', []),
                'release_date': game_data.get('release_date', {}).get('date', 'Unknown'),
                'recommendations': None,
                'website': game_data.get('website')  # Game's official website
            }

            # Recommendations data (total number of reviews)
            recommendations = game_data.get('recommendations')
            if recommendations:
                details['recommendations'] = recommendations.get('total')

            log(f"Got store details for AppID {app_id}", "STEAM")
            return details
    except Exception as e:
        log(f"Failed to fetch game store details: {e}", "ERROR")
    return None


def get_steamspy_data(app_id):
    """Fetch game data from SteamSpy API.

    Returns dict with: owners, ccu (peak concurrent yesterday), user_score (percentage)
    """
    if app_id == 0:
        return None
    try:
        url = f"https://steamspy.com/api.php?request=appdetails&appid={app_id}"
        response = requests.get(url, timeout=5)
        data = response.json()

        if response.status_code == 200 and data:
            spy_data = {
                'owners': data.get('owners'),  # e.g., "10,000,000 .. 20,000,000"
                'ccu': data.get('ccu'),  # Peak concurrent users yesterday
                'user_score': None
            }

            # Calculate user score from positive/negative reviews
            positive = data.get('positive', 0)
            negative = data.get('negative', 0)
            total = positive + negative
            if total > 0:
                spy_data['user_score'] = round((positive / total) * 100)

            log(f"Got SteamSpy data for AppID {app_id}", "STEAM")
            return spy_data
    except Exception as e:
        log(f"Failed to fetch SteamSpy data: {e}", "ERROR")
    return None


# =============================================================================
# Game Details Preloading
# =============================================================================

# Pre-loaded game details for instant popup display
_preloaded_game_details = None
_preloaded_game_details_lock = threading.Lock()


def preload_game_details(app_id):
    """Pre-load game details from Steam Store API and SteamSpy for instant display."""
    global _preloaded_game_details

    if app_id == 0:
        return

    details = get_game_store_details(app_id)
    if details:
        # Also fetch SteamSpy data and merge it
        steamspy = get_steamspy_data(app_id)
        if steamspy:
            details['steamspy_owners'] = steamspy.get('owners')
            details['steamspy_ccu'] = steamspy.get('ccu')
            details['steamspy_user_score'] = steamspy.get('user_score')

        with _preloaded_game_details_lock:
            _preloaded_game_details = details
        log(f"Pre-loaded game details for AppID {app_id}", "CACHE")


def get_preloaded_game_details():
    """Get the pre-loaded game details (or None if not available)."""
    global _preloaded_game_details
    with _preloaded_game_details_lock:
        details = _preloaded_game_details
        _preloaded_game_details = None  # Clear after use
        return details


# =============================================================================
# Header Image Caching
# =============================================================================

# Directory for cached game header images
HEADER_IMAGE_CACHE_DIR = os.path.join(appdata_dir, 'images')
os.makedirs(HEADER_IMAGE_CACHE_DIR, exist_ok=True)


def get_cached_header_image_path(app_id):
    """Get the path to the cached header image for a game."""
    return os.path.join(HEADER_IMAGE_CACHE_DIR, f"{app_id}.jpg")


def cache_game_header_image(app_id):
    """Download and cache the game header image for later use.

    Should be called when a game starts so the image is ready when the game ends.
    Runs in the background to avoid blocking.
    """
    if app_id == 0:
        return

    cache_path = get_cached_header_image_path(app_id)

    # Skip if already cached
    if os.path.exists(cache_path):
        log(f"Header image already cached for AppID {app_id}", "CACHE")
        return

    try:
        # Get the image URL from Steam API
        header_image_url = get_game_header_image(app_id)
        if not header_image_url:
            return

        # Download the image
        response = requests.get(header_image_url, timeout=10)
        if response.status_code == 200:
            # Save to cache
            with open(cache_path, 'wb') as f:
                f.write(response.content)
            log(f"Cached header image for AppID {app_id}", "CACHE")
    except Exception as e:
        log(f"Failed to cache header image for AppID {app_id}: {e}", "ERROR")


# Pre-loaded image for instant popup display
_preloaded_header_image = None
_preloaded_header_image_lock = threading.Lock()


def preload_header_image(app_id):
    """Pre-load and resize the header image into memory for instant display.

    Should be called after cache_game_header_image() completes.
    """
    global _preloaded_header_image
    from PIL import Image

    if app_id == 0:
        return

    cache_path = get_cached_header_image_path(app_id)
    if not os.path.exists(cache_path):
        return

    try:
        pil_image = Image.open(cache_path)
        # Pre-resize to the exact size needed for the popup
        aspect_ratio = pil_image.height / pil_image.width
        new_width = 400
        new_height = int(new_width * aspect_ratio)
        pil_image = pil_image.resize((new_width, new_height), Image.LANCZOS)

        with _preloaded_header_image_lock:
            _preloaded_header_image = pil_image
        log(f"Pre-loaded header image for AppID {app_id}", "CACHE")
    except Exception as e:
        log(f"Failed to pre-load header image: {e}", "ERROR")


def get_preloaded_header_image():
    """Get the pre-loaded header image (or None if not available)."""
    global _preloaded_header_image
    with _preloaded_header_image_lock:
        img = _preloaded_header_image
        _preloaded_header_image = None  # Clear after use
        return img


# =============================================================================
# Background Image Caching
# =============================================================================

def get_cached_background_image_path(app_id):
    """Get the path to the cached background image for a game."""
    return os.path.join(HEADER_IMAGE_CACHE_DIR, f"{app_id}_bg.jpg")


def cache_game_background_image(app_id):
    """Download and cache the game background image for later use.

    Tries Steam library hero image first, then falls back to page background.
    """
    if app_id == 0:
        return

    cache_path = get_cached_background_image_path(app_id)

    # Skip if already cached
    if os.path.exists(cache_path):
        log(f"Background image already cached for AppID {app_id}", "CACHE")
        return

    # Try library hero image first (better quality)
    urls_to_try = [
        f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/library_hero.jpg",
        f"https://steamcdn-a.akamaihd.net/steam/apps/{app_id}/page_bg_generated_v6b.jpg",
    ]

    for url in urls_to_try:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                with open(cache_path, 'wb') as f:
                    f.write(response.content)
                log(f"Cached background image for AppID {app_id}", "CACHE")
                return
        except Exception:
            continue

    log(f"No background image available for AppID {app_id}", "CACHE")


# Pre-loaded background image for instant popup display
_preloaded_background_image = None
_preloaded_background_image_lock = threading.Lock()


def preload_background_image(app_id):
    """Pre-load the background image into memory for instant display."""
    global _preloaded_background_image
    from PIL import Image

    if app_id == 0:
        return

    cache_path = get_cached_background_image_path(app_id)
    if not os.path.exists(cache_path):
        return

    try:
        pil_image = Image.open(cache_path)
        with _preloaded_background_image_lock:
            _preloaded_background_image = pil_image
        log(f"Pre-loaded background image for AppID {app_id}", "CACHE")
    except Exception as e:
        log(f"Failed to pre-load background image: {e}", "ERROR")


def get_preloaded_background_image():
    """Get the pre-loaded background image (or None if not available)."""
    global _preloaded_background_image
    with _preloaded_background_image_lock:
        img = _preloaded_background_image
        _preloaded_background_image = None  # Clear after use
        return img


# =============================================================================
# Session Popup Preparation
# =============================================================================

def warmup_customtkinter():
    """Pre-initialize CustomTkinter by creating and destroying a hidden window.

    This loads themes, fonts, etc. so the actual popup appears faster.
    """
    try:
        import customtkinter as ctk
        # Create a tiny hidden window to trigger CTk initialization
        root = ctk.CTk()
        root.withdraw()  # Hide immediately
        root.update()    # Process initialization
        root.destroy()   # Clean up
        log("CustomTkinter pre-initialized", "CACHE")
    except Exception as e:
        log(f"Failed to pre-initialize CustomTkinter: {e}", "ERROR")


def prepare_session_popup(app_id):
    """Background task to prepare everything needed for the session popup.

    Called when a game starts. Downloads/caches images, pre-loads them into memory,
    fetches game details from Steam and SteamSpy, and warms up CustomTkinter so the popup
    appears instantly when the game ends.
    """
    cache_game_header_image(app_id)
    cache_game_background_image(app_id)
    preload_header_image(app_id)
    preload_background_image(app_id)
    preload_game_details(app_id)
    warmup_customtkinter()
