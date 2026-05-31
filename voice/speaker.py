"""
============================================================
J.A.R.V.I.S. — Text-to-Speech (TTS) Engine
Layer 1: Voice Pipeline
============================================================
Wraps pyttsx3 for local, offline, async voice output.
JARVIS persona: deep, calm voice — no cloud, no latency.
"""

import pyttsx3
import threading
import logging
import queue
import pythoncom
from config import Config

log = logging.getLogger("jarvis.speaker")


class Speaker:
    """
    Thread-safe TTS speaker.
    Queues speech requests and processes them in a dedicated thread
    so the main loop is never blocked during voice output.
    """

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._engine = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="TTS-Thread")
        self._thread.start()
        log.info("Speaker initialised (async TTS thread running)")

    def _init_engine(self) -> pyttsx3.Engine:
        """Initialise pyttsx3 engine on the TTS thread (required for COM)."""
        engine = pyttsx3.init()

        # ── Voice selection: prefer deeper/male voice ──────
        voices = engine.getProperty("voices")
        preferred = None
        for v in voices:
            name_lower = v.name.lower()
            # Prefer David (US male) or Zira's counterpart on Windows
            if "david" in name_lower or "mark" in name_lower or "george" in name_lower:
                preferred = v.id
                break
        if preferred:
            engine.setProperty("voice", preferred)
        elif voices:
            engine.setProperty("voice", voices[0].id)   # fallback

        # ── Speed & Volume ─────────────────────────────────
        engine.setProperty("rate", Config.voice_speed)
        engine.setProperty("volume", Config.voice_volume)

        log.info(
            "TTS engine ready | voice=%s | rate=%d | volume=%.1f",
            preferred or "default",
            Config.voice_speed,
            Config.voice_volume,
        )
        return engine

    def _run(self):
        """Main loop for the TTS worker thread."""
        pythoncom.CoInitialize()
        self._engine = self._init_engine()
        while True:
            text = self._queue.get()
            if text is None:   # Sentinel: shutdown signal
                break
            if Config.voice_enabled:
                try:
                    self._engine.say(text)
                    self._engine.runAndWait()
                except Exception as e:
                    log.error("TTS error: %s", e)
            self._queue.task_done()

    def speak(self, text: str):
        """
        Queue a text string for voice output.
        Non-blocking — returns immediately.
        """
        log.debug("Queuing speech: %s", text)
        print(f"\n🤖 JARVIS: {text}\n")   # Always print even if voice disabled
        self._queue.put(text)

    def speak_sync(self, text: str):
        """
        Speak and block until done (used for boot greeting).
        """
        self._queue.put(text)
        self._queue.join()

    def stop(self):
        """Graceful shutdown."""
        self._queue.put(None)
        self._thread.join(timeout=3)

    def set_speed(self, rate: int):
        """Update TTS speed at runtime."""
        Config.voice_speed = rate
        if self._engine:
            self._engine.setProperty("rate", rate)

    def toggle_voice(self):
        """Toggle voice output on/off."""
        Config.voice_enabled = not Config.voice_enabled
        state = "enabled" if Config.voice_enabled else "disabled"
        log.info("Voice output %s", state)
        return Config.voice_enabled


# ── Module-level singleton ────────────────────────────────
_speaker_instance: Speaker = None


def get_speaker() -> Speaker:
    global _speaker_instance
    if _speaker_instance is None:
        _speaker_instance = Speaker()
    return _speaker_instance


def speak(text: str):
    """Convenience function: speak text asynchronously."""
    get_speaker().speak(text)


def speak_sync(text: str):
    """Convenience function: speak text and wait for completion."""
    get_speaker().speak_sync(text)
