"""
============================================================
J.A.R.V.I.S. — Reminders Skill
Layer 7: Notifications & Reminders (FR-22, FR-23)
============================================================
Handles: set reminders, persistent SQLite-backed scheduling
"""

import logging
import threading
import time
from datetime import datetime, timedelta

import dateparser

from core.brain import Intent, Response
from config import Config
from data.database import add_reminder, get_pending_reminders, mark_reminder_fired

log = logging.getLogger("jarvis.skills.reminders")


# ══════════════════════════════════════════════════════════
# FR-22: Reminders
# ══════════════════════════════════════════════════════════
def handle_reminder_set(intent: Intent) -> Response:
    task = intent.params.get("task", "").strip()
    time_str = intent.params.get("time_str", "").strip()

    if not task or not time_str:
        return Response(
            text="I need to know what to remind you about and when, Sir.",
            success=False
        )

    # Parse time using dateparser (handles "in 30 minutes", "at 9pm", "tomorrow morning")
    remind_at = dateparser.parse(
        time_str,
        settings={
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": False,
        }
    )

    if not remind_at:
        return Response(
            text=f"I couldn't understand the time '{time_str}', Sir. Try 'in 30 minutes' or 'at 9 PM'.",
            success=False
        )

    if remind_at <= datetime.now():
        return Response(
            text=f"That time has already passed, Sir. Please give me a future time.",
            success=False
        )

    rid = add_reminder(task, remind_at)

    # Format for voice
    time_fmt = remind_at.strftime("%I:%M %p").lstrip("0")
    date_fmt = remind_at.strftime("%B %d") if remind_at.date() != datetime.now().date() else "today"

    return Response(
        text=f"Reminder set, {Config.username}. I'll remind you to {task} at {time_fmt} {date_fmt}.",
        data={"reminder_id": rid, "task": task, "remind_at": remind_at.isoformat()}
    )


# ══════════════════════════════════════════════════════════
# Background Reminder Scheduler
# ══════════════════════════════════════════════════════════
class ReminderScheduler:
    """
    Runs in a background thread. Checks for due reminders every 30 seconds.
    When a reminder fires: speaks it + sends a Windows toast notification.
    """

    def __init__(self):
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="ReminderScheduler"
        )
        self._running = False

    def start(self):
        self._running = True
        self._thread.start()
        log.info("Reminder scheduler started")

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            try:
                self._check_reminders()
            except Exception as e:
                log.error("Reminder check error: %s", e)
            time.sleep(30)   # Check every 30 seconds

    def _check_reminders(self):
        pending = get_pending_reminders()
        for reminder in pending:
            try:
                mark_reminder_fired(reminder["id"])
                task = reminder["task"]

                # Speak the reminder
                from voice.speaker import speak
                speak(f"Reminder, {Config.username}: {task}")

                # Windows toast notification
                try:
                    from plyer import notification
                    notification.notify(
                        title="JARVIS Reminder",
                        message=task,
                        timeout=15,
                    )
                except Exception as e:
                    log.warning("Toast notification failed: %s", e)

                log.info("Reminder fired: %s", task)

            except Exception as e:
                log.error("Error processing reminder %s: %s", reminder["id"], e)


# ── Singleton scheduler ───────────────────────────────────
_scheduler: ReminderScheduler = None


def get_scheduler() -> ReminderScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = ReminderScheduler()
    return _scheduler


def register(brain):
    """Register reminder skill handlers and start scheduler."""
    brain.register_skill("reminder_set", handle_reminder_set)

    # Start background scheduler
    get_scheduler().start()
