"""
modules/llm_bridge.py — Gemini LLM integration for NOVA.

Handles two jobs:
  1. Natural-language intent parsing when regex fails (unknown intent).
  2. Fuzzy app-name resolution (e.g. "ms paint" → "mspaint.exe").

Requires:  pip install google-generativeai
API key:   Free tier at https://aistudio.google.com/app/apikey
           Set  GEMINI_API_KEY  in your environment  OR  put it in config.json
           under  "api" → "gemini_api_key".
"""

import json
import os
import re
from utils.logger import get_logger

logger = get_logger("llm_bridge")

# ── lazy import so NOVA still works without the package installed ────────────
try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False
    logger.warning("google-generativeai not installed. Run: pip install google-generativeai")


# ── known intents the LLM can return ────────────────────────────────────────
VALID_INTENTS = {
    "open_app", "close_app", "open_website", "web_search", "weather",
    "volume_set", "volume_up", "volume_down", "mute", "unmute",
    "lock", "screenshot", "system_info", "battery",
    "shutdown", "restart", "sleep",
    "find_file", "open_file", "open_folder", "create_folder",
    "time", "date", "set_timer", "joke",
    "hello", "goodbye", "switch_language", "unknown",
}

_SYSTEM_PROMPT = """
You are the intent-parsing brain of NOVA, a Windows voice assistant.
Given a user command, reply with ONLY a JSON object (no markdown, no extra text):

{
  "intent": "<one of the valid intents>",
  "params": { ... }
}

Valid intents and their params:
- open_app        → {"app": "<name>"}
- close_app       → {"app": "<name>"}
- open_website    → {"site": "<url or domain>"}
- web_search      → {"query": "<search query>"}
- weather         → {"city": "<city or empty>"}
- volume_set      → {"level": <0-100>}
- volume_up       → {}
- volume_down     → {}
- mute            → {}
- unmute          → {}
- lock            → {}
- screenshot      → {}
- system_info     → {}
- battery         → {}
- shutdown        → {}
- restart         → {}
- sleep           → {}
- find_file       → {"filename": "<name or partial name>"}
- open_file       → {"filepath": "<full path if given, else filename>"}
- open_folder     → {"folder_path": "<path or name like Documents/Downloads/Desktop>"}
- create_folder   → {"folder": "<name>"}
- time            → {}
- date            → {}
- set_timer       → {"seconds": <int>}
- joke            → {}
- hello           → {}
- goodbye         → {}
- switch_language → {"lang": "<code>"}
- unknown         → {}

For app names, normalise to the most common name (e.g. "ms paint" → "paint",
"microsoft paint" → "paint", "google chrome" → "chrome").
For folder paths like "my documents" → "Documents", "downloads" → "Downloads".
"""

_ASK_SYSTEM_PROMPT = (
    "You are NOVA, a helpful Windows voice assistant. Answer the user's question "
    "clearly and concisely in 2-3 sentences. Do not use markdown, bullet points, "
    "or special characters — respond in plain spoken English suitable for text-to-speech."
)

# Order: models that work on the current Gemini API (1.5-* names return 404)
_GEMINI_MODELS = (
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash",
)

_PLACEHOLDER_MARKERS = ("YOUR_", "REPLACE_", "PASTE_", "API_KEY_HERE", "xxx", "placeholder")


def _is_valid_api_key(key: str) -> bool:
    if not key or len(key.strip()) < 20:
        return False
    lower = key.lower().strip()
    if any(marker.lower() in lower for marker in _PLACEHOLDER_MARKERS):
        return False
    return True


class LLMBridge:
    """
    Google Gemini API wrapper.

    - parse_intent(): command → JSON intent (when regex fails)
    - ask(): free-form Q&A for general knowledge
    - resolve_app_name(): fuzzy app name → short name
    """

    def __init__(self, api_key: str = ""):
        self._ready = False
        self._model = None
        self._last_error = ""

        key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        if not _is_valid_api_key(key):
            logger.warning(
                "Gemini API key missing or still a placeholder. "
                "Set api.gemini_api_key in config.json (get a free key at "
                "https://aistudio.google.com/app/apikey)"
            )
            return
        if not _GENAI_AVAILABLE:
            logger.warning("Install google-generativeai: pip install google-generativeai")
            return

        try:
            genai.configure(api_key=key)
            last_error = None
            for model_name in _GEMINI_MODELS:
                try:
                    ask_model = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=_ASK_SYSTEM_PROMPT,
                    )
                    test = ask_model.generate_content("Reply with exactly: ok")
                    if not test or not getattr(test, "text", None):
                        raise RuntimeError("Empty response from Gemini")
                    self._ask_model = ask_model
                    self._model = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=_SYSTEM_PROMPT,
                    )
                    self._model_name = model_name
                    self._ready = True
                    logger.info(f"Gemini LLM bridge ready (model={model_name}).")
                    return
                except Exception as e:
                    last_error = e
                    self._last_error = str(e)
                    logger.warning(f"Model {model_name} failed: {e}")
            logger.error(f"Gemini init failed for all models: {last_error}")
            self._ask_model = None
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Gemini init failed: {e}")
            self._ask_model = None

    @property
    def available(self) -> bool:
        return self._ready

    def parse_intent(self, command: str) -> dict | None:
        """
        Ask Gemini to parse the command.
        Returns {"intent": str, "params": dict} or None on failure.
        """
        if not self._ready:
            return None
        try:
            response = self._model.generate_content(command)
            raw = response.text.strip()
            # Strip accidental markdown fences
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            data = json.loads(raw)
            intent = data.get("intent", "unknown")
            if intent not in VALID_INTENTS:
                intent = "unknown"
            params = data.get("params", {})
            logger.info(f"Gemini parsed → intent={intent} params={params}")
            return {"intent": intent, "params": params}
        except Exception as e:
            logger.error(f"Gemini parse_intent error: {e}")
            return None

    def ask(self, question: str) -> str:
        """
        Send a free-form question to Gemini and return its answer as a string.
        Used for general knowledge, conversation, and anything not a system command.
        """
        if not self._ready:
            return (
                "I cannot answer that yet. Please add your Gemini API key in config.json "
                "under api gemini api key. Get a free key from Google AI Studio."
            )
        try:
            model = getattr(self, "_ask_model", None) or self._model
            response = model.generate_content(question)
            text = response.text.strip()
            text = re.sub(r"[*_#`]", "", text)
            text = re.sub(r"\s+", " ", text)
            logger.info(f"Gemini ask OK: {text[:80]}...")
            return text
        except Exception as e:
            logger.error(f"Gemini ask error: {e}")
            return "I'm sorry, I couldn't get an answer right now. Please try again."

    def resolve_app_name(self, spoken_name: str) -> str:
        """
        Ask Gemini to resolve a spoken/fuzzy app name to its common key.
        e.g. "ms paint" → "paint", "microsoft word" → "word"
        Returns the resolved name (lowercase) or the original if LLM fails.
        """
        if not self._ready:
            return spoken_name
        try:
            prompt = (
                f'The user said they want to open: "{spoken_name}". '
                "Reply with ONLY the most common short name for this Windows app "
                "(e.g. 'paint', 'chrome', 'notepad', 'word', 'vlc'). "
                "No extra words."
            )
            response = self._model.generate_content(prompt)
            resolved = response.text.strip().lower()
            logger.info(f"App name resolved: '{spoken_name}' → '{resolved}'")
            return resolved
        except Exception as e:
            logger.error(f"resolve_app_name error: {e}")
            return spoken_name


# ── module-level singleton ───────────────────────────────────────────────────
_bridge: LLMBridge | None = None


def _load_key_from_config() -> str:
    """Read gemini_api_key directly from NOVA/config.json next to this package."""
    import pathlib
    config_path = pathlib.Path(__file__).resolve().parent.parent / "config.json"
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        return (data.get("api") or {}).get("gemini_api_key", "") or ""
    except Exception as e:
        logger.debug(f"Could not read {config_path}: {e}")
        return ""


def get_llm_bridge(api_key: str = "") -> LLMBridge:
    global _bridge
    resolved_key = (api_key or _load_key_from_config() or os.getenv("GEMINI_API_KEY", "")).strip()
    if _bridge is None or (not _bridge.available and _is_valid_api_key(resolved_key)):
        _bridge = LLMBridge(api_key=resolved_key)
    return _bridge


def reset_llm_bridge() -> None:
    """Force reload after config.json changes (call on restart)."""
    global _bridge
    _bridge = None
