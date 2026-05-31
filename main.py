import sys
import time
import logging
import threading

# ── Force UTF-8 encoding for Windows terminals ────────────
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# ── Setup logging first ───────────────────────────────────
from core.logger import setup_logging
setup_logging()
log = logging.getLogger("jarvis.main")

# ── Core imports ──────────────────────────────────────────
from config import Config
from core.brain import get_brain
from core.session import get_session
from data.database import init_db, log_command
from skills.loader import load_all_skills
from voice.speaker import speak, get_speaker
from voice.listener import get_listener
from voice.hotkey import get_hotkey_manager


# ══════════════════════════════════════════════════════════
# JARVIS Application
# ══════════════════════════════════════════════════════════
class JARVIS:
    """Main JARVIS application controller."""

    def __init__(self):
        self.brain = get_brain()
        self.session = get_session()
        self.speaker = get_speaker()
        self.listener = get_listener()
        self.hotkey_mgr = get_hotkey_manager()
        self._running = False
        self._listening = False
        self._listen_lock = threading.Lock()
        self._hud = None

    def boot(self):
        """Initialise all systems and speak boot greeting."""
        print("\n" + "=" * 60)
        print("  J.A.R.V.I.S. — Initialising...")
        print("=" * 60)

        # ── Database ──────────────────────────────────────
        log.info("Initialising database...")
        init_db()

        # ── Load Skills ───────────────────────────────────
        log.info("Loading skill modules...")
        loaded, failed = load_all_skills(self.brain)
        print(f"\n  Skills loaded: {', '.join(loaded)}")
        if failed:
            print(f"  Skills skipped (missing deps): {', '.join(failed)}")

        # ── Preload Whisper in background ─────────────────
        log.info("Preloading Whisper model in background...")
        self.listener.preload_model()

        # ── Register Hotkey ───────────────────────────────
        self.hotkey_mgr.register(callback=self._on_hotkey_press)

        # ── Boot Greeting ─────────────────────────────────
        self._running = True
        self._boot_greeting()

        print("\n" + "=" * 60)
        print(f"  JARVIS ONLINE | User: {Config.username}")
        print(f"  Hotkey: [{Config.hotkey.upper()}] to activate voice")
        print(f"  Type commands below or press the hotkey to speak")
        print("  Type 'quit' or say 'goodbye' to exit")
        print("=" * 60 + "\n")

    def _boot_greeting(self):
        """Speak the Iron Man-style boot greeting."""
        from datetime import datetime
        h = datetime.now().hour
        if 5 <= h < 12:
            tod = "morning"
        elif 12 <= h < 17:
            tod = "afternoon"
        elif 17 <= h < 21:
            tod = "evening"
        else:
            tod = "night"

        greeting = (
            f"All systems online. "
            f"Good {tod}, {Config.username}. "
            f"J.A.R.V.I.S. is ready. How can I assist you?"
        )
        # Update HUD
        self._set_hud_state("idle")
        self._set_hud_response(greeting)
        speak(greeting)

    def _on_hotkey_press(self):
        """Called when Alt+J is pressed."""
        with self._listen_lock:
            if self._listening:
                return
            self._listening = True

        try:
            self._set_hud_state("listening")
            speak("Listening, Sir.")
            time.sleep(0.3)

            text = self.listener.listen()

            if text:
                print(f"\n  You: {text}")
                self._set_hud_state("processing")
                threading.Thread(target=self._process_and_respond, args=(text, "voice"), daemon=True).start()
            else:
                self._set_hud_state("error")
                speak("I didn't catch that, Sir. Please try again.")
                time.sleep(1)
                self._set_hud_state("idle")
        finally:
            with self._listen_lock:
                self._listening = False

    def _process_and_respond(self, text: str, source: str = "text"):
        """Core: parse intent → route to skill → speak response."""
        response = self.brain.process(text, session=self.session)

        # Handle pending confirmation
        if response.data.get("needs_confirmation"):
            self.session.set_pending_confirmation(
                action=response.data.get("action"),
                data=response.data
            )

        # Handle conversation mode transitions
        if response.data.get("mode") == "conversation":
            self.session.enter_conversation_mode()
            self._set_hud_mode("CONVERSATION")
        elif response.data.get("mode") == "command":
            self.session.exit_conversation_mode()
            self._set_hud_mode("COMMAND")

        # Update HUD before speaking
        self._set_hud_state("speaking")
        self._set_hud_response(response.text)
        self._set_hud_last_cmd(text)

        # Speak the response (blocks background thread, keeps HUD in 'speaking' state)
        from voice.speaker import speak_sync
        speak_sync(response.text)

        # Back to idle after speaking is completely finished
        self._set_hud_state("idle")

        # Store in session memory
        self.session.add_turn(text, response.text, intent="")

        # Log to DB
        log_command(text, response.text, source=source)

        # Check for exit signal
        if response.data.get("action") == "exit":
            time.sleep(2)
            self._running = False

    # ── HUD helpers (thread-safe) ─────────────────────────
    def _set_hud_state(self, state: str):
        try:
            from ui.hud import update_hud_state, JarvisState
            state_map = {
                "idle": JarvisState.IDLE,
                "listening": JarvisState.LISTENING,
                "processing": JarvisState.PROCESSING,
                "speaking": JarvisState.SPEAKING,
                "error": JarvisState.ERROR,
            }
            update_hud_state(state_map.get(state, JarvisState.IDLE))
        except Exception:
            pass

    def _set_hud_response(self, text: str):
        try:
            from ui.hud import update_hud_response
            update_hud_response(text)
        except Exception:
            pass

    def _set_hud_last_cmd(self, cmd: str):
        try:
            from ui.hud import get_hud
            hud = get_hud()
            if hud:
                from PyQt6.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(hud, "set_last_command",
                                         Qt.ConnectionType.QueuedConnection,
                                         cmd)
        except Exception:
            pass

    def _set_hud_mode(self, mode: str):
        try:
            from ui.hud import get_hud
            hud = get_hud()
            if hud:
                from PyQt6.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(hud, "set_mode",
                                         Qt.ConnectionType.QueuedConnection,
                                         mode)
        except Exception:
            pass

    def _text_input_loop(self):
        """Allow text commands from the terminal as an alternative to voice."""
        while self._running:
            try:
                user_input = input("  > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "q"):
                    from voice.speaker import speak_sync
                    speak_sync(f"Goodbye, {Config.username}. JARVIS signing off.")
                    time.sleep(1.5)
                    self._running = False
                    break
                self._set_hud_state("processing")
                threading.Thread(target=self._process_and_respond, args=(user_input, "text"), daemon=True).start()
            except KeyboardInterrupt:
                print("\n")
                from voice.speaker import speak_sync
                speak_sync(f"Goodbye, {Config.username}.")
                time.sleep(1.5)
                self._running = False
                break
            except EOFError:
                break

    def run(self):
        """Main application loop with HUD."""
        # Try to launch HUD
        hud_available = False
        try:
            from PyQt6.QtWidgets import QApplication
            from ui.hud import launch_hud, JarvisState
            hud_available = True
        except ImportError:
            log.warning("PyQt6 not available — running without HUD")

        if hud_available:
            # Boot in a background thread; HUD runs in main thread
            boot_thread = threading.Thread(target=self._boot_with_hud, daemon=True)
            boot_thread.start()

            # Launch HUD (blocks main thread with Qt event loop)
            from PyQt6.QtWidgets import QApplication
            from ui.hud import launch_hud, get_hud_signals
            app = QApplication(sys.argv)
            self._hud = launch_hud(jarvis_app=self)
            self._set_hud_state("idle")
            
            # Connect HUD text input directly to processing thread
            get_hud_signals().text_command.connect(
                lambda text: threading.Thread(
                    target=self._process_and_respond, 
                    args=(text, "text"), 
                    daemon=True
                ).start()
            )
            
            app.exec()
        else:
            # Headless mode
            self.boot()
            self._text_input_loop()

        self.shutdown()

    def _boot_with_hud(self):
        """Boot sequence that runs in background while HUD initialises."""
        time.sleep(1.5)   # Wait for HUD to fade in
        self.boot()
        # Start text input in yet another thread (so main thread = Qt)
        input_thread = threading.Thread(target=self._text_input_loop, daemon=True)
        input_thread.start()

    def shutdown(self):
        """Graceful shutdown."""
        log.info("Shutting down JARVIS...")
        self._running = False
        self.hotkey_mgr.unregister()
        print("\n  JARVIS offline. Goodbye.\n")


# ══════════════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    try:
        jarvis = JARVIS()
        jarvis.run()
    except KeyboardInterrupt:
        print("\n\nJARVIS interrupted. Shutting down...")
        sys.exit(0)
    except Exception as e:
        log.exception("Fatal error: %s", e)
        print(f"\n  Fatal error: {e}")
        sys.exit(1)
