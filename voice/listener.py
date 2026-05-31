"""
============================================================
J.A.R.V.I.S. — Voice Listener (STT)
Layer 1: Voice Pipeline
============================================================
Records audio from the microphone, detects silence,
and transcribes using OpenAI Whisper (fully local).
"""

import io
import logging
import tempfile
import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import whisper

from config import Config

log = logging.getLogger("jarvis.listener")

# ── Silence detection constants ────────────────────────────
SAMPLE_RATE     = 16000   # Hz — Whisper expects 16kHz
CHUNK_DURATION  = 0.5     # seconds per audio chunk
SILENCE_THRESH  = 500     # RMS energy below this = silence (int16 scale: 0–32767)
SILENCE_CHUNKS  = 3       # consecutive silent chunks after speech = stop recording
MAX_DURATION    = 15      # max recording seconds (safety cap)
WAIT_FOR_SPEECH = 12      # chunks (~6s) of silence before giving up waiting for speech


class Listener:
    """
    Microphone listener using sounddevice + Whisper.
    Loads the Whisper model once and keeps it in memory for fast transcription.
    """

    def __init__(self):
        self._model = None
        self._model_lock = threading.Lock()
        self._loading = False
        log.info("Listener created — Whisper model will load on first use")

    def _load_model(self):
        """Lazy-load Whisper model (only when first listen is triggered)."""
        with self._model_lock:
            if self._model is None:
                log.info("Loading Whisper '%s' model — this may take a moment...", Config.whisper_model)
                self._model = whisper.load_model(Config.whisper_model)
                log.info("Whisper model loaded ✓")

    def _rms(self, chunk: np.ndarray) -> float:
        """Calculate root-mean-square energy of an audio chunk."""
        return float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))

    def record_until_silence(self) -> np.ndarray | None:
        """
        Record from the default microphone.
        Stops automatically when the user stops speaking (silence detection).
        Returns a numpy int16 array at SAMPLE_RATE, or None on error.
        """
        chunks_per_second = int(1 / CHUNK_DURATION)
        chunk_samples = int(SAMPLE_RATE * CHUNK_DURATION)
        max_chunks = int(MAX_DURATION / CHUNK_DURATION)

        audio_chunks = []
        silent_count = 0
        got_speech = False
        pre_speech_silence = 0   # Track how long we wait before speech starts

        log.debug("Recording started — waiting for speech...")

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=chunk_samples,
            ) as stream:
                for _ in range(max_chunks):
                    chunk, _ = stream.read(chunk_samples)
                    chunk = chunk.flatten()
                    energy = self._rms(chunk)

                    if energy > SILENCE_THRESH:
                        got_speech = True
                        silent_count = 0
                        audio_chunks.append(chunk)
                    elif got_speech:
                        # Only count silence after we've heard speech
                        silent_count += 1
                        audio_chunks.append(chunk)  # include trailing silence (natural)
                        if silent_count >= SILENCE_CHUNKS:
                            log.debug("Silence detected — stopping recording")
                            break
                    else:
                        # No speech yet — give up after WAIT_FOR_SPEECH chunks
                        pre_speech_silence += 1
                        if pre_speech_silence >= WAIT_FOR_SPEECH:
                            log.debug("No speech detected within timeout — giving up")
                            break

        except Exception as e:
            log.error("Microphone error: %s", e)
            return None

        if not got_speech or not audio_chunks:
            log.debug("No speech detected")
            return None

        return np.concatenate(audio_chunks, axis=0)

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe a numpy audio array to text using Whisper.
        Returns the transcribed string (stripped, lowercased).
        """
        self._load_model()

        # Whisper expects float32 in range [-1, 1]
        audio_float = audio.astype(np.float32) / 32768.0

        try:
            result = self._model.transcribe(
                audio_float,
                language="en",
                fp16=False,                 # CPU-safe (fp16 only for CUDA)
                temperature=0,              # Greedy — most deterministic
                condition_on_previous_text=False,
            )
            text = result["text"].strip()
            log.info("Transcribed: '%s'", text)
            return text
        except Exception as e:
            log.error("Whisper transcription error: %s", e)
            return ""

    def listen(self) -> str:
        """
        Full listen cycle: record → transcribe → return text.
        Returns empty string if nothing was heard.
        """
        audio = self.record_until_silence()
        if audio is None:
            return ""
        return self.transcribe(audio)

    def preload_model(self):
        """Warm up the Whisper model in a background thread at startup."""
        t = threading.Thread(target=self._load_model, daemon=True, name="WhisperPreload")
        t.start()


# ── Module-level singleton ────────────────────────────────
_listener_instance: Listener = None


def get_listener() -> Listener:
    global _listener_instance
    if _listener_instance is None:
        _listener_instance = Listener()
    return _listener_instance


def listen() -> str:
    """Convenience: listen and return transcription."""
    return get_listener().listen()
