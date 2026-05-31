"""
============================================================
J.A.R.V.I.S. — Session Memory
Layer 2: Core Brain
============================================================
Maintains in-session conversation context.
Used to pass history to Qwen for multi-turn conversations.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from config import Config


@dataclass
class Turn:
    """A single exchange: user → JARVIS."""
    user_input: str
    jarvis_response: str
    intent: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_qwen_messages(self) -> list[dict]:
        """Format as OpenAI-style message dicts for Qwen context."""
        msgs = []
        if self.user_input:
            msgs.append({"role": "user", "content": self.user_input})
        if self.jarvis_response:
            msgs.append({"role": "assistant", "content": self.jarvis_response})
        return msgs


class SessionMemory:
    """
    Ring buffer of recent conversation turns.
    Provides context for Qwen conversational mode.
    """

    def __init__(self, max_turns: int = None):
        self.max_turns = max_turns or Config.ai_context_turns
        self._turns: deque[Turn] = deque(maxlen=self.max_turns)
        self.mode: str = "command"          # "command" | "conversation"
        self.pending_confirmation: Optional[dict] = None   # For shutdown/restart

    def add_turn(self, user_input: str, jarvis_response: str, intent: str = ""):
        """Add a completed exchange to memory."""
        self._turns.append(Turn(
            user_input=user_input,
            jarvis_response=jarvis_response,
            intent=intent,
        ))

    def get_history(self) -> list[Turn]:
        """Return all stored turns (oldest first)."""
        return list(self._turns)

    def get_qwen_messages(self, system_prompt: str = None) -> list[dict]:
        """
        Return message list formatted for Qwen/Ollama chat API.
        Includes optional system prompt + conversation history.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for turn in self._turns:
            messages.extend(turn.to_qwen_messages())
        return messages

    def clear(self):
        """Clear all memory (e.g. on 'end conversation')."""
        self._turns.clear()
        self.mode = "command"

    def enter_conversation_mode(self):
        self.mode = "conversation"

    def exit_conversation_mode(self):
        self.mode = "command"
        self._turns.clear()   # Fresh context when returning to commands

    def is_conversation_mode(self) -> bool:
        return self.mode == "conversation"

    def set_pending_confirmation(self, action: str, data: dict = None):
        """Store an action that needs voice confirmation (e.g. shutdown)."""
        self.pending_confirmation = {"action": action, "data": data or {}}

    def pop_pending_confirmation(self) -> Optional[dict]:
        """Retrieve and clear pending confirmation."""
        c = self.pending_confirmation
        self.pending_confirmation = None
        return c

    def has_pending_confirmation(self) -> bool:
        return self.pending_confirmation is not None

    def __len__(self) -> int:
        return len(self._turns)

    def __repr__(self) -> str:
        return f"<SessionMemory turns={len(self._turns)} mode={self.mode}>"


# ── Module-level singleton ────────────────────────────────
_session: SessionMemory = None


def get_session() -> SessionMemory:
    global _session
    if _session is None:
        _session = SessionMemory()
    return _session
