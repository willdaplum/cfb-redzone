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
    "ESPN+/SECN+": "https://www.disneyplus.com/browse/entity-67d48152-056a-4fc1-bd99-e943cfe56481",
    "ESPNU": "",
    "ABC": "https://abc.com/watch-live/784b058c-3aee-4ec9-a6d3-754ba6e4dbac",
    "Peacock": "",
    "Fox": "",
    "FS1": "",
    "FS2": "",
    "CBS/Paramount+": "https://www.cbs.com/live-tv/stream/tveverywhere/",
    "NBC/Peacock": "",
    "CBS Sports Network": "",
    "BTN": "",
    "ACC Network": "",
    "SEC Network": "",
    "The CW Network": "",
    "TNT": "",
    # Add/remove/modify depending on what broadcasts you have access to
}