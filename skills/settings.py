"""
============================================================
J.A.R.V.I.S. — Settings Skill
Layer 8: Settings Panel
============================================================
Handles: open settings, configure JARVIS on the fly
"""

import os
import subprocess
from pathlib import Path
from core.brain import Intent, Response
from config import Config, ROOT_DIR


def handle_open_settings(intent: Intent) -> Response:
    """Open the settings.yaml in the default text editor."""
    settings_path = ROOT_DIR / "config" / "settings.yaml"
    try:
        os.startfile(str(settings_path))
        return Response(
            text=f"Opening settings file, {Config.username}. Restart JARVIS to apply changes.",
            data={"file": str(settings_path)}
        )
    except Exception as e:
        return Response(text=f"Couldn't open settings, Sir: {e}", success=False)


def register(brain):
    brain.register_skill("open_settings", handle_open_settings)
