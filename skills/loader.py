"""
============================================================
J.A.R.V.I.S. — Skill Loader
Registers all skills with the brain.
============================================================
"""

import logging
log = logging.getLogger("jarvis.skills")


def load_all_skills(brain):
    """Import and register all skill modules with the brain."""

    skill_modules = [
        ("skills.greeting",       "Greeting & Status"),
        ("skills.apps",           "App Control"),
        ("skills.system_control", "System Control"),
        ("skills.media",          "Media & Music"),
        ("skills.web_info",       "Web & Information"),
        ("skills.reminders",      "Reminders"),
        ("skills.files",          "File Operations"),
        ("skills.settings",       "Settings"),
        ("ai.qwen",               "AI / Qwen"),
    ]

    loaded = []
    failed = []

    for module_path, name in skill_modules:
        try:
            import importlib
            module = importlib.import_module(module_path)
            if hasattr(module, "register"):
                module.register(brain)
                loaded.append(name)
                log.info("✓ Skill loaded: %s", name)
            else:
                log.warning("No register() function in %s", module_path)
        except ImportError as e:
            failed.append(name)
            log.warning("Could not load skill '%s': %s", name, e)
        except Exception as e:
            failed.append(name)
            log.error("Error loading skill '%s': %s", name, e)

    log.info("Skills loaded: %d success, %d failed", len(loaded), len(failed))
    if failed:
        log.warning("Failed skills (non-critical): %s", ", ".join(failed))

    return loaded, failed
