"""
utils/config_manager.py — Load and merge config.json with built-in defaults.

Config file location: NOVA/config.json (next to main.py).
Access nested keys with dot notation: cfg.get("voice.tts_rate")
"""

import json
import os
from utils.logger import get_logger

logger = get_logger("config")

# Used when config.json is missing or a key is absent
DEFAULT_CONFIG = {
    "assistant": {
        "name": "NOVA",
        "wake_word": "nova",
        "address_as": "boss",
        "language": "en-IN"
    },
    "voice": {
        "tts_rate": 175,
        "tts_volume": 1.0,
        "preferred_voice": "female",
        "speech_timeout": 5,
        "energy_threshold": 300
    },
    "features": {
        "wake_word_enabled": True,
        "multi_language": True,
        "offline_fallback": True
    },
    "api": {
        "weather_api_key": "YOUR_OPENWEATHERMAP_KEY",
        "weather_city": "Indore"
    }
}


class ConfigManager:
    """Loads config.json from project root and deep-merges over DEFAULT_CONFIG."""

    def __init__(self, path="config.json"):
        self._config = DEFAULT_CONFIG.copy()
        # Resolve path relative to NOVA package root (parent of utils/)
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), path)
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    loaded = json.load(f)
                self._deep_merge(self._config, loaded)
            except Exception as e:
                logger.warning(f"Could not load config.json: {e}. Using defaults.")

    def _deep_merge(self, base, override):
        """Recursively merge override dict into base."""
        for k, v in override.items():
            if isinstance(v, dict) and k in base:
                self._deep_merge(base[k], v)
            else:
                base[k] = v

    def get(self, key: str, default=None):
        """
        Get config value. Supports dotted keys, e.g. "api.gemini_api_key".
        Pass a single segment like "api" to get the whole section dict.
        """
        parts = key.split(".")
        val = self._config
        for p in parts:
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                return default
        return val


_config = None


def get_config() -> ConfigManager:
    """Process-wide singleton ConfigManager."""
    global _config
    if _config is None:
        _config = ConfigManager()
    return _config
