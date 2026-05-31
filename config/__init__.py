"""
============================================================
J.A.R.V.I.S. â€” Config Loader
Layer 0: Project Foundation
============================================================
Central configuration: loads settings.yaml + .env
Provides a singleton Config object accessible across all modules.
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# ── Resolve project root ──────────────────────────────────
# __file__ = d:\JARVIS 2\config\__init__.py → .parent = config/ → .parent = project root
ROOT_DIR = Path(__file__).parent.parent.resolve()
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"

# ── Create required directories ───────────────────────────
for d in [DATA_DIR, LOGS_DIR, ROOT_DIR / "screenshots"]:
    d.mkdir(parents=True, exist_ok=True)

# â”€â”€ Load .env â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
env_path = ROOT_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv(ROOT_DIR / ".env.example")   # fallback, no real keys


# â”€â”€ Load settings.yaml â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _load_yaml(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


_settings = _load_yaml(CONFIG_DIR / "settings.yaml")


# â”€â”€ Helper: deep-get from nested dict â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _get(d: dict, *keys, default=None):
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, default)
        else:
            return default
    return d


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Config â€” single flat access surface
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class _Config:
    # --- User ---
    username: str       = _get(_settings, "user", "name", default="Sir")
    first_boot: bool    = _get(_settings, "user", "first_boot", default=True)

    # --- Voice ---
    voice_enabled: bool = _get(_settings, "voice", "enabled", default=True)
    voice_speed: int    = _get(_settings, "voice", "speed", default=175)
    voice_volume: float = _get(_settings, "voice", "volume", default=0.9)
    whisper_model: str  = _get(_settings, "voice", "whisper_model", default="base")

    # --- Activation ---
    hotkey: str              = _get(_settings, "activation", "hotkey", default="alt+j")
    text_hotkey: str         = _get(_settings, "activation", "text_hotkey", default="ctrl+space")
    wake_word_enabled: bool  = _get(_settings, "activation", "wake_word_enabled", default=False)
    wake_word: str           = _get(_settings, "activation", "wake_word", default="jarvis")
    listen_timeout: int      = _get(_settings, "activation", "listen_timeout", default=6)

    # --- System ---
    screenshot_folder: str          = _get(_settings, "system", "screenshot_folder",
                                           default=str(Path.home() / "Pictures" / "JARVIS"))
    default_browser: str            = _get(_settings, "system", "default_browser", default="chrome")
    always_on_top: bool             = _get(_settings, "system", "always_on_top", default=True)
    notifications_enabled: bool     = _get(_settings, "system", "notifications_enabled", default=True)

    # --- AI ---
    ollama_host: str    = os.getenv("OLLAMA_HOST",
                                    _get(_settings, "ai", "ollama_host",
                                         default="http://localhost:11434"))
    ollama_model: str   = os.getenv("OLLAMA_MODEL",
                                    _get(_settings, "ai", "model",
                                         default="qwen2.5-coder:7b"))
    ai_context_turns: int = _get(_settings, "ai", "context_turns", default=10)
    ai_timeout: int     = _get(_settings, "ai", "timeout", default=60)

    # --- UI ---
    theme: str          = _get(_settings, "ui", "theme", default="classic_blue")
    boot_animation: bool = _get(_settings, "ui", "boot_animation", default=True)

    # --- API Keys (from .env only) ---
    news_api_key: str       = os.getenv("NEWS_API_KEY", "")
    weather_api_key: str    = os.getenv("WEATHER_API_KEY", "")
    exchange_api_key: str   = os.getenv("EXCHANGE_API_KEY", "")

    # --- Weather ---
    weather_city: str   = os.getenv("WEATHER_CITY",
                                    _get(_settings, "weather", "location", default=""))
    weather_units: str  = _get(_settings, "weather", "units", default="metric")

    # --- App aliases ---
    app_aliases: dict   = _get(_settings, "apps", "aliases", default={})

    # --- Paths ---
    root_dir: Path      = ROOT_DIR
    data_dir: Path      = DATA_DIR
    logs_dir: Path      = LOGS_DIR
    db_path: Path       = DATA_DIR / "jarvis.db"

    def save_setting(self, section: str, key: str, value):
        """Persist a setting back to settings.yaml."""
        global _settings
        if section not in _settings:
            _settings[section] = {}
        _settings[section][key] = value
        with open(CONFIG_DIR / "settings.yaml", "w", encoding="utf-8") as f:
            yaml.dump(_settings, f, default_flow_style=False, allow_unicode=True)
        # Update live attribute
        attr = f"{section}_{key}" if section else key
        if hasattr(self, attr):
            setattr(self, attr, value)


# â”€â”€ Singleton â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Config = _Config()
