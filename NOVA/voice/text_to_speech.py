"""
voice/text_to_speech.py — Text-to-speech using pyttsx3 (offline, Windows SAPI).

Settings from config.json: voice.tts_rate, voice.tts_volume, voice.preferred_voice
"""

import pyttsx3
import threading
from utils.config_manager import get_config
from utils.logger import get_logger

logger = get_logger("tts")


class TextToSpeech:
    """Wraps pyttsx3 with thread lock so concurrent speak() calls do not clash."""

    def __init__(self):
        cfg = get_config()
        self._rate = cfg.get("voice.tts_rate", 175)
        self._volume = cfg.get("voice.tts_volume", 1.0)
        self._preferred = cfg.get("voice.preferred_voice", "female")
        self._lock = threading.Lock()
        self._engine = None
        self._init_engine()

    def _init_engine(self):
        """Create pyttsx3 engine and apply rate/volume/voice."""
        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self._rate)
            self._engine.setProperty("volume", self._volume)
            self._set_voice()
            logger.info("TTS engine ready.")
        except Exception as e:
            logger.error(f"TTS init failed: {e}")
            self._engine = None

    def _set_voice(self):
        """Pick first installed voice matching preferred gender."""
        if not self._engine:
            return
        voices = self._engine.getProperty("voices")
        for voice in voices:
            name = voice.name.lower()
            if self._preferred == "female" and any(w in name for w in ["zira", "hazel", "female", "woman"]):
                self._engine.setProperty("voice", voice.id)
                return
            if self._preferred == "male" and any(w in name for w in ["david", "mark", "male", "man"]):
                self._engine.setProperty("voice", voice.id)
                return

    def speak(self, text: str):
        """Speak text aloud (blocking until finished)."""
        if not text or not self._engine:
            return
        logger.info(f"NOVA says: {text}")
        with self._lock:
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                logger.error(f"TTS speak error: {e}")

    def set_rate(self, rate: int):
        """Adjust words-per-minute at runtime."""
        self._rate = rate
        if self._engine:
            self._engine.setProperty("rate", rate)


_tts = None


def get_tts() -> TextToSpeech:
    """Singleton TTS instance."""
    global _tts
    if _tts is None:
        _tts = TextToSpeech()
    return _tts
