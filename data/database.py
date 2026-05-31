"""
============================================================
J.A.R.V.I.S. — Database Manager
Layer 0: Project Foundation
============================================================
Initialises and manages the SQLite database.
Tables: reminders, command_history, settings_store
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from config import Config

log = logging.getLogger("jarvis.db")


def get_connection() -> sqlite3.Connection:
    """Return a thread-safe SQLite connection."""
    conn = sqlite3.connect(
        str(Config.db_path),
        check_same_thread=False,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # Better concurrency
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

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

    # ── Session Notes (persistent Qwen memory, Phase 2) ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            role        TEXT    NOT NULL,   -- user | assistant
            content     TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
            session_id  TEXT    NOT NULL DEFAULT 'default'
        )
    """)

    conn.commit()
    conn.close()
    log.info("Database initialised at %s", Config.db_path)


# ── Reminder helpers ──────────────────────────────────────
def add_reminder(task: str, remind_at: datetime) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO reminders (task, remind_at) VALUES (?, ?)",
        (task, remind_at.isoformat())
    )
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def get_pending_reminders():
    conn = get_connection()
    now = datetime.now().isoformat()
    rows = conn.execute(
        "SELECT * FROM reminders WHERE fired=0 AND cancelled=0 AND remind_at <= ?",
        (now,)
    ).fetchall()
    conn.close()
    return rows


def mark_reminder_fired(reminder_id: int):
    conn = get_connection()
    conn.execute("UPDATE reminders SET fired=1 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


def get_upcoming_reminders(limit: int = 5):
    conn = get_connection()
    now = datetime.now().isoformat()
    rows = conn.execute(
        "SELECT * FROM reminders WHERE fired=0 AND cancelled=0 AND remind_at > ? ORDER BY remind_at LIMIT ?",
        (now, limit)
    ).fetchall()
    conn.close()
    return rows


# ── Command history helpers ───────────────────────────────
def log_command(user_input: str, jarvis_resp: str, intent: str = "", source: str = "voice"):
    conn = get_connection()
    conn.execute(
        "INSERT INTO command_history (user_input, jarvis_resp, intent, source) VALUES (?, ?, ?, ?)",
        (user_input, jarvis_resp, intent, source)
    )
    conn.commit()
    conn.close()


def get_recent_commands(limit: int = 20):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM command_history ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return rows


# ── Timer helpers ─────────────────────────────────────────
def add_timer(name: str, duration_s: int, end_time: datetime) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO timers (name, duration_s, end_time) VALUES (?, ?, ?)",
        (name, duration_s, end_time.isoformat())
    )
    tid = cur.lastrowid
    conn.commit()
    conn.close()
    return tid


def get_active_timers():
    conn = get_connection()
    now = datetime.now().isoformat()
    rows = conn.execute(
        "SELECT * FROM timers WHERE fired=0 AND cancelled=0 ORDER BY end_time",
    ).fetchall()
    conn.close()
    return rows


def get_due_timers():
    conn = get_connection()
    now = datetime.now().isoformat()
    rows = conn.execute(
        "SELECT * FROM timers WHERE fired=0 AND cancelled=0 AND end_time <= ?",
        (now,)
    ).fetchall()
    conn.close()
    return rows


def mark_timer_fired(timer_id: int):
    conn = get_connection()
    conn.execute("UPDATE timers SET fired=1 WHERE id=?", (timer_id,))
    conn.commit()
    conn.close()


def cancel_timer(timer_id: int = None, cancel_all: bool = False):
    conn = get_connection()
    if cancel_all:
        conn.execute("UPDATE timers SET cancelled=1 WHERE fired=0 AND cancelled=0")
    elif timer_id:
        conn.execute("UPDATE timers SET cancelled=1 WHERE id=?", (timer_id,))
    conn.commit()
    conn.close()
