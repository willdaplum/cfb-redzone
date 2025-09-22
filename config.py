from pathlib import Path

# ----------------------------
# Config: edit these for your env
# ----------------------------
CHROME_PATH = {
    "win": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "mac": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "linux": "/usr/bin/google-chrome"
}

# Base dir where we create per-service chrome profiles
BASE_PROFILE_DIR = Path.home() / ".cfb_redzone_profiles"

# Poll interval (seconds)
POLL_INTERVAL = 12

# How many seconds of "grace" before switching away
SWITCH_GRACE_SECONDS = 10

# Heuristic: detect "red zone" using play-by-play text or yardline
RED_ZONE_YARDS = 20

# Example: service -> display name (and optional url template)
# URL template expected to accept a competition id or game path that fetcher returns.
SERVICE_URL_TEMPLATES = {
    "espn": "{game_href}",          # game_href will be taken from the scoreboard JSON
    "peacock": "{game_href}",
    "fox": "{game_href}",
    # You can map other services to their per-game watch URLs here.
}

AVAILABLE_BROADCASTS = {
    "ESPN": "",
    "ESPN2": "",
    "ESPN3": "",
    "ESPN+": "",
    "ESPNU": "",
    "ABC": "",
    "Peacock": "",
    "Fox": "",
    "FS1": "",
    "FS2": "",
    "CBS": "",
    "NBC": "",
    "CBS Sports Network": "",
    "BTN": "",
    "ACC Network": "",
    "SEC Network": "",
    "Longhorn Network": "",
    "Pac-12 Network": "",
    "The CW": "",
    "TNT": "",
    # Add/remove/modify depending on what broadcasts you have access to
}