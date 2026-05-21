"""
voice/speech_recognition_engine.py — Speech-to-text (STT).

Online: Google Speech Recognition (requires internet).
Offline fallback: Vosk (needs vosk-model folder in project root).
"""

import speech_recognition as sr
from utils.config_manager import get_config
from utils.logger import get_logger
from utils.helpers import is_online

logger = get_logger("stt")

# Normalise locale codes from config / CLI
LANGUAGE_MAP = {
    "en-in": "en-IN",
    "en-us": "en-US",
    "hi-in": "hi-IN",
    "fr-fr": "fr-FR",
    "de-de": "de-DE",
    "es-es": "es-ES",
    "ta-in": "ta-IN",
    "te-in": "te-IN",
}


class SpeechEngine:
    """Captures microphone audio and returns transcribed text."""

    def __init__(self, language: str = "en-IN"):
        cfg = get_config()
        self._timeout = cfg.get("voice.speech_timeout", 5)
        self._energy = cfg.get("voice.energy_threshold", 300)
        self.language = LANGUAGE_MAP.get(language.lower(), language)
        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = self._energy
        self._recognizer.dynamic_energy_threshold = True
        logger.info(f"Speech engine ready | Language: {self.language}")

    def set_language(self, lang_code: str):
        """Switch recognition language (e.g. after switch_language intent)."""
        self.language = LANGUAGE_MAP.get(lang_code.lower(), lang_code)
        logger.info(f"Language switched to: {self.language}")

    def listen(self) -> str | None:
        """Listen from mic and return recognized text, or None on failure/timeout."""
        with sr.Microphone() as source:
            logger.info("Listening...")
            self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self._recognizer.listen(source, timeout=self._timeout, phrase_time_limit=10)
            except sr.WaitTimeoutError:
                logger.debug("No speech detected (timeout).")
                return None

        # Online path — Google STT
        if is_online():
            try:
                text = self._recognizer.recognize_google(audio, language=self.language)
                logger.info(f"Heard (online): {text}")
                return text
            except sr.UnknownValueError:
                logger.debug("Could not understand audio.")
                return None
            except sr.RequestError as e:
                logger.warning(f"Google STT failed: {e}. Trying offline...")

        # Offline fallback — Vosk local model
        try:
            import vosk, json
            model_path = "vosk-model"
            import os
            if not os.path.exists(model_path):
                logger.error("Vosk model not found. Download from alphacephei.com/vosk/models")
                return None
            model = vosk.Model(model_path)
            rec = vosk.KaldiRecognizer(model, 16000)
            raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
            rec.AcceptWaveform(raw)
            result = json.loads(rec.Result())
            text = result.get("text", "")
            logger.info(f"Heard (offline/vosk): {text}")
            return text if text else None
        except Exception as e:
            logger.error(f"Vosk offline STT failed: {e}")
            return None


_engine = None


def get_speech_engine(language="en-IN") -> SpeechEngine:
    """Singleton speech engine (language set on first create)."""
    global _engine
    if _engine is None:
        _engine = SpeechEngine(language=language)
    return _engine
