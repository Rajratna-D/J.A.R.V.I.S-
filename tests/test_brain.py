"""
============================================================
J.A.R.V.I.S. — Intent Parser Unit Tests
Layer 10: Testing & QA
============================================================
Tests all major intent pattern categories with multiple phrasings.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from core.brain import IntentParser, Intent


class TestIntentParser(unittest.TestCase):
    def setUp(self):
        self.parser = IntentParser()

    def _assert_intent(self, text, expected_category):
        intent = self.parser.parse(text)
        self.assertEqual(
            intent.category, expected_category,
            f"'{text}' → expected {expected_category!r}, got {intent.category!r}"
        )

    # ── Greetings ────────────────────────────────────────
    def test_greeting_hello(self):
        for cmd in ["hello", "hey", "hi", "good morning", "good evening"]:
            self._assert_intent(cmd, "greeting")

    # ── Status ───────────────────────────────────────────
    def test_status(self):
        for cmd in ["how are you", "status report", "how's jarvis"]:
            self._assert_intent(cmd, "status")

    # ── Time/Date ─────────────────────────────────────────
    def test_time(self):
        for cmd in ["what time is it", "what's the time", "tell me the time"]:
            self._assert_intent(cmd, "time")

    def test_date(self):
        for cmd in ["what's the date", "what's today", "what day is it"]:
            self._assert_intent(cmd, "date")

    # ── App Control ───────────────────────────────────────
    def test_open_app(self):
        for cmd in ["open chrome", "launch spotify", "start notepad", "fire up VS Code"]:
            self._assert_intent(cmd, "open_app")

    def test_close_app(self):
        for cmd in ["close chrome", "kill notepad", "quit spotify"]:
            self._assert_intent(cmd, "close_app")

    def test_switch_app(self):
        for cmd in ["switch to VS Code", "focus chrome", "bring up notepad"]:
            self._assert_intent(cmd, "switch_app")

    # ── Volume ────────────────────────────────────────────
    def test_volume_set(self):
        intent = self.parser.parse("set volume to 70%")
        self.assertEqual(intent.category, "volume_set")
        self.assertEqual(intent.params.get("value"), 70)

    def test_volume_up(self):
        for cmd in ["volume up", "increase volume", "louder", "turn up"]:
            self._assert_intent(cmd, "volume_up")

    def test_volume_down(self):
        for cmd in ["volume down", "quieter", "lower volume"]:
            self._assert_intent(cmd, "volume_down")

    def test_mute(self):
        self._assert_intent("mute", "volume_mute")

    def test_unmute(self):
        self._assert_intent("unmute", "volume_unmute")

    # ── Brightness ────────────────────────────────────────
    def test_brightness_set(self):
        intent = self.parser.parse("set brightness to 80%")
        self.assertEqual(intent.category, "brightness_set")
        self.assertEqual(intent.params.get("value"), 80)

    def test_brightness_up(self):
        for cmd in ["increase brightness", "brighter"]:
            self._assert_intent(cmd, "brightness_up")

    def test_brightness_down(self):
        for cmd in ["dim the screen", "decrease brightness", "dimmer"]:
            self._assert_intent(cmd, "brightness_down")

    # ── Power ─────────────────────────────────────────────
    def test_lock(self):
        for cmd in ["lock", "lock the computer", "lock the screen", "lock up"]:
            self._assert_intent(cmd, "lock_screen")

    def test_sleep(self):
        for cmd in ["sleep", "put to sleep"]:
            self._assert_intent(cmd, "sleep")

    def test_shutdown(self):
        for cmd in ["shut down", "shutdown", "power off"]:
            self._assert_intent(cmd, "shutdown")

    def test_restart(self):
        for cmd in ["restart", "reboot"]:
            self._assert_intent(cmd, "restart")

    def test_cancel(self):
        for cmd in ["abort", "cancel", "never mind", "no"]:
            self._assert_intent(cmd, "cancel")

    def test_confirm(self):
        for cmd in ["yes", "confirm", "do it", "sure"]:
            self._assert_intent(cmd, "confirm")

    # ── Screenshots ───────────────────────────────────────
    def test_screenshot_full(self):
        for cmd in ["take a screenshot", "screenshot", "capture screen"]:
            self._assert_intent(cmd, "screenshot_full")

    def test_clipboard(self):
        for cmd in ["what's in my clipboard", "read clipboard"]:
            self._assert_intent(cmd, "clipboard_read")

    # ── System Stats ─────────────────────────────────────
    def test_stats_cpu(self):
        self._assert_intent("cpu usage", "stats_cpu")

    def test_stats_all(self):
        for cmd in ["system status", "system stats", "how's my pc"]:
            self._assert_intent(cmd, "stats_all")

    # ── Timers ───────────────────────────────────────────
    def test_timer_set(self):
        intent = self.parser.parse("set a timer for 25 minutes")
        self.assertEqual(intent.category, "timer_set")

    def test_timer_cancel(self):
        self._assert_intent("cancel the timer", "timer_cancel")

    # ── Reminders ────────────────────────────────────────
    def test_reminder_set(self):
        intent = self.parser.parse("remind me to check email in 30 minutes")
        self.assertEqual(intent.category, "reminder_set")

    # ── Media ─────────────────────────────────────────────
    def test_media_play(self):
        self._assert_intent("play music", "media_play")

    def test_media_pause(self):
        self._assert_intent("pause", "media_pause")

    def test_media_next(self):
        for cmd in ["skip", "next song", "next track"]:
            self._assert_intent(cmd, "media_next")

    # ── YouTube ───────────────────────────────────────────
    def test_youtube_play(self):
        intent1 = self.parser.parse("play Bohemian Rhapsody on YouTube")
        self.assertEqual(intent1.category, "youtube_play")
        self.assertIn("bohemian rhapsody", intent1.params.get("query", "").lower())

        intent2 = self.parser.parse("play Bohemian Rhapsody")
        self.assertEqual(intent2.category, "youtube_play")
        self.assertEqual(intent2.params.get("query"), "Bohemian Rhapsody")

        intent3 = self.parser.parse("play perfect by ed sheeran")
        self.assertEqual(intent3.category, "youtube_play")
        self.assertEqual(intent3.params.get("query"), "perfect by ed sheeran")

    # ── Web ───────────────────────────────────────────────
    def test_web_search(self):
        for cmd in ["search for python tutorials", "google python"]:
            self._assert_intent(cmd, "web_search")

    def test_open_website(self):
        for cmd in ["open youtube", "go to google", "visit reddit", "open wikipedia.org", "visit github.com"]:
            self._assert_intent(cmd, "open_website")

    # ── Weather ───────────────────────────────────────────
    def test_weather(self):
        for cmd in ["what's the weather", "will it rain", "weather forecast"]:
            self._assert_intent(cmd, "weather")

    # ── News ─────────────────────────────────────────────
    def test_news_general(self):
        for cmd in ["what's in the news", "headlines"]:
            self._assert_intent(cmd, "news")

    def test_news_tech(self):
        self._assert_intent("tech news", "news")

    # ── Quick Facts ───────────────────────────────────────
    def test_what_is(self):
        for cmd in ["what is python", "who is Elon Musk", "define entropy"]:
            self._assert_intent(cmd, "what_is")

    def test_currency(self):
        intent = self.parser.parse("convert 100 USD to INR")
        self.assertEqual(intent.category, "currency_convert")
        self.assertEqual(intent.params.get("amount"), 100.0)
        self.assertEqual(intent.params.get("from_currency"), "USD")
        self.assertEqual(intent.params.get("to_currency"), "INR")

    # ── Conversation ──────────────────────────────────────
    def test_conversation_start(self):
        for cmd in ["let's talk", "chat mode", "conversation mode"]:
            self._assert_intent(cmd, "conversation_start")

    def test_conversation_end(self):
        for cmd in ["end conversation", "command mode", "back to commands"]:
            self._assert_intent(cmd, "conversation_end")

    # ── Goodbye ───────────────────────────────────────────
    def test_goodbye(self):
        for cmd in ["goodbye", "bye", "exit", "quit"]:
            self._assert_intent(cmd, "goodbye")

    # ── Fallback to AI ───────────────────────────────────
    def test_ai_fallback(self):
        intent = self.parser.parse("xyzzy completely unrecognised command blah blah")
        self.assertEqual(intent.category, "ai_query")


if __name__ == "__main__":
    unittest.main(verbosity=2)
