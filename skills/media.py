"""
============================================================
J.A.R.V.I.S. — Media & Music Skills
Layer 4: Music & Media (FR-12, FR-13)
============================================================
Handles: play/pause/skip media, YouTube playback/search
Uses Windows media key simulation (works with Spotify, YouTube, VLC, etc.)
"""

import webbrowser
import urllib.parse
import logging
import keyboard
import os
import psutil

from core.brain import Intent, Response

log = logging.getLogger("jarvis.skills.media")


# ══════════════════════════════════════════════════════════
# FR-12: Media Playback Control (Windows Media Keys)
# ══════════════════════════════════════════════════════════
def handle_media_play(intent: Intent) -> Response:
    # 1. Try to send play/pause media hardware key
    try:
        keyboard.send("play/pause media")
    except Exception as e:
        log.warning("Failed to send play/pause key: %s", e)

    # 2. Check if a dedicated media player process is running
    media_running = False
    media_apps = ["spotify.exe", "vlc.exe", "itunes.exe", "foobar2000.exe", "winamp.exe", "wmplayer.exe", "music.ui.exe"]
    for proc in psutil.process_iter(["name"]):
        try:
            name = (proc.info["name"] or "").lower()
            if any(app in name for app in media_apps):
                media_running = True
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not media_running:
        # Check if Spotify is installed using our apps path resolver
        from skills.apps import _resolve_exe_path, _launch_app
        spotify_path = _resolve_exe_path("Spotify.exe")
        if os.path.isabs(spotify_path) and os.path.exists(spotify_path):
            _launch_app(spotify_path)
            return Response(text="Starting Spotify and playing music, Sir.")
        else:
            # Fallback to browser YouTube Music
            try:
                webbrowser.open("https://music.youtube.com")
                return Response(text="Opening YouTube Music in your browser, Sir.")
            except Exception as e:
                log.error("Failed to open YouTube Music web: %s", e)
                return Response(text="I couldn't start a music player, Sir.", success=False)

    return Response(text="Playing, Sir.")


def handle_media_pause(intent: Intent) -> Response:
    keyboard.send("play/pause media")
    return Response(text="Paused, Sir.")


def handle_media_stop(intent: Intent) -> Response:
    keyboard.send("stop media")
    return Response(text="Stopping media, Sir.")


def handle_media_next(intent: Intent) -> Response:
    keyboard.send("next track")
    return Response(text="Skipping to the next track, Sir.")


def handle_media_prev(intent: Intent) -> Response:
    keyboard.send("previous track")
    return Response(text="Going back to the previous track, Sir.")


# ══════════════════════════════════════════════════════════
# FR-13: YouTube Playback
# ══════════════════════════════════════════════════════════
def handle_youtube_play(intent: Intent) -> Response:
    query = intent.params.get("query", "").strip()
    if not query:
        return Response(text="What would you like me to play on YouTube, Sir?", success=False)

    import requests
    import re

    # Try to find the first video ID for direct auto-play
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=4)
        video_ids = re.findall(r"watch\?v=([a-zA-Z0-9_-]{11})", r.text)
        if video_ids:
            direct_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
            webbrowser.open(direct_url)
            return Response(text=f"Playing {query} on YouTube, Sir.")
    except Exception as e:
        log.warning("YouTube direct play search failed: %s", e)

    # Fallback to search results URL if scraping failed
    webbrowser.open(url)
    return Response(text=f"Opening YouTube search for {query}, Sir.")


def handle_youtube_search(intent: Intent) -> Response:
    query = intent.params.get("query", "").strip()
    if not query:
        return Response(text="What should I search for on YouTube, Sir?", success=False)

    encoded = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={encoded}"
    webbrowser.open(url)
    return Response(text=f"Searching YouTube for {query}, Sir.")


def register(brain):
    """Register all media skill handlers."""
    brain.register_skill("media_play", handle_media_play)
    brain.register_skill("media_pause", handle_media_pause)
    brain.register_skill("media_stop", handle_media_stop)
    brain.register_skill("media_next", handle_media_next)
    brain.register_skill("media_prev", handle_media_prev)
    brain.register_skill("youtube_play", handle_youtube_play)
    brain.register_skill("youtube_search", handle_youtube_search)
