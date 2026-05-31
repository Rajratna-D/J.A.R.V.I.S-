"""
============================================================
J.A.R.V.I.S. — Hotkey Trigger
Layer 1: Voice Pipeline
============================================================
Registers a global hotkey (Alt+J) that triggers JARVIS listening.
Works system-wide even when the JARVIS window is not focused.
"""

import keyboard
import logging
import threading
from typing import Callable
from config import Config

log = logging.getLogger("jarvis.hotkey")


class HotkeyManager:
    """
    Manages global hotkey registration.
    Calls the provided callback when the hotkey is pressed.
    Debounced to prevent accidental double-triggers.
    """

    def __init__(self):
        self._callback: Callable = None
        self._cooldown: float = 1.0   # seconds between triggers
        self._last_trigger: float = 0
        self._registered: bool = False

    def register(self, callback: Callable, hotkey: str = None):
        """
        Register the global hotkey.
        callback: function to call when hotkey is pressed
        hotkey: keyboard shortcut string (e.g. "alt+j")
        """
        self._callback = callback
        hotkey = hotkey or Config.hotkey

        if self._registered:
            keyboard.remove_hotkey(hotkey)

        keyboard.add_hotkey(
            hotkey,
            self._on_trigger,
            suppress=False,  # Don't consume the key event
        )
        self._registered = True
        log.info("Hotkey '%s' registered for JARVIS activation", hotkey)
        print(f"  [OK] Hotkey [{hotkey.upper()}] registered -- press to activate JARVIS")

    def _on_trigger(self):
        """Called when hotkey is pressed — debounced."""
        import time
        now = time.time()
        if now - self._last_trigger < self._cooldown:
            log.debug("Hotkey debounced (too soon)")
            return
        self._last_trigger = now

        # Run callback in a separate thread so hotkey handler returns fast
        if self._callback:
            t = threading.Thread(target=self._callback, daemon=True, name="HotkeyCallback")
            t.start()

    def unregister(self):
        """Remove the hotkey registration."""
        try:
            keyboard.unhook_all_hotkeys()
            self._registered = False
            log.info("Hotkeys unregistered")
        except Exception as e:
            log.warning("Error unregistering hotkeys: %s", e)


# ── Singleton ─────────────────────────────────────────────
_manager: HotkeyManager = None


def get_hotkey_manager() -> HotkeyManager:
    global _manager
    if _manager is None:
        _manager = HotkeyManager()
    return _manager
