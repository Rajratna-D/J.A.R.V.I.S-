"""
============================================================
J.A.R.V.I.S. — Logging Setup
============================================================
Configures console (colourised) + rotating file logging.
Log files rotate at 5 MB with 3 backups to prevent disk bloat.
"""

import logging
import logging.handlers
import sys
from config import Config


def setup_logging(level=logging.INFO):
    """Configure logging: console (colour) + rotating file."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_fmt = "%H:%M:%S"

    # ── Rotating file handler (5 MB per file, keep 3 backups) ──
    log_file = Config.logs_dir / "jarvis.log"
    file_handler = logging.handlers.RotatingFileHandler(
        str(log_file),
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(fmt, date_fmt))

    # ── Console handler (encoding-safe) ────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    try:
        from colorama import Fore, Style, init
        init(autoreset=True)

        class ColourFormatter(logging.Formatter):
            COLOURS = {
                logging.DEBUG:    Fore.CYAN,
                logging.INFO:     Fore.GREEN,
                logging.WARNING:  Fore.YELLOW,
                logging.ERROR:    Fore.RED,
                logging.CRITICAL: Fore.MAGENTA,
            }
            def format(self, record):
                colour = self.COLOURS.get(record.levelno, "")
                record.levelname = f"{colour}{record.levelname}{Style.RESET_ALL}"
                return super().format(record)

        console_handler.setFormatter(ColourFormatter(fmt, date_fmt))
    except ImportError:
        console_handler.setFormatter(logging.Formatter(fmt, date_fmt))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Avoid duplicate handlers on re-import
    if not root.handlers:
        root.addHandler(file_handler)
        root.addHandler(console_handler)

    # Suppress noisy third-party loggers
    for name in ["whisper", "urllib3", "httpx", "httpcore", "PIL", "comtypes"]:
        logging.getLogger(name).setLevel(logging.WARNING)
