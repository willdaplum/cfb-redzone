#!/usr/bin/env python3
"""
cfb_redzone.py - Proof of concept:
- Launches Chrome user-data dirs (one per service)
- Opens game pages for chosen games
- Polls ESPN scoreboard/play-by-play JSON and brings red-zone games forward

Notes:
- Customize SERVICE_URL_TEMPLATES to map service -> URL pattern for a game
- ESPN JSON endpoints are used here as an example. You may need to adapt parsing for other sources.
"""

import subprocess
import time
import json
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests
import pygetwindow as gw
import pyautogui
from tqdm import tqdm

from config import (
    CHROME_PATH,
    BASE_PROFILE_DIR,
    POLL_INTERVAL,
    SWITCH_GRACE_SECONDS,
    RED_ZONE_YARDS,
    SERVICE_URL_TEMPLATES
)

# ----------------------------
# Simple data classes
# ----------------------------
@dataclass
class Game:
    id: str
    short_name: str         # e.g., "OSU vs PSU"
    competition_href: str   # link to the game's watch/summary page
    play_by_play_href: Optional[str]  # URL to poll for drives / plays

@dataclass
class ServiceProfile:
    name: str               # "espn", "peacock", ...
    profile_dir: Path       # path to chrome user-data-dir to use
    launched: bool = False

# ----------------------------
# Helper: find platform chrome
# ----------------------------
import platform
def get_chrome_exe():
    system = platform.system().lower()
    if "windows" in system:
        return CHROME_PATH["win"]
    if "darwin" in system:
        return CHROME_PATH["mac"]
    return CHROME_PATH["linux"]

# ----------------------------
# Scoreboard + Play-by-Play fetcher (example: ESPN)
# ----------------------------
class ESPNFetcher:
    """
    Lightweight fetcher using ESPN JSON endpoints.
    This is intentionally minimal — adjust parsing if ESPN changes JSON schema.
    """
    BASE_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"

    def __init__(self, date: Optional[str] = None):
        self.date = date  # YYYYMMDD if desired; leave None for "today"

    def fetch_scoreboard(self) -> List[Game]:
        params = {}
        if self.date:
            params["dates"] = self.date
        r = requests.get(self.BASE_SCOREBOARD, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        games: List[Game] = []
        for comp in data.get("events", []) + data.get("competitions", []):
            # flexible access depending on version of feed
            event = comp if "id" in comp else comp
            cid = event.get("id") or event.get("uid") or event.get("gameId") or str(event.get("name"))
            # try to get a link to the game's main page
            href = None
            play_href = None
            for link in event.get("links", []):
                rel = link.get("rel", [])
                if "summary" in rel or "gamepackage" in rel or "boxscore" in rel:
                    href = link.get("href")
                if "playbyplay" in rel or "pbp" in rel:
                    play_href = link.get("href")

            # fallback: find the alternate link container
            if not href:
                for link in event.get("shortLinkHref", []):
                    href = link

            # build short_name from competitors if possible
            teams = []
            for c in event.get("competitors", []):
                teams.append(c.get("team", {}).get("shortDisplayName") or c.get("displayName") or c.get("abbreviation"))
            short_name = " vs ".join(teams) if teams else event.get("name", cid)

            if href:
                games.append(Game(id=str(cid), short_name=short_name, competition_href=href, play_by_play_href=play_href))
        return games

    def fetch_latest_play(self, play_by_play_href: str) -> Dict:
        """
        Fetch the latest play or drive info from a play-by-play JSON URL.
        The JSON shapes vary; we attempt to find a yardline or description.
        Returns a dict with keys like 'desc' and 'yardline' when available.
        """
        if not play_by_play_href:
            return {}
        r = requests.get(play_by_play_href, timeout=10)
        r.raise_for_status()
        j = r.json()
        # attempt to find last play
        # many ESPN endpoints put plays under j['plays'] or j['drives']
        # Searching heuristically:
        # Try top-level plays list:
        plays = []
        if isinstance(j.get("plays"), list):
            plays = j["plays"]
        else:
            # dig into drives -> plays
            drives = j.get("drives") or {}
            for d in drives.get("entries", []) or []:
                for p in d.get("plays", []) or []:
                    plays.append(p)
        if not plays:
            # fallback: maybe event has items
            plays = j.get("items", []) or []

        if not plays:
            return {}

        last = plays[-1]
        desc = last.get("text") or last.get("description") or last.get("playDescription") or ""
        # try to find yardline
        yardline = None
        # many play objects include 'yardLine' or 'yardsToGo' or 'yardLineNumber'
        for key in ("yardLine", "yardLineNumber", "startYardLine", "yardsToGo"):
            if key in last:
                try:
                    yardline_val = int(last.get(key) or 0)
                    yardline = yardline_val
                    break
                except Exception:
                    pass
        return {"desc": desc, "yardline": yardline, "raw": last}

# ----------------------------
# Browser manager: create profile dirs and launch Chrome windows
# ----------------------------
def ensure_profile_dir(service_name: str) -> Path:
    p = BASE_PROFILE_DIR / service_name
    p.mkdir(parents=True, exist_ok=True)
    return p

def launch_chrome_with_profile(profile_dir: Path, url: str):
    chrome = get_chrome_exe()
    # Use --user-data-dir to isolate cookies; --new-window so each URL gets its window
    cmd = [
        chrome,
        f'--user-data-dir={str(profile_dir)}',
        '--no-first-run',
        '--new-window',
        url
    ]
    # On macOS the Chrome path contains spaces; pass whole stringlist is fine
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print("Failed to launch Chrome. Cmd:", cmd, "error:", e)

# ----------------------------
# Window control
# ----------------------------
def bring_window_to_front_by_title_hint(title_hint: str, timeout=6) -> bool:
    """
    Attempt to find a window whose title contains title_hint and activate it.
    Returns True on success.
    """
    # try repeated searches for a few seconds
    end = time.time() + timeout
    while time.time() < end:
        titles = gw.getAllTitles()
        for t in titles:
            if not t:
                continue
            if title_hint.lower() in t.lower():
                try:
                    w = gw.getWindowsWithTitle(t)[0]
                    w.activate()
                    # if activation fails, fallback to click
                    return True
                except Exception:
                    # fallback: try click center of approximate window
                    try:
                        # get bounding box, click in the middle
                        w = gw.getWindowsWithTitle(t)[0]
                        left, top, width, height = w.left, w.top, w.width, w.height
                        pyautogui.click(left + width // 2, top + height // 2)
                        return True
                    except Exception:
                        pass
        time.sleep(0.3)
    return False

# ----------------------------
# Main controller
# ----------------------------
def main():
    print("CFB RedZone")
    # Step 1: ask what services you have
    available = list(SERVICE_URL_TEMPLATES.keys())
    print("Available services:", ", ".join(available))
    chosen = input("Which services do you have access to? (comma separated) ").strip().lower().split(",")
    chosen = [c.strip() for c in chosen if c.strip()]
    profiles = {}
    for s in chosen:
        if s not in SERVICE_URL_TEMPLATES:
            print(f"Warning: {s} not in known services. I'll still create a profile for it.")
        pdir = ensure_profile_dir(s)
        profiles[s] = ServiceProfile(name=s, profile_dir=pdir)

    # Step 2: fetch today's games (ESPN example)
    fetcher = ESPNFetcher()
    print("Fetching today's schedule from ESPN...")
    try:
        games = fetcher.fetch_scoreboard()
    except Exception as e:
        print("Failed to fetch scoreboard:", e)
        return

    if not games:
        print("No games found. Exiting.")
        return

    # present games to user to pick which to follow
    print("Found games:")
    for i, g in enumerate(games):
        print(f"[{i}] {g.short_name}  (play_by_play: {'yes' if g.play_by_play_href else 'no'})")
    pick_raw = input("Enter indices of games to follow (comma separated, e.g. 0,3,5) or 'all': ").strip()
    if pick_raw.lower() == "all":
        chosen_games = games
    else:
        idxs = [int(x.strip()) for x in pick_raw.split(",") if x.strip().isdigit()]
        chosen_games = [games[i] for i in idxs]

    # Map each chosen game to a service (simple heuristic: ask user)
    game_launches = []

    # to be replaced:
    game_launches = []
    print("\nFor each chosen game, specify which service you'll open it with.")
    for g in chosen_games:
        print(f"Game: {g.short_name}")
        svc = input(f" Service (one of {', '.join(chosen)}): ").strip().lower()
        if svc not in profiles:
            print("Unknown service, using first available.")
            svc = next(iter(profiles.keys()))
        # compute URL for this service - default: use the competition_href as-is
        template = SERVICE_URL_TEMPLATES.get(svc, "{game_href}")
        url = template.format(game_href=g.competition_href)
        game_launches.append((g, svc, url))
    # to be replaced ^

    # Step 3: Launch all games (one window per game, using the service's profile)
    print("\nLaunching browser windows for each chosen game. For each window, complete login if required.")
    for g, svc, url in game_launches:
        prof = profiles[svc]
        print(f"Launching {g.short_name} in profile '{svc}' -> {url}")
        launch_chrome_with_profile(prof.profile_dir, url)
        prof.launched = True
        time.sleep(0.8)  # small spacing so windows don't interfere

    print("\nWaiting 30s for pages to load and for you to login if needed...")
    for i in tqdm(range(30), desc="Initial wait"):
        time.sleep(1)

    # Step 4: Monitoring loop
    print("Entering monitoring loop. Ctrl-C to exit.")
    last_switch_time = 0
    currently_featured_game = None

    try:
        while True:
            best_game = None
            best_metric = -999
            # For each tracked game, fetch latest play and compute a 'score' for switching
            for g, svc, url in game_launches:
                info = {}
                try:
                    if g.play_by_play_href:
                        info = fetcher.fetch_latest_play(g.play_by_play_href)
                except Exception:
                    info = {}
                desc = info.get("desc", "") or ""
                yardline = info.get("yardline")
                # heuristic: if yardline not None and <= RED_ZONE_YARDS -> candidate
                score = 0
                if yardline is not None:
                    # smaller yardline gets higher score (0 near goal line)
                    score = max(0, (RED_ZONE_YARDS - yardline) + 50)
                # text heuristics
                txt = desc.lower()
                if "in the red zone" in txt or "inside the 20" in txt or "inside the 10" in txt:
                    score += 100
                if "touchdown" in txt:
                    score += 80
                # more advanced heuristics could parse possession/downs/seconds left
                if score > best_metric:
                    best_metric = score
                    best_game = (g, svc, url, desc, yardline)

            # Decide whether to switch
            tnow = time.time()
            if best_game and best_metric > 0 and (tnow - last_switch_time > SWITCH_GRACE_SECONDS):
                g, svc, url, desc, yardline = best_game
                print(f"[{time.strftime('%H:%M:%S')}] Switching to {g.short_name} (score {best_metric}). Desc: {desc} yardline={yardline}")
                # try to bring the window to front using some hint (short_name or team names)
                title_hint = g.short_name.split(" vs ")[0]  # a simple part of title
                success = bring_window_to_front_by_title_hint(title_hint, timeout=4)
                if not success:
                    # fallback: try url hint
                    success = bring_window_to_front_by_title_hint(url, timeout=2)
                if not success:
                    print("Could not locate window to bring forward. You may need to customize title hint logic.")
                else:
                    currently_featured_game = g
                    last_switch_time = tnow
            # sleep until next poll
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("Stopping monitor. Exiting.")

if __name__ == "__main__":
    main()