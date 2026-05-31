"""
============================================================
J.A.R.V.I.S. — Greeting & Status Skill
Layer 2: Core Brain (Starter Skills)
============================================================
Handles: greeting, goodbye, status, how are you
"""

from datetime import datetime
from core.brain import Intent, Response
from config import Config


def _time_of_day() -> str:
    h = datetime.now().hour
    if 5 <= h < 12:
        return "morning"
    elif 12 <= h < 17:
        return "afternoon"
    elif 17 <= h < 21:
        return "evening"
    else:
        return "night"


def handle_greeting(intent: Intent) -> Response:
    tod = _time_of_day()
    name = Config.username
    responses = [
        f"Good {tod}, {name}. All systems are online. How can I assist you?",
        f"Hello, {name}. JARVIS at your service.",
        f"Good {tod}, {name}. What can I do for you?",
        f"At your service, {name}.",
    ]
    import random
    return Response(text=random.choice(responses))


def handle_status(intent: Intent) -> Response:
    import psutil
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    responses = [
        f"All systems nominal, {Config.username}. CPU at {cpu:.0f}%, RAM usage {ram.percent:.0f}%. Ready for your commands.",
        f"Running smoothly, {Config.username}. {cpu:.0f}% processor load, {ram.percent:.0f}% memory in use.",
    ]
    import random
    return Response(text=random.choice(responses), data={"cpu": cpu, "ram": ram.percent})


def handle_time(intent: Intent) -> Response:
    now = datetime.now()
    time_str = now.strftime("%I:%M %p").lstrip("0")
    return Response(text=f"The time is {time_str}, {Config.username}.", data={"time": time_str})


def handle_date(intent: Intent) -> Response:
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    return Response(text=f"Today is {date_str}.", data={"date": date_str})


def handle_goodbye(intent: Intent) -> Response:
    return Response(
        text=f"Goodbye, {Config.username}. JARVIS signing off.",
        data={"action": "exit"}
    )


def register(brain):
    """Register all greeting/status skill handlers."""
    brain.register_skill("greeting", handle_greeting)
    brain.register_skill("status", handle_status)
    brain.register_skill("time", handle_time)
    brain.register_skill("date", handle_date)
    brain.register_skill("goodbye", handle_goodbye)
