"""
============================================================
J.A.R.V.I.S. — Module Import & Config Test
Run this to verify all modules load correctly before main.py
============================================================
Usage: python test_imports.py
"""

import sys
import os

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("  JARVIS — Module Import Test")
print("=" * 60)

errors = []
warnings = []


def test(name, fn):
    try:
        fn()
        print(f"  [OK] {name}")
    except ImportError as e:
        warnings.append(f"{name}: {e}")
        print(f"  [WARN] {name} -- missing dep: {e}")
    except Exception as e:
        errors.append(f"{name}: {e}")
        print(f"  [FAIL] {name} -- ERROR: {e}")


# ── Config & DB ───────────────────────────────────────────
test("config.py", lambda: __import__("config"))
test("data.database", lambda: __import__("data.database"))

# ── Core ──────────────────────────────────────────────────
test("core.brain (IntentParser)", lambda: (
    __import__("core.brain", fromlist=["get_brain"]),
))
test("core.session (SessionMemory)", lambda: (
    __import__("core.session", fromlist=["get_session"]),
))
test("core.logger", lambda: (
    __import__("core.logger", fromlist=["setup_logging"]),
))

# ── Voice ─────────────────────────────────────────────────
test("voice.speaker (pyttsx3)", lambda: (
    __import__("voice.speaker", fromlist=["speak"]),
))
test("voice.hotkey (keyboard)", lambda: (
    __import__("voice.hotkey", fromlist=["get_hotkey_manager"]),
))
test("voice.listener (whisper+sounddevice)", lambda: (
    __import__("voice.listener", fromlist=["listen"]),
))

# ── Skills ────────────────────────────────────────────────
test("skills.greeting", lambda: __import__("skills.greeting"))
test("skills.apps (pygetwindow+fuzzywuzzy)", lambda: __import__("skills.apps"))
test("skills.system_control (pycaw+psutil)", lambda: __import__("skills.system_control"))
test("skills.media (keyboard)", lambda: __import__("skills.media"))
test("skills.web_info (requests+wikipedia)", lambda: __import__("skills.web_info"))
test("skills.reminders (dateparser)", lambda: __import__("skills.reminders"))
test("skills.files", lambda: __import__("skills.files"))
test("skills.settings", lambda: __import__("skills.settings"))
test("skills.loader", lambda: __import__("skills.loader"))

# ── AI ────────────────────────────────────────────────────
test("ai.qwen (ollama)", lambda: __import__("ai.qwen"))

# ── Intent Parser basic test ──────────────────────────────
print("\n  Testing Intent Parser...")
from core.brain import IntentParser

parser = IntentParser()
test_commands = [
    ("hello", "greeting"),
    ("what time is it", "time"),
    ("open chrome", "open_app"),
    ("set volume to 50", "volume_set"),
    ("take a screenshot", "screenshot_full"),
    ("set a timer for 25 minutes", "timer_set"),
    ("what is python", "what_is"),
    ("search for python tutorials", "web_search"),
    ("let's talk", "conversation_start"),
    ("remind me to check email in 30 minutes", "reminder_set"),
]

intent_ok = 0
for cmd, expected in test_commands:
    intent = parser.parse(cmd)
    ok = intent.category == expected
    if ok:
        intent_ok += 1
    else:
        print(f"    [FAIL] '{cmd}' -> expected {expected!r}, got {intent.category!r}")

if intent_ok == len(test_commands):
    print(f"    [OK] All {intent_ok}/{len(test_commands)} intent patterns correct")
else:
    print(f"    [WARN] {intent_ok}/{len(test_commands)} intent patterns correct")

# ── Summary ───────────────────────────────────────────────
print("\n" + "=" * 60)
if errors:
    print(f"  [FAIL] {len(errors)} ERROR(S) -- JARVIS may not start:")
    for e in errors:
        print(f"     - {e}")
elif warnings:
    print(f"  [WARN] {len(warnings)} WARNING(S) -- Some features may be limited:")
    for w in warnings:
        print(f"     - {w}")
    print("\n  [OK] Core systems OK -- JARVIS should start.")
else:
    print("  [OK] ALL MODULES LOADED SUCCESSFULLY")
    print("  [OK] JARVIS is ready to run: python main.py")
print("=" * 60)
