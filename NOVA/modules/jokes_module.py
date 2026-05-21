"""
modules/jokes_module.py — Fetch random jokes via pyjokes library.

Triggered by joke intent: "tell me a joke", "make me laugh", etc.
"""

import pyjokes
from utils.logger import get_logger

logger = get_logger("jokes")


class JokesModule:
    """Returns one joke string in the requested language."""

    def get_joke(self, language: str = "en") -> str:
        # pyjokes supports: en, de, es, gl, eu
        lang = language[:2].lower()
        supported = ["en", "de", "es", "gl", "eu"]
        if lang not in supported:
            lang = "en"
        try:
            joke = pyjokes.get_joke(language=lang, category="all")
            logger.info(f"Joke fetched ({lang})")
            return joke
        except Exception as e:
            logger.error(f"Joke error: {e}")
            return "Why don't scientists trust atoms? Because they make up everything!"
