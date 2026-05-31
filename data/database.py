"""
============================================================
J.A.R.V.I.S. — Database Manager
Layer 0: Project Foundation
============================================================
Initialises and manages the SQLite database.
Tables: reminders, command_history, timers, conversation_history

Thread-safe: all operations are serialised through a module-level
lock, so multiple JARVIS threads (TTS, timers, command processing)
can safely access the database concurrently.
"""

import sqlite3
import logging
import threading
from contextlib import contextmanager
from datetime import datetime
from config import Config

log = logging.getLogger("jarvis.db")

# Module-level lock — serialises all DB access across threads
_db_lock = threading.Lock()


@contextmanager
def _connection():
    """
    Context manager for thread-safe database access.
    Acquires the lock, yields a connection, and guarantees
    cleanup (commit + close) even if an exception occurs.
    """
    with _db_lock:
        conn = sqlite3.connect(
            str(Config.db_path),
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with _connection() as conn:
        cursor = conn.cursor()

        # Enable WAL mode once (persists across connections)
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")

        # ── Reminders ─────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                task        TEXT    NOT NULL,
                remind_at   TEXT    NOT NULL,   -- ISO 8601 datetime string
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                fired       INTEGER NOT NULL DEFAULT 0,
                cancelled   INTEGER NOT NULL DEFAULT 0
            )
        """)

        # ── Command History ───────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_input  TEXT    NOT NULL,
                jarvis_resp TEXT,
                intent      TEXT,
                timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
                source      TEXT    DEFAULT 'voice'   -- voice | text | hotkey
            )
        """)

        # ── Timers ────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS timers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL DEFAULT 'Timer',
                duration_s  INTEGER NOT NULL,
                end_time    TEXT    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                fired       INTEGER NOT NULL DEFAULT 0,
                cancelled   INTEGER NOT NULL DEFAULT 0
            )
        """)

        # ── Conversation History (persistent Qwen memory) ────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                role        TEXT    NOT NULL,   -- user | assistant
                content     TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
                session_id  TEXT    NOT NULL DEFAULT 'default'
            )
        """)

    log.info("Database initialised at %s", Config.db_path)


# ══════════════════════════════════════════════════════════
# Reminder helpers
# ══════════════════════════════════════════════════════════
def add_reminder(task: str, remind_at: datetime) -> int:
    with _connection() as conn:
        cur = conn.execute(
            "INSERT INTO reminders (task, remind_at) VALUES (?, ?)",
            (task, remind_at.isoformat()),
        )
        return cur.lastrowid


def get_pending_reminders():
    with _connection() as conn:
        now = datetime.now().isoformat()
        return conn.execute(
            "SELECT * FROM reminders WHERE fired=0 AND cancelled=0 AND remind_at <= ?",
            (now,),
        ).fetchall()


def mark_reminder_fired(reminder_id: int):
    with _connection() as conn:
        conn.execute("UPDATE reminders SET fired=1 WHERE id=?", (reminder_id,))


def get_upcoming_reminders(limit: int = 5):
    with _connection() as conn:
        now = datetime.now().isoformat()
        return conn.execute(
            "SELECT * FROM reminders WHERE fired=0 AND cancelled=0 AND remind_at > ? ORDER BY remind_at LIMIT ?",
            (now, limit),
        ).fetchall()


# ══════════════════════════════════════════════════════════
# Command history helpers
# ══════════════════════════════════════════════════════════
def log_command(user_input: str, jarvis_resp: str, intent: str = "", source: str = "voice"):
    with _connection() as conn:
        conn.execute(
            "INSERT INTO command_history (user_input, jarvis_resp, intent, source) VALUES (?, ?, ?, ?)",
            (user_input, jarvis_resp, intent, source),
        )


def get_recent_commands(limit: int = 20):
    with _connection() as conn:
        return conn.execute(
            "SELECT * FROM command_history ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()


# ══════════════════════════════════════════════════════════
# Timer helpers
# ══════════════════════════════════════════════════════════
def add_timer(name: str, duration_s: int, end_time: datetime) -> int:
    with _connection() as conn:
        cur = conn.execute(
            "INSERT INTO timers (name, duration_s, end_time) VALUES (?, ?, ?)",
            (name, duration_s, end_time.isoformat()),
        )
        return cur.lastrowid


def get_active_timers():
    with _connection() as conn:
        return conn.execute(
            "SELECT * FROM timers WHERE fired=0 AND cancelled=0 ORDER BY end_time",
        ).fetchall()


def get_due_timers():
    with _connection() as conn:
        now = datetime.now().isoformat()
        return conn.execute(
            "SELECT * FROM timers WHERE fired=0 AND cancelled=0 AND end_time <= ?",
            (now,),
        ).fetchall()


def mark_timer_fired(timer_id: int):
    with _connection() as conn:
        conn.execute("UPDATE timers SET fired=1 WHERE id=?", (timer_id,))


def cancel_timer(timer_id: int = None, cancel_all: bool = False):
    with _connection() as conn:
        if cancel_all:
            conn.execute("UPDATE timers SET cancelled=1 WHERE fired=0 AND cancelled=0")
        elif timer_id:
            conn.execute("UPDATE timers SET cancelled=1 WHERE id=?", (timer_id,))
