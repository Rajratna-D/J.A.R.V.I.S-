"""
============================================================
J.A.R.V.I.S. — System Control Skills
Layer 3: System Automation (FR-07 to FR-11)
============================================================
Handles: volume, brightness, lock, sleep, shutdown,
         screenshots, clipboard, system stats, timers
"""

import os
import logging
import subprocess
import datetime
import pyperclip
import psutil
import pyautogui
from PIL import ImageGrab
from pathlib import Path

from core.brain import Intent, Response
from config import Config

log = logging.getLogger("jarvis.skills.system")

VOLUME_STEP = 10       # % per relative volume command
BRIGHTNESS_STEP = 10   # % per relative brightness command


# ══════════════════════════════════════════════════════════
# FR-07: Volume Control (pycaw)
# ══════════════════════════════════════════════════════════
def _get_volume_interface():
    """Get Windows Core Audio volume interface via pycaw."""
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception as e:
        log.error("Volume interface error: %s", e)
        return None


def _get_current_volume() -> int:
    """Get current master volume as 0-100 int."""
    vol = _get_volume_interface()
    if vol:
        try:
            return int(vol.GetMasterVolumeLevelScalar() * 100)
        except Exception:
            pass
    return 50  # fallback


def _set_volume_scalar(scalar: float):
    """Set volume (0.0 to 1.0)."""
    vol = _get_volume_interface()
    if vol:
        scalar = max(0.0, min(1.0, scalar))
        vol.SetMasterVolumeLevelScalar(scalar, None)


def handle_volume_set(intent: Intent) -> Response:
    value = intent.params.get("value")
    if value is None:
        return Response(text="What percentage should I set the volume to, Sir?", success=False)
    value = max(0, min(100, value))
    _set_volume_scalar(value / 100.0)
    return Response(text=f"Volume set to {value}%, Sir.", data={"volume": value})


def handle_volume_up(intent: Intent) -> Response:
    current = _get_current_volume()
    new_vol = min(100, current + VOLUME_STEP)
    _set_volume_scalar(new_vol / 100.0)
    return Response(text=f"Volume up to {new_vol}%, Sir.", data={"volume": new_vol})


def handle_volume_down(intent: Intent) -> Response:
    current = _get_current_volume()
    new_vol = max(0, current - VOLUME_STEP)
    _set_volume_scalar(new_vol / 100.0)
    return Response(text=f"Volume down to {new_vol}%, Sir.", data={"volume": new_vol})


def handle_volume_mute(intent: Intent) -> Response:
    vol = _get_volume_interface()
    if vol:
        vol.SetMute(1, None)
    return Response(text="Audio muted, Sir.")


def handle_volume_unmute(intent: Intent) -> Response:
    vol = _get_volume_interface()
    if vol:
        vol.SetMute(0, None)
    return Response(text="Audio restored, Sir.")


# ══════════════════════════════════════════════════════════
# FR-08: Brightness Control
# ══════════════════════════════════════════════════════════
def _get_brightness() -> int:
    try:
        import screen_brightness_control as sbc
        return sbc.get_brightness()[0]
    except Exception:
        return 50


def _set_brightness(level: int):
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(max(0, min(100, level)))
    except Exception as e:
        log.error("Brightness set error: %s", e)


def handle_brightness_set(intent: Intent) -> Response:
    value = intent.params.get("value")
    if value is None:
        return Response(text="What percentage should I set the brightness to, Sir?", success=False)
    _set_brightness(value)
    return Response(text=f"Brightness set to {value}%, Sir.")


def handle_brightness_up(intent: Intent) -> Response:
    current = _get_brightness()
    new_b = min(100, current + BRIGHTNESS_STEP)
    _set_brightness(new_b)
    return Response(text=f"Brightness increased to {new_b}%, Sir.")


def handle_brightness_down(intent: Intent) -> Response:
    current = _get_brightness()
    new_b = max(5, current - BRIGHTNESS_STEP)
    _set_brightness(new_b)
    return Response(text=f"Brightness reduced to {new_b}%, Sir.")


# ══════════════════════════════════════════════════════════
# FR-09: Power & Lock Management
# ══════════════════════════════════════════════════════════
def handle_lock_screen(intent: Intent) -> Response:
    import ctypes
    ctypes.windll.user32.LockWorkStation()
    return Response(text="Locking the workstation, Sir.")


def handle_sleep(intent: Intent) -> Response:
    subprocess.Popen(
        ["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"],
        shell=False
    )
    return Response(text="Putting the computer to sleep, Sir. Good night.")


def handle_shutdown(intent: Intent) -> Response:
    confirmed = intent.params.get("confirmed", False)
    if confirmed:
        subprocess.Popen(["shutdown", "/s", "/t", "5"], shell=True)
        return Response(text="Shutting down in 5 seconds, Sir. It has been an honour.")
    else:
        return Response(
            text="Are you sure you want to shut down, Sir?",
            data={"needs_confirmation": True, "action": "shutdown"}
        )


def handle_restart(intent: Intent) -> Response:
    confirmed = intent.params.get("confirmed", False)
    if confirmed:
        subprocess.Popen(["shutdown", "/r", "/t", "5"], shell=True)
        return Response(text="Restarting in 5 seconds, Sir.")
    else:
        return Response(
            text="Shall I restart the computer, Sir?",
            data={"needs_confirmation": True, "action": "restart"}
        )


def handle_cancel(intent: Intent) -> Response:
    # Also try to cancel any pending shutdown
    subprocess.Popen(["shutdown", "/a"], shell=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return Response(text="Understood, Sir. Action cancelled.")


def handle_confirm(intent: Intent) -> Response:
    # This is handled by Brain with pending_confirmation — should rarely hit here
    return Response(text="Nothing to confirm, Sir.")


# ══════════════════════════════════════════════════════════
# FR-10: Screenshots & Clipboard
# ══════════════════════════════════════════════════════════
def _get_screenshot_folder() -> Path:
    folder = Path(Config.screenshot_folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def handle_screenshot_full(intent: Intent) -> Response:
    try:
        folder = _get_screenshot_folder()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = folder / f"jarvis_screenshot_{timestamp}.png"
        screenshot = ImageGrab.grab()
        screenshot.save(str(filename))
        return Response(
            text=f"Screenshot saved to your Pictures folder, Sir.",
            data={"file": str(filename)}
        )
    except Exception as e:
        log.error("Screenshot error: %s", e)
        return Response(text=f"Screenshot failed, Sir: {e}", success=False)


def handle_screenshot_window(intent: Intent) -> Response:
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        rect = win32gui.GetWindowRect(hwnd)
        folder = _get_screenshot_folder()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = folder / f"jarvis_window_{timestamp}.png"
        screenshot = ImageGrab.grab(bbox=rect)
        screenshot.save(str(filename))
        return Response(
            text="Window screenshot saved, Sir.",
            data={"file": str(filename)}
        )
    except Exception as e:
        log.error("Window screenshot error: %s", e)
        return Response(text=f"Window screenshot failed, Sir: {e}", success=False)


def handle_clipboard_read(intent: Intent) -> Response:
    try:
        content = pyperclip.paste()
        if not content:
            return Response(text="Your clipboard appears to be empty, Sir.")
        # Truncate long content for voice
        if len(content) > 200:
            short = content[:200] + "..."
            return Response(
                text=f"Your clipboard contains: {short}",
                data={"clipboard": content}
            )
        return Response(
            text=f"Your clipboard contains: {content}",
            data={"clipboard": content}
        )
    except Exception as e:
        return Response(text=f"Couldn't read clipboard, Sir: {e}", success=False)


# ══════════════════════════════════════════════════════════
# FR-05: System Stats
# ══════════════════════════════════════════════════════════
def handle_stats_cpu(intent: Intent) -> Response:
    cpu = psutil.cpu_percent(interval=1)
    freq = psutil.cpu_freq()
    cores = psutil.cpu_count(logical=False)
    freq_ghz = f"{freq.current / 1000:.1f} GHz" if freq else ""
    return Response(
        text=f"CPU is at {cpu:.0f}% utilisation, {cores} cores at {freq_ghz}, Sir.",
        data={"cpu_percent": cpu}
    )


def handle_stats_ram(intent: Intent) -> Response:
    ram = psutil.virtual_memory()
    used_gb = ram.used / (1024 ** 3)
    total_gb = ram.total / (1024 ** 3)
    return Response(
        text=f"RAM usage is {ram.percent:.0f}%, that's {used_gb:.1f} of {total_gb:.1f} gigabytes, Sir.",
        data={"ram_percent": ram.percent, "used_gb": used_gb, "total_gb": total_gb}
    )


def handle_stats_disk(intent: Intent) -> Response:
    disk = psutil.disk_usage("/")
    used_gb = disk.used / (1024 ** 3)
    total_gb = disk.total / (1024 ** 3)
    return Response(
        text=f"Disk usage is {disk.percent:.0f}%, using {used_gb:.0f} of {total_gb:.0f} gigabytes, Sir.",
        data={"disk_percent": disk.percent}
    )


def handle_stats_all(intent: Intent) -> Response:
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return Response(
        text=(
            f"System report, {Config.username}: "
            f"CPU at {cpu:.0f}%, "
            f"RAM at {ram.percent:.0f}%, "
            f"Disk at {disk.percent:.0f}%. "
            f"All systems operational."
        ),
        data={"cpu": cpu, "ram": ram.percent, "disk": disk.percent}
    )


# ══════════════════════════════════════════════════════════
# FR-11: Timers
# ══════════════════════════════════════════════════════════
def _parse_duration(duration_str: str) -> int | None:
    """Parse '25 minutes', '1 hour 30 minutes', '90 seconds' → seconds."""
    duration_str = duration_str.lower().strip()
    total_seconds = 0
    found = False

    patterns = [
        (r"(\d+)\s*h(?:our)?s?", 3600),
        (r"(\d+)\s*m(?:in(?:ute)?)?s?", 60),
        (r"(\d+)\s*s(?:ec(?:ond)?)?s?", 1),
    ]
    import re
    for pattern, multiplier in patterns:
        for m in re.finditer(pattern, duration_str):
            total_seconds += int(m.group(1)) * multiplier
            found = True

    return total_seconds if found else None


def handle_timer_set(intent: Intent) -> Response:
    from data.database import add_timer
    import threading

    name = intent.params.get("name", "Timer")
    duration_str = intent.params.get("duration_str", "")

    duration_s = _parse_duration(duration_str)
    if not duration_s:
        return Response(
            text=f"I couldn't understand the duration '{duration_str}', Sir. Please say something like '25 minutes'.",
            success=False
        )

    end_time = datetime.datetime.now() + datetime.timedelta(seconds=duration_s)
    timer_id = add_timer(name, duration_s, end_time)

    # Format duration for voice
    mins, secs = divmod(duration_s, 60)
    hours, mins = divmod(mins, 60)
    parts = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if mins:
        parts.append(f"{mins} minute{'s' if mins > 1 else ''}")
    if secs and not hours:
        parts.append(f"{secs} second{'s' if secs > 1 else ''}")
    duration_human = " and ".join(parts)

    # Schedule the timer fire in a background thread
    def _fire_timer():
        import time
        time.sleep(duration_s)
        # Re-check DB (may have been cancelled)
        from data.database import get_active_timers, mark_timer_fired
        active = [t for t in get_active_timers() if t["id"] == timer_id and not t["fired"] and not t["cancelled"]]
        if active:
            mark_timer_fired(timer_id)
            from voice.speaker import speak
            speak(f"{name} complete, {Config.username}. Your {duration_human} timer has finished.")
            try:
                from plyer import notification
                notification.notify(
                    title="JARVIS Timer",
                    message=f"{name} — {duration_human} complete!",
                    timeout=10,
                )
            except Exception:
                pass

    t = threading.Thread(target=_fire_timer, daemon=True, name=f"Timer-{timer_id}")
    t.start()

    return Response(
        text=f"{name} set for {duration_human}, Sir.",
        data={"timer_id": timer_id, "duration_s": duration_s}
    )


def handle_timer_cancel(intent: Intent) -> Response:
    from data.database import cancel_timer
    cancel_timer(cancel_all=True)
    return Response(text="All timers cancelled, Sir.")


def handle_timer_status(intent: Intent) -> Response:
    from data.database import get_active_timers
    timers = get_active_timers()
    active = [t for t in timers if not t["fired"] and not t["cancelled"]]
    if not active:
        return Response(text="No active timers, Sir.")

    timer = active[0]
    end_dt = datetime.datetime.fromisoformat(timer["end_time"])
    remaining = (end_dt - datetime.datetime.now()).total_seconds()
    if remaining <= 0:
        return Response(text="Your timer has just expired, Sir.")
    mins, secs = divmod(int(remaining), 60)
    return Response(text=f"{timer['name']} has {mins} minutes and {secs} seconds remaining, Sir.")


def register(brain):
    """Register all system control skill handlers."""
    # Volume
    brain.register_skill("volume_set", handle_volume_set)
    brain.register_skill("volume_up", handle_volume_up)
    brain.register_skill("volume_down", handle_volume_down)
    brain.register_skill("volume_mute", handle_volume_mute)
    brain.register_skill("volume_unmute", handle_volume_unmute)
    # Brightness
    brain.register_skill("brightness_set", handle_brightness_set)
    brain.register_skill("brightness_up", handle_brightness_up)
    brain.register_skill("brightness_down", handle_brightness_down)
    # Power
    brain.register_skill("lock_screen", handle_lock_screen)
    brain.register_skill("sleep", handle_sleep)
    brain.register_skill("shutdown", handle_shutdown)
    brain.register_skill("restart", handle_restart)
    brain.register_skill("cancel", handle_cancel)
    brain.register_skill("confirm", handle_confirm)
    # Screenshots / Clipboard
    brain.register_skill("screenshot_full", handle_screenshot_full)
    brain.register_skill("screenshot_window", handle_screenshot_window)
    brain.register_skill("clipboard_read", handle_clipboard_read)
    # System Stats
    brain.register_skill("stats_cpu", handle_stats_cpu)
    brain.register_skill("stats_ram", handle_stats_ram)
    brain.register_skill("stats_disk", handle_stats_disk)
    brain.register_skill("stats_all", handle_stats_all)
    # Timers
    brain.register_skill("timer_set", handle_timer_set)
    brain.register_skill("timer_cancel", handle_timer_cancel)
    brain.register_skill("timer_status", handle_timer_status)
