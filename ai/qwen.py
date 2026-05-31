"""
============================================================
J.A.R.V.I.S. — AI / Qwen 2.5 Coder Integration
Layer 6: AI-Powered Tasks (FR-19, FR-20, FR-21)
============================================================
Integrates with Ollama local API for:
- Code generation & debugging
- Natural language tasks (emails, summaries)
- Conversational mode with context
- General question answering

Degrades gracefully if Ollama is not running.
"""

import logging
import pyperclip
import requests as req_lib

from core.brain import Intent, Response
from config import Config

log = logging.getLogger("jarvis.ai")

JARVIS_SYSTEM_PROMPT = """You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), 
the AI assistant created for your user. You are intelligent, helpful, and slightly formal — 
like the AI from Iron Man. Keep responses concise and practical. 
When writing code, include comments. When answering questions, be direct and accurate.
Address the user as Sir."""


# ══════════════════════════════════════════════════════════
# Ollama Client
# ══════════════════════════════════════════════════════════
class OllamaClient:
    """
    Thin wrapper around the Ollama HTTP API.
    Handles connection errors gracefully.
    """

    def __init__(self):
        self.base_url = Config.ollama_host
        self.model = Config.ollama_model
        self.timeout = Config.ai_timeout

    def is_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            resp = req_lib.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def chat(self, messages: list[dict], stream: bool = False) -> str:
        """
        Send a chat request to Ollama.
        messages: list of {"role": "user"|"assistant"|"system", "content": "..."}
        Returns the response text or raises an exception.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 1024,
            }
        }

        resp = req_lib.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=self.timeout
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"].strip()

    def generate(self, prompt: str) -> str:
        """Simple one-shot generation."""
        return self.chat([{"role": "user", "content": prompt}])


# ── Singleton ─────────────────────────────────────────────
_client: OllamaClient = None


def get_client() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


def _ai_unavailable_response() -> Response:
    return Response(
        text=f"AI systems are offline, {Config.username}. Please ensure Ollama is running with the {Config.ollama_model} model.",
        success=False,
        data={"ai_available": False}
    )


# ══════════════════════════════════════════════════════════
# FR-19: Code Assistance
# ══════════════════════════════════════════════════════════
def handle_ai_code(intent: Intent) -> Response:
    prompt = intent.params.get("prompt", intent.raw_text)
    client = get_client()

    if not client.is_available():
        return _ai_unavailable_response()

    try:
        messages = [
            {"role": "system", "content": JARVIS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        response_text = client.chat(messages)
        # Print full response to console (for code with syntax)
        print(f"\n{'='*60}\n🤖 JARVIS AI Response:\n{'='*60}\n{response_text}\n{'='*60}\n")
        # Speak a brief summary
        lines = response_text.split("\n")
        brief = next((l for l in lines if l.strip() and not l.startswith("```")), "Here's the code, Sir.")
        return Response(
            text=f"Done, {Config.username}. {brief[:100]}. Full response displayed in the terminal.",
            data={"ai_response": response_text, "type": "code"}
        )
    except Exception as e:
        log.error("AI code error: %s", e)
        return Response(text=f"AI code generation failed, Sir: {str(e)[:80]}", success=False)


# ══════════════════════════════════════════════════════════
# FR-20: Natural Language Tasks
# ══════════════════════════════════════════════════════════
def handle_ai_write(intent: Intent) -> Response:
    prompt = intent.params.get("prompt", intent.raw_text)
    client = get_client()

    if not client.is_available():
        return _ai_unavailable_response()

    try:
        messages = [
            {"role": "system", "content": JARVIS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        response_text = client.chat(messages)
        print(f"\n{'='*60}\n🤖 JARVIS AI:\n{'='*60}\n{response_text}\n{'='*60}\n")
        # Copy to clipboard for convenience
        pyperclip.copy(response_text)
        return Response(
            text=f"I've drafted that for you, {Config.username}. It's also been copied to your clipboard.",
            data={"ai_response": response_text}
        )
    except Exception as e:
        log.error("AI write error: %s", e)
        return Response(text=f"AI writing failed, Sir: {str(e)[:80]}", success=False)


def handle_ai_summarize(intent: Intent) -> Response:
    client = get_client()
    if not client.is_available():
        return _ai_unavailable_response()

    # Get text from clipboard
    clipboard_text = pyperclip.paste()
    if not clipboard_text:
        return Response(text="Your clipboard is empty, Sir. Copy the text you want summarised first.", success=False)

    try:
        prompt = f"Summarise the following text concisely:\n\n{clipboard_text[:3000]}"
        messages = [
            {"role": "system", "content": JARVIS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        response_text = client.chat(messages)
        print(f"\n{'='*60}\n🤖 JARVIS Summary:\n{'='*60}\n{response_text}\n{'='*60}\n")
        return Response(
            text=response_text[:300] + ("..." if len(response_text) > 300 else ""),
            data={"ai_response": response_text}
        )
    except Exception as e:
        return Response(text=f"Summarisation failed, Sir: {str(e)[:80]}", success=False)


def handle_ai_debug(intent: Intent) -> Response:
    client = get_client()
    if not client.is_available():
        return _ai_unavailable_response()

    clipboard_text = pyperclip.paste()
    prompt = intent.raw_text
    if clipboard_text:
        prompt += f"\n\nCode/error from clipboard:\n{clipboard_text[:2000]}"

    try:
        messages = [
            {"role": "system", "content": JARVIS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        response_text = client.chat(messages)
        print(f"\n{'='*60}\n🤖 JARVIS Debug:\n{'='*60}\n{response_text}\n{'='*60}\n")
        return Response(
            text=f"Analysis complete, {Config.username}. Check the terminal for the full diagnosis.",
            data={"ai_response": response_text}
        )
    except Exception as e:
        return Response(text=f"Debug analysis failed, Sir: {str(e)[:80]}", success=False)


def handle_ai_explain(intent: Intent) -> Response:
    query = intent.params.get("query", intent.raw_text)
    client = get_client()

    if not client.is_available():
        return _ai_unavailable_response()

    try:
        messages = [
            {"role": "system", "content": JARVIS_SYSTEM_PROMPT},
            {"role": "user", "content": f"Explain this simply in 2-3 sentences: {query}"}
        ]
        response_text = client.chat(messages)
        return Response(text=response_text[:400], data={"ai_response": response_text})
    except Exception as e:
        return Response(text=f"Explanation failed, Sir: {str(e)[:80]}", success=False)


def handle_ai_rephrase(intent: Intent) -> Response:
    client = get_client()
    if not client.is_available():
        return _ai_unavailable_response()

    clipboard_text = pyperclip.paste()
    if not clipboard_text:
        return Response(text="Copy the text to rephrase to your clipboard first, Sir.", success=False)

    try:
        messages = [
            {"role": "system", "content": JARVIS_SYSTEM_PROMPT},
            {"role": "user", "content": f"Rephrase the following more formally and professionally:\n\n{clipboard_text[:1500]}"}
        ]
        response_text = client.chat(messages)
        pyperclip.copy(response_text)
        print(f"\n{'='*60}\n🤖 Rephrased:\n{'='*60}\n{response_text}\n{'='*60}\n")
        return Response(
            text=f"Rephrased and copied to clipboard, {Config.username}.",
            data={"ai_response": response_text}
        )
    except Exception as e:
        return Response(text=f"Rephrasing failed, Sir: {str(e)[:80]}", success=False)


# ══════════════════════════════════════════════════════════
# FR-21: Conversational Mode
# ══════════════════════════════════════════════════════════
def handle_conversation_start(intent: Intent) -> Response:
    return Response(
        text=f"Entering conversational mode, {Config.username}. I'm listening. Say 'end conversation' to return to command mode.",
        data={"mode": "conversation"}
    )


def handle_conversation_end(intent: Intent) -> Response:
    return Response(
        text=f"Returning to command mode, {Config.username}.",
        data={"mode": "command"}
    )


def handle_ai_chat(intent: Intent, session=None) -> Response:
    """Handler for in-conversation messages. Called by Brain in conversation mode."""
    prompt = intent.params.get("prompt", intent.raw_text)
    client = get_client()

    if not client.is_available():
        return _ai_unavailable_response()

    try:
        messages = [{"role": "system", "content": JARVIS_SYSTEM_PROMPT}]

        # Add session history for context
        if session:
            messages.extend(session.get_qwen_messages())
        messages.append({"role": "user", "content": prompt})

        response_text = client.chat(messages)
        # Keep response to 300 chars for voice
        voice_resp = response_text[:300] + ("..." if len(response_text) > 300 else "")
        if len(response_text) > 300:
            print(f"\n{'='*60}\n🤖 JARVIS:\n{response_text}\n{'='*60}\n")

        return Response(text=voice_resp, data={"ai_response": response_text})
    except Exception as e:
        log.error("AI chat error: %s", e)
        return Response(text=f"AI response failed, Sir: {str(e)[:80]}", success=False)


# ── General AI query (fallback) ───────────────────────────
def handle_ai_query(intent: Intent) -> Response:
    """Catch-all for anything that doesn't match a skill — route to Qwen."""
    prompt = intent.params.get("prompt", intent.raw_text)
    client = get_client()

    if not client.is_available():
        return Response(
            text=f"I didn't understand that command, {Config.username}. And my AI systems are offline. Please try a different command.",
            success=False
        )

    try:
        messages = [
            {"role": "system", "content": JARVIS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        response_text = client.chat(messages)
        voice_resp = response_text[:300] + ("..." if len(response_text) > 300 else "")
        if len(response_text) > 300:
            print(f"\n{'='*60}\n🤖 JARVIS AI:\n{response_text}\n{'='*60}\n")
        return Response(text=voice_resp, data={"ai_response": response_text})
    except Exception as e:
        log.error("AI query error: %s", e)
        return Response(
            text=f"I'm not sure what you mean, {Config.username}. Could you rephrase that?",
            success=False
        )


def register(brain):
    """Register all AI skill handlers."""
    brain.register_skill("ai_code", handle_ai_code)
    brain.register_skill("ai_write", handle_ai_write)
    brain.register_skill("ai_summarize", handle_ai_summarize)
    brain.register_skill("ai_debug", handle_ai_debug)
    brain.register_skill("ai_explain", handle_ai_explain)
    brain.register_skill("ai_rephrase", handle_ai_rephrase)
    brain.register_skill("ai_chat", handle_ai_chat)
    brain.register_skill("ai_query", handle_ai_query)
    brain.register_skill("conversation_start", handle_conversation_start)
    brain.register_skill("conversation_end", handle_conversation_end)
