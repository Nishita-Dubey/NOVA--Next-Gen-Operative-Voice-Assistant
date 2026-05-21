"""
voice/wake_word.py — Background listener for "Hey NOVA" wake phrase.

Runs in a daemon thread; calls callback when wake word is detected.
Uses Google STT (requires internet). Enable via config features.wake_word_enabled.
"""

import threading
import speech_recognition as sr
from utils.logger import get_logger

logger = get_logger("wake_word")


class WakeWordDetector:
    """Polls microphone in a loop until wake word appears in transcription."""

    def __init__(self, wake_word: str = "nova", callback=None):
        self.wake_word = wake_word.lower()
        self.callback = callback  # function to run when user says "Hey NOVA"
        self._running = False
        self._thread = None
        self._recognizer = sr.Recognizer()
        self._recognizer.dynamic_energy_threshold = True

    def start(self):
        """Start background listening thread."""
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info(f"Wake word detector running — say 'Hey {self.wake_word.upper()}'")

    def stop(self):
        self._running = False
        logger.info("Wake word detector stopped.")

    def _listen_loop(self):
        """Continuously listen for short phrases containing the wake word."""
        while self._running:
            try:
                with sr.Microphone() as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio = self._recognizer.listen(source, timeout=3, phrase_time_limit=4)
                text = self._recognizer.recognize_google(audio, language="en-IN").lower()
                logger.debug(f"Wake word listener heard: {text}")
                if self.wake_word in text or f"hey {self.wake_word}" in text:
                    logger.info("Wake word detected!")
                    if self.callback:
                        self.callback()
            except (sr.WaitTimeoutError, sr.UnknownValueError):
                pass
            except sr.RequestError:
                pass
            except Exception as e:
                logger.debug(f"Wake word loop error: {e}")
