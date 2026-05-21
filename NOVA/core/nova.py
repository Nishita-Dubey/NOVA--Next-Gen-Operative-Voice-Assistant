"""
core/nova.py — Central controller for NOVA.

Wires together:
  - CommandProcessor (intent → action)
  - TextToSpeech (spoken replies)
  - ResponseGenerator (personality phrases)

Use get_nova() for a process-wide singleton instance.
"""

from core.command_processor import CommandProcessor
from voice.text_to_speech import get_tts
from personality.response_generator import ResponseGenerator
from utils.logger import get_logger

logger = get_logger("nova")


class Nova:
    """Main assistant object: receives text/voice commands and speaks replies."""

    def __init__(self, language: str = "en-IN"):
        self.language = language
        self._tts = get_tts()
        self.responses = ResponseGenerator()
        # Processor gets say() so timer module can speak when done
        self.processor = CommandProcessor(
            speak_callback=self.say,
            language=language
        )
        logger.info("NOVA initialized.")

    def greet(self):
        """Speak and return the startup greeting."""
        msg = self.responses.greeting()
        self.say(msg)
        return msg

    def say(self, text: str):
        """Print to console and speak via TTS."""
        print(f"NOVA: {text}")
        self._tts.speak(text)

    def process_command(self, command: str) -> dict:
        """
        Run one user command end-to-end.
        Returns dict with keys: success, response, and optionally exit=True.
        """
        logger.info(f"Command received: {command}")
        result = self.processor.process(command)
        self.say(result["response"])
        return result


# Singleton — one Nova instance per process
_nova_instance = None


def get_nova(language: str = "en-IN") -> Nova:
    """Return shared Nova instance (created on first call)."""
    global _nova_instance
    if _nova_instance is None:
        _nova_instance = Nova(language=language)
    return _nova_instance
