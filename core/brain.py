"""
============================================================
J.A.R.V.I.S. — Intent Parser & Command Router (Brain)
Layer 2: Core Brain
============================================================
Classifies voice/text commands into structured Intents,
then routes them to the correct skill handler.

Architecture:
  raw text → IntentParser → Intent → CommandRouter → Response
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any

log = logging.getLogger("jarvis.brain")


# ══════════════════════════════════════════════════════════
# Intent dataclass — output of the parser
# ══════════════════════════════════════════════════════════
@dataclass
class Intent:
    category: str                        # e.g. "open_app", "volume", "weather"
    raw_text: str                        # original user input
    params: Dict[str, Any] = field(default_factory=dict)   # extracted params
    confidence: float = 1.0

    def __repr__(self):
        return f"<Intent category={self.category!r} params={self.params}>"


# ══════════════════════════════════════════════════════════
# Response dataclass — output of the router
# ══════════════════════════════════════════════════════════
@dataclass
class Response:
    text: str                            # What JARVIS says
    success: bool = True
    data: Dict[str, Any] = field(default_factory=dict)   # Extra HUD data

    def __repr__(self):
        return f"<Response text={self.text!r} success={self.success}>"


# ══════════════════════════════════════════════════════════
# Intent Patterns (regex-based, fast, zero AI cost)
# ══════════════════════════════════════════════════════════
# Format: (compiled_regex, intent_category, param_extractor_fn)
# Patterns are checked in order — first match wins.

def _extract_app(m) -> dict:
    """Extract app name from match groups."""
    return {"app_name": (m.group(1) or "").strip().lower()}

def _extract_number(m) -> dict:
    """Extract a numeric value."""
    try:
        return {"value": int(m.group(1))}
    except (IndexError, ValueError):
        return {"value": None}

def _extract_query(m) -> dict:
    return {"query": (m.group(1) or "").strip()}

def _extract_task_time(m) -> dict:
    return {"task": (m.group(1) or "").strip(), "time_str": (m.group(2) or "").strip()}

def _extract_task_duration(m) -> dict:
    return {"task": (m.group(1) or "").strip(), "duration_str": (m.group(2) or "").strip()}

def _extract_timer(m) -> dict:
    name = (m.group(1) or "Timer").strip()
    duration = (m.group(2) or "").strip()
    if not duration:
        # Try reverse — "set a timer for 10 minutes"
        duration = (m.group(1) or "").strip()
        name = "Timer"
    return {"name": name, "duration_str": duration}


INTENT_PATTERNS = [
    # ── Greetings ─────────────────────────────────────────
    (re.compile(r"\b(hello|hey|hi|good morning|good afternoon|good evening|howdy)\b", re.I),
     "greeting", lambda m: {}),

    # ── Goodbye / Exit ────────────────────────────────────
    # NOTE: 'quit <app>' and 'close <app>' are handled by close_app (line below)
    # These patterns only match bare goodbye words (not followed by an app name)
    (re.compile(r"\b(goodbye|bye|shutdown jarvis|close jarvis|stop jarvis)\b", re.I),
     "goodbye", lambda m: {}),
    # Bare 'exit' or 'quit' alone = goodbye; with app name = close_app (handled below)
    (re.compile(r"^(?:exit|quit)\s*$", re.I),
     "goodbye", lambda m: {}),

    # ── How are you ───────────────────────────────────────
    (re.compile(r"\b(how are you|how.s it going|you okay)\b", re.I),
     "status", lambda m: {}),

    # ── System Stats (must come before generic status) ───────
    (re.compile(r"\b(system stats|system status|system info|how.s my (?:pc|computer|system)|system status report)\b", re.I),
     "stats_all", lambda m: {}),

    # ── Status (generic) ─────────────────────────────────────
    (re.compile(r"\b(status report|how.s (?:everything|jarvis))\b", re.I),
     "status", lambda m: {}),

    # ── Time / Date ───────────────────────────────────────
    (re.compile(r"\b(what.s the time|what time is it|current time|tell me the time)\b", re.I),
     "time", lambda m: {}),
    (re.compile(r"\b(what.s the date|what.s today|today.s date|what day is it)\b", re.I),
     "date", lambda m: {}),

    # ── Open Website (MUST be before Open App to prioritize websites over apps) ──
    (re.compile(r"\b(?:open|go to|visit)\s+(youtube|google|facebook|twitter|reddit|gmail|github)\b", re.I),
     "open_website", lambda m: {"website": m.group(1)}),
    (re.compile(r"\b(?:open|go to|visit)\s+([a-z0-9\-]+\.[a-z]{2,6}(?:\.[a-z]{2})?)\b", re.I),
     "open_website", lambda m: {"website": m.group(1)}),

    # ── Open App ──────────────────────────────────────────
    (re.compile(r"\b(?:open|launch|start|run|fire up)\s+(.+)", re.I),
     "open_app", _extract_app),

    # ── Close App ─────────────────────────────────────────
    (re.compile(r"\b(?:close|kill|quit|terminate|exit)\s+(.+)", re.I),
     "close_app", _extract_app),

    # ── Switch App ────────────────────────────────────────
    (re.compile(r"\b(?:switch to|focus|go to|bring up)\s+(.+)", re.I),
     "switch_app", _extract_app),

    # ── Window Management ─────────────────────────────────
    (re.compile(r"\b(?:snap|move)\s+(?:\w+\s+)?(?:to the\s+)?(left|right|full|fullscreen|maximize|minimise|minimize|restore)\b", re.I),
     "window_snap", lambda m: {"direction": m.group(1).lower()}),
    (re.compile(r"\b(maximize|maximise|full ?screen)\b", re.I),
     "window_snap", lambda m: {"direction": "maximize"}),
    (re.compile(r"\b(minimize|minimise)\b", re.I),
     "window_snap", lambda m: {"direction": "minimize"}),
    (re.compile(r"\b(restore|unmaximize|unminimize)\b", re.I),
     "window_snap", lambda m: {"direction": "restore"}),

    # ── List Running Apps ─────────────────────────────────
    (re.compile(r"\b(what.s running|list apps|show apps|what apps are open)\b", re.I),
     "list_apps", lambda m: {}),

    # ── Volume ────────────────────────────────────────────
    (re.compile(r"\bset volume\s+(?:to\s+)?(\d+)\s*%?\b", re.I),
     "volume_set", _extract_number),
    (re.compile(r"\b(volume up|increase volume|louder|turn up)\b", re.I),
     "volume_up", lambda m: {}),
    (re.compile(r"\b(volume down|decrease volume|quieter|lower volume|turn down)\b", re.I),
     "volume_down", lambda m: {}),
    (re.compile(r"\b(mute|silence|shut up volume)\b", re.I),
     "volume_mute", lambda m: {}),
    (re.compile(r"\b(unmute|restore volume|un-?mute)\b", re.I),
     "volume_unmute", lambda m: {}),

    # ── Brightness ────────────────────────────────────────
    (re.compile(r"\bset brightness\s+(?:to\s+)?(\d+)\s*%?\b", re.I),
     "brightness_set", _extract_number),
    (re.compile(r"\b(increase brightness|brighter|turn up brightness)\b", re.I),
     "brightness_up", lambda m: {}),
    (re.compile(r"\b(decrease brightness|dim|dimmer|lower brightness|reduce brightness)\b", re.I),
     "brightness_down", lambda m: {}),

    # ── Power / Lock ──────────────────────────────────────
    (re.compile(r"\b(lock|lock the (?:computer|pc|screen)|lock up)\b", re.I),
     "lock_screen", lambda m: {}),
    (re.compile(r"\b(sleep|put to sleep|hibernate)\b", re.I),
     "sleep", lambda m: {}),
    (re.compile(r"\b(restart|reboot)\b", re.I),
     "restart", lambda m: {}),
    (re.compile(r"\b(shut ?down|power off|turn off)\b", re.I),
     "shutdown", lambda m: {}),

    # ── Web & Information ─────────────────────────────────────
    (re.compile(r"\b(search|google|look up|find out)\b\s+(.+)", re.I),
     "web_search", lambda m: {"query": m.group(2)}),
    (re.compile(r"\b(what is|who is|tell me about)\b\s+(.+)", re.I),
     "what_is", lambda m: {"query": m.group(2)}),
    (re.compile(r"\bweather\b(?!.*\b(?:tomorrow|next)\b).*(?:in|at)\s+(.+)", re.I),
     "weather", lambda m: {"location": m.group(1)}),

    # ── Timers (MUST be before generic cancel) ──────────────
    (re.compile(r"\bset\s+a?\s*(.+?)\s*timer\s+(?:for\s+)?(.+)", re.I),
     "timer_set", _extract_timer),
    (re.compile(r"\bset\s+a?\s*timer\s+(?:for\s+)?(.+)", re.I),
     "timer_set", lambda m: {"name": "Timer", "duration_str": m.group(1).strip()}),
    (re.compile(r"\b(cancel|stop|clear)\s+(?:the\s+)?timer", re.I),
     "timer_cancel", lambda m: {}),
    (re.compile(r"\bhow\s+(?:long|much time)\s+(?:is|does)?\s+(?:the\s+)?timer\b", re.I),
     "timer_status", lambda m: {}),

    # ── Cancel / Confirm (AFTER timer_cancel) ────────────────
    (re.compile(r"\b(abort|cancel|never mind|stop that|no)\b", re.I),
     "cancel", lambda m: {}),
    (re.compile(r"\b(yes|confirm|do it|sure|proceed|go ahead)\b", re.I),
     "confirm", lambda m: {}),

    # ── Screenshots ───────────────────────────────────────
    (re.compile(r"\b(take a screenshot|screenshot|capture screen|screen ?shot)\b", re.I),
     "screenshot_full", lambda m: {}),
    (re.compile(r"\b(screenshot this window|capture this window|window screenshot)\b", re.I),
     "screenshot_window", lambda m: {}),

    # ── Clipboard ─────────────────────────────────────────
    (re.compile(r"\b(what.s in my clipboard|read clipboard|clipboard content|paste content)\b", re.I),
     "clipboard_read", lambda m: {}),

    # ── System Stats ─────────────────────────────────────
    (re.compile(r"\b(cpu|processor)\s+(?:usage|stats?|status|load)\b", re.I),
     "stats_cpu", lambda m: {}),
    (re.compile(r"\b(ram|memory)\s+(?:usage|stats?|status)\b", re.I),
     "stats_ram", lambda m: {}),
    (re.compile(r"\b(disk|storage|drive)\s+(?:usage|stats?|status|space)\b", re.I),
     "stats_disk", lambda m: {}),

    # ── Reminders ─────────────────────────────────────────
    (re.compile(r"\bremind me\s+(?:to\s+)?(.+?)\s+(?:at|in)\s+(.+)", re.I),
     "reminder_set", _extract_task_time),
    (re.compile(r"\bset\s+a?\s*reminder\s+(?:to\s+)?(.+?)\s+(?:at|in)\s+(.+)", re.I),
     "reminder_set", _extract_task_time),

    # ── YouTube (MUST be before generic media_play) ──────────
    (re.compile(r"\bplay\s+(.+?)\s+on\s+youtube\b", re.I),
     "youtube_play", _extract_query),
    (re.compile(r"\byoutube\s+(.+)", re.I),
     "youtube_play", _extract_query),
    (re.compile(r"\bplay\s+(?!(?:music|song|songs|tracks?|audio)\b)(.+)", re.I),
     "youtube_play", lambda m: {"query": m.group(1).strip()}),

    # ── Media ─────────────────────────────────────────────
    (re.compile(r"\b(play music|start music|resume music|play)\b", re.I),
     "media_play", lambda m: {}),
    (re.compile(r"\b(pause|pause music)\b", re.I),
     "media_pause", lambda m: {}),
    (re.compile(r"\b(stop music|stop playing)\b", re.I),
     "media_stop", lambda m: {}),
    (re.compile(r"\b(skip|next|next song|next track)\b", re.I),
     "media_next", lambda m: {}),
    (re.compile(r"\b(previous|prev|previous song|previous track|go back)\b", re.I),
     "media_prev", lambda m: {}),

    # ── Web Search ────────────────────────────────────────
    (re.compile(r"\bsearch\s+(?:for\s+)?(.+?)\s+on\s+youtube\b", re.I),
     "youtube_search", _extract_query),
    (re.compile(r"\bsearch\s+(?:youtube\s+for\s+)?(.+?)\s+on\s+youtube\b", re.I),
     "youtube_search", _extract_query),
    (re.compile(r"\bsearch\s+(?:for\s+|google\s+for\s+)?(.+)", re.I),
     "web_search", _extract_query),
    (re.compile(r"\bgoogle\s+(.+)", re.I),
     "web_search", _extract_query),

    # ── Weather ───────────────────────────────────────────
    (re.compile(r"\b(weather|what.s the weather|how.s the weather|will it rain|forecast)\b", re.I),
     "weather", lambda m: {}),

    # ── News ──────────────────────────────────────────────
    (re.compile(r"\b(?:tech|technology)\s+news\b", re.I),
     "news", lambda m: {"category": "technology"}),
    (re.compile(r"\b(?:sports?)\s+news\b", re.I),
     "news", lambda m: {"category": "sports"}),
    (re.compile(r"\b(?:india|indian)\s+news\b", re.I),
     "news", lambda m: {"category": "india"}),
    (re.compile(r"\b(?:business|finance|financial)\s+news\b", re.I),
     "news", lambda m: {"category": "business"}),
    (re.compile(r"\b(news|headlines|what.s happening|what.s in the news)\b", re.I),
     "news", lambda m: {"category": "general"}),

    # ── Quick Facts ───────────────────────────────────────
    (re.compile(r"\bconvert\s+(\d+(?:\.\d+)?)\s+(\w+)\s+to\s+(\w+)\b", re.I),
     "currency_convert", lambda m: {
         "amount": float(m.group(1)),
         "from_currency": m.group(2).upper(),
         "to_currency": m.group(3).upper()
     }),
    (re.compile(r"\bwhat\s+is\s+(.+)", re.I),
     "what_is", _extract_query),
    (re.compile(r"\bwho\s+is\s+(.+)", re.I),
     "what_is", _extract_query),
    (re.compile(r"\btell me about\s+(.+)", re.I),
     "what_is", _extract_query),
    (re.compile(r"\bdefine\s+(.+)", re.I),
     "what_is", _extract_query),

    # ── AI / Code ─────────────────────────────────────────
    (re.compile(r"\b(?:write|create|generate|make)\s+(?:a\s+|an\s+)?(?:python|javascript|java|c\+\+|script|code|program|function)\s*.+", re.I),
     "ai_code", lambda m: {"prompt": m.group(0).strip()}),
    (re.compile(r"\b(?:explain|debug|fix)\s+(?:this\s+)?(?:error|code|bug|issue)\b", re.I),
     "ai_debug", lambda m: {"prompt": m.group(0).strip()}),
    (re.compile(r"\b(?:write|draft|compose)\s+(?:a\s+|an\s+)?(?:email|letter|message|report|essay)\b", re.I),
     "ai_write", lambda m: {"prompt": m.group(0).strip()}),
    (re.compile(r"\b(?:summarize|summarise|summary of|sum up)\b", re.I),
     "ai_summarize", lambda m: {}),
    (re.compile(r"\b(?:rephrase|rewrite|paraphrase)\b", re.I),
     "ai_rephrase", lambda m: {}),
    (re.compile(r"\b(?:explain|describe)\s+(.+)\s+(?:simply|in simple terms|for a beginner)\b", re.I),
     "ai_explain", _extract_query),

    # ── Conversational Mode ───────────────────────────────
    (re.compile(r"\b(let.s talk|chat mode|conversation mode|talk to me|let.s chat)\b", re.I),
     "conversation_start", lambda m: {}),
    (re.compile(r"\b(end conversation|stop talking|command mode|back to commands|exit chat)\b", re.I),
     "conversation_end", lambda m: {}),

    # ── File Operations (Phase 2 — stub for routing) ──────
    (re.compile(r"\bfind\s+(?:all\s+)?(.+?)\s+(?:in|on|from)\s+(.+)", re.I),
     "file_search", lambda m: {"query": m.group(1), "location": m.group(2)}),
    (re.compile(r"\bcreate\s+(?:a\s+)?folder\s+(?:called\s+)?(.+?)(?:\s+on\s+(.+))?$", re.I),
     "folder_create", lambda m: {"name": m.group(1), "location": m.group(2) or "Desktop"}),

    # ── Settings ─────────────────────────────────────────
    (re.compile(r"\b(open settings|show settings|settings|preferences)\b", re.I),
     "open_settings", lambda m: {}),
]


# ══════════════════════════════════════════════════════════
# Intent Parser
# ══════════════════════════════════════════════════════════
class IntentParser:
    """
    Fast regex-based intent classifier.
    Checks patterns in priority order, returns first match.
    Falls back to 'ai_query' for unmatched commands.
    """

    def __init__(self):
        self._patterns = INTENT_PATTERNS
        log.info("IntentParser initialised with %d patterns", len(self._patterns))

    def parse(self, text: str) -> Intent:
        """Parse raw text → Intent."""
        text_clean = text.strip()

        for pattern, category, extractor in self._patterns:
            m = pattern.search(text_clean)
            if m:
                try:
                    params = extractor(m)
                except Exception as e:
                    log.warning("Param extraction error for %s: %s", category, e)
                    params = {}

                intent = Intent(
                    category=category,
                    raw_text=text_clean,
                    params=params,
                )
                log.info("Intent matched: %s | params=%s", category, params)
                return intent

        # No match — send to AI
        log.info("No intent match — routing to AI: %r", text_clean)
        return Intent(
            category="ai_query",
            raw_text=text_clean,
            params={"prompt": text_clean},
            confidence=0.5,
        )


# ══════════════════════════════════════════════════════════
# Skill Registry & Command Router
# ══════════════════════════════════════════════════════════
class CommandRouter:
    """
    Routes Intent → registered skill handler → Response.
    Skills register themselves via register_skill().
    """

    def __init__(self):
        self._skills: Dict[str, Callable[[Intent], Response]] = {}
        log.info("CommandRouter initialised")

    def register(self, intent_category: str, handler: Callable[[Intent], Response]):
        """Register a handler function for an intent category."""
        self._skills[intent_category] = handler
        log.debug("Registered skill handler for '%s'", intent_category)

    def route(self, intent: Intent) -> Response:
        """
        Dispatch intent to the correct skill handler.
        Falls back to a helpful message if no handler registered.
        """
        handler = self._skills.get(intent.category)

        if handler is None:
            log.warning("No handler registered for intent '%s'", intent.category)
            return Response(
                text=f"I know you want to {intent.category.replace('_', ' ')}, but that skill isn't loaded yet, Sir.",
                success=False,
            )

        try:
            response = handler(intent)
            log.info("Skill executed: %s → %r", intent.category, response.text[:60])
            return response
        except Exception as e:
            log.exception("Skill handler error for '%s': %s", intent.category, e)
            return Response(
                text=f"Something went wrong with that, Sir. {str(e)[:100]}",
                success=False,
            )


# ══════════════════════════════════════════════════════════
# The Brain — combines parser + router
# ══════════════════════════════════════════════════════════
class Brain:
    """
    JARVIS core: parses commands and routes them to skills.
    Handles confirmation flow and conversational mode state.
    """

    def __init__(self):
        self.parser = IntentParser()
        self.router = CommandRouter()
        log.info("Brain online ✓")

    def process(self, text: str, session=None) -> Response:
        """
        Process a raw text command end-to-end.
        session: optional SessionMemory for context-aware routing
        """
        if not text or not text.strip():
            return Response(text="I didn't catch that, Sir.", success=False)

        # ── Check for pending confirmation ────────────────
        if session and session.has_pending_confirmation():
            pending = session.pop_pending_confirmation()
            intent = self.parser.parse(text)

            if intent.category == "confirm":
                # Execute the confirmed action
                confirm_intent = Intent(
                    category=pending["action"],
                    raw_text=text,
                    params={**pending.get("data", {}), "confirmed": True},
                )
                return self.router.route(confirm_intent)
            elif intent.category == "cancel":
                return Response(text="Understood. Cancelling that, Sir.")
            else:
                # Treat as cancel if something else said
                return Response(text="Request cancelled. What else can I do for you?")

        # ── In conversation mode → route to AI ───────────
        if session and session.is_conversation_mode():
            intent = self.parser.parse(text)
            if intent.category == "conversation_end":
                session.exit_conversation_mode()
                return Response(text="Returning to command mode, Sir. How can I assist you?")
            # Everything else in chat mode goes to AI
            intent = Intent(
                category="ai_chat",
                raw_text=text,
                params={"prompt": text},
            )
            return self.router.route(intent)

        # ── Normal command mode ───────────────────────────
        intent = self.parser.parse(text)
        return self.router.route(intent)

    def register_skill(self, category: str, handler: Callable):
        """Register a skill handler."""
        self.router.register(category, handler)


# ── Module-level singleton ────────────────────────────────
_brain: Brain = None


def get_brain() -> Brain:
    global _brain
    if _brain is None:
        _brain = Brain()
    return _brain
