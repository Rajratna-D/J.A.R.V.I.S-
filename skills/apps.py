"""
============================================================
J.A.R.V.I.S. — App Control Skills
Layer 3: System Automation (FR-01, FR-02, FR-03, FR-04)
============================================================
Handles: open app, close app, switch app, window management,
         list running apps, virtual desktops
"""

import os
import re
import subprocess
import logging
import psutil
import pygetwindow as gw
from fuzzywuzzy import fuzz
from core.brain import Intent, Response
from config import Config

log = logging.getLogger("jarvis.skills.apps")


# ══════════════════════════════════════════════════════════
# App Name → Executable Mapping
# ══════════════════════════════════════════════════════════
def _get_app_exe(name: str) -> str | None:
    """Resolve app name to executable path using config aliases."""
    name_l = name.lower().strip()

    # Direct alias match
    if name_l in Config.app_aliases:
        return Config.app_aliases[name_l]

    # Fuzzy match on aliases
    best_score = 0
    best_exe = None
    for alias, exe in Config.app_aliases.items():
        score = fuzz.partial_ratio(name_l, alias)
        if score > best_score:
            best_score = score
            best_exe = exe

    if best_score >= 70:
        return best_exe

    # Try direct execution (e.g. user said "notepad" and it's on PATH)
    return name_l + ".exe" if not name_l.endswith(".exe") else name_l


def _resolve_exe_path(exe: str) -> str:
    """Resolve an executable name (e.g. 'chrome.exe') to its absolute path on Windows."""
    if os.path.isabs(exe) or ":" in exe:
        return exe

    try:
        import winreg
        for hkey in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                key_path = f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe}"
                with winreg.OpenKey(hkey, key_path) as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val:
                        val = val.strip('"')
                        if os.path.exists(val):
                            log.info("Resolved %s via registry: %s", exe, val)
                            return val
            except OSError:
                continue
    except ImportError:
        pass

    # Fallback to common installation folders
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    local_app_data = os.environ.get("LocalAppData", os.path.expanduser("~\\AppData\\Local"))

    fallbacks = {
        "chrome.exe": [
            os.path.join(program_files, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(program_files_x86, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(local_app_data, "Google\\Chrome\\Application\\chrome.exe"),
        ],
        "firefox.exe": [
            os.path.join(program_files, "Mozilla Firefox\\firefox.exe"),
            os.path.join(program_files_x86, "Mozilla Firefox\\firefox.exe"),
        ],
        "msedge.exe": [
            os.path.join(program_files, "Microsoft\\Edge\\Application\\msedge.exe"),
            os.path.join(program_files_x86, "Microsoft\\Edge\\Application\\msedge.exe"),
        ],
    }

    if exe in fallbacks:
        for path in fallbacks[exe]:
            if os.path.exists(path):
                log.info("Resolved %s via fallback: %s", exe, path)
                return path

    return exe


def _launch_app(exe: str) -> bool:
    """Try to launch an application."""
    try:
        # Handle ms-settings: style URIs
        if exe.startswith("ms-"):
            os.startfile(exe)
            return True

        # Resolve path
        resolved_exe = _resolve_exe_path(exe)

        # Normal executable
        cmd = f'"{resolved_exe}"' if os.path.isabs(resolved_exe) else resolved_exe
        subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        log.error("Failed to launch %s: %s", exe, e)
        return False


# ── FR-01: Launch App ─────────────────────────────────────
def handle_open_app(intent: Intent) -> Response:
    app_name = intent.params.get("app_name", "").strip()
    if not app_name:
        return Response(text="Which app would you like me to open, Sir?", success=False)

    exe = _get_app_exe(app_name)
    if exe and _launch_app(exe):
        return Response(
            text=f"Opening {app_name}, Sir.",
            data={"app": app_name, "exe": exe}
        )
    else:
        return Response(
            text=f"I couldn't find or open {app_name}, Sir. Please check if it's installed.",
            success=False
        )


# ── FR-02: Switch App ─────────────────────────────────────
def handle_switch_app(intent: Intent) -> Response:
    app_name = intent.params.get("app_name", "").strip()
    if not app_name:
        return Response(text="Which app should I switch to, Sir?", success=False)

    # Find best matching open window
    windows = gw.getAllWindows()
    best_win = None
    best_score = 0

    for win in windows:
        if not win.title:
            continue
        score = fuzz.partial_ratio(app_name.lower(), win.title.lower())
        if score > best_score:
            best_score = score
            best_win = win

    if best_win and best_score >= 50:
        try:
            if best_win.isMinimized:
                best_win.restore()
            best_win.activate()
            return Response(text=f"Switching to {best_win.title}, Sir.")
        except Exception as e:
            log.error("Window switch error: %s", e)
            return Response(text=f"I found the window but couldn't switch to it, Sir.", success=False)
    else:
        return Response(
            text=f"I couldn't find {app_name} in your open windows, Sir.",
            success=False
        )


# ── FR-03: Close App ──────────────────────────────────────
def handle_close_app(intent: Intent) -> Response:
    app_name = intent.params.get("app_name", "").strip()
    if not app_name:
        return Response(text="Which app should I close, Sir?", success=False)

    # First try to close the window gracefully
    windows = gw.getAllWindows()
    closed = False

    for win in windows:
        if not win.title:
            continue
        score = fuzz.partial_ratio(app_name.lower(), win.title.lower())
        if score >= 50:
            try:
                win.close()
                closed = True
                log.info("Closed window: %s", win.title)
                break
            except Exception as e:
                log.warning("Could not close window %s: %s", win.title, e)

    if closed:
        return Response(text=f"Closing {app_name}, Sir.")

    # Fallback: kill by process name
    app_l = app_name.lower()
    for proc in psutil.process_iter(["name", "pid"]):
        proc_name = (proc.info["name"] or "").lower()
        if app_l in proc_name or fuzz.partial_ratio(app_l, proc_name) >= 70:
            try:
                proc.terminate()
                return Response(text=f"Terminated {app_name}, Sir.")
            except Exception as e:
                log.error("Process termination error: %s", e)

    return Response(
        text=f"I couldn't find a running instance of {app_name}, Sir.",
        success=False
    )


# ── FR-04: Window Management ──────────────────────────────
def handle_window_snap(intent: Intent) -> Response:
    direction = intent.params.get("direction", "").lower()
    import win32gui
    import win32con

    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return Response(text="No active window found to snap, Sir.", success=False)

    screen_w = 1920   # TODO: detect actual screen resolution
    screen_h = 1080

    try:
        if direction in ("left",):
            win32gui.SetWindowPos(hwnd, None, 0, 0, screen_w // 2, screen_h,
                                  win32con.SWP_NOZORDER)
            return Response(text="Snapped window to the left, Sir.")

        elif direction in ("right",):
            win32gui.SetWindowPos(hwnd, None, screen_w // 2, 0, screen_w // 2, screen_h,
                                  win32con.SWP_NOZORDER)
            return Response(text="Snapped window to the right, Sir.")

        elif direction in ("maximize", "full", "fullscreen"):
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return Response(text="Window maximised, Sir.")

        elif direction in ("minimize", "minimise"):
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return Response(text="Window minimised, Sir.")

        elif direction in ("restore",):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            return Response(text="Window restored, Sir.")

        else:
            return Response(text=f"I don't know how to snap to '{direction}', Sir.", success=False)

    except Exception as e:
        log.error("Window snap error: %s", e)
        return Response(text=f"Couldn't manage the window, Sir: {e}", success=False)


# ── List Running Apps ──────────────────────────────────────
def handle_list_apps(intent: Intent) -> Response:
    windows = [w.title for w in gw.getAllWindows() if w.title and w.visible]
    if not windows:
        return Response(text="No visible windows found, Sir.")

    app_list = ", ".join(windows[:8])  # Limit to 8 for voice
    return Response(
        text=f"You have {len(windows)} windows open, Sir: {app_list}.",
        data={"windows": windows}
    )


def register(brain):
    """Register all app control skill handlers."""
    brain.register_skill("open_app", handle_open_app)
    brain.register_skill("close_app", handle_close_app)
    brain.register_skill("switch_app", handle_switch_app)
    brain.register_skill("window_snap", handle_window_snap)
    brain.register_skill("list_apps", handle_list_apps)
