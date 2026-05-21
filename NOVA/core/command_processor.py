"""
core/command_processor.py — Routes intents to module handlers.

Pipeline:
  1. IntentRecognizer (regex)
  2. Optional Gemini: ask() for questions, parse_intent() for unknown commands
  3. _handle_<intent> methods return {success, response, ...}
"""

from core.intent_recognizer import IntentRecognizer
from modules.application_manager import ApplicationManager
from modules.system_controller import SystemController
from modules.file_manager import FileManager
from modules.web_module import WebModule
from modules.timer_module import TimerModule
from modules.jokes_module import JokesModule
from personality.response_generator import ResponseGenerator
from utils.helpers import get_current_time, get_current_date
from utils.logger import get_logger

logger = get_logger("command_processor")

class CommandProcessor:
    """Central dispatcher: wires intents to apps, files, web, system, LLM, etc."""

    def __init__(self, speak_callback=None, language="en-IN"):
        self.intent = IntentRecognizer()
        self.apps = ApplicationManager()
        self.system = SystemController()
        self.files = FileManager()
        self.web = WebModule()
        self.timer = TimerModule(speak_callback=speak_callback)
        self.jokes = JokesModule()
        self.responses = ResponseGenerator()
        self.language = language
        self._speak = speak_callback

        # Initialise LLM bridge (Gemini) — loads API key from config/env
        try:
            from utils.config_manager import ConfigManager
            cfg = ConfigManager().get("api") or {}
            gemini_key = cfg.get("gemini_api_key", "") if isinstance(cfg, dict) else ""
        except Exception:
            gemini_key = ""
        try:
            from modules.llm_bridge import reset_llm_bridge, get_llm_bridge
            reset_llm_bridge()
            self._llm = get_llm_bridge(api_key=gemini_key)
            if self._llm.available:
                logger.info("LLM (Gemini) is active — natural language fallback enabled.")
            else:
                logger.warning("LLM unavailable — regex-only mode.")
        except Exception as e:
            self._llm = None
            logger.error(f"LLM bridge init failed: {e}")

    def process(self, command: str) -> dict:
        """Main entry: recognize intent, optionally use LLM, run handler."""
        intent = self.intent.recognize(command)
        logger.info(f"Intent: {intent.name} | Params: {intent.params} | Confidence: {intent.confidence}")

        # Route general questions to Gemini ask()
        if self._should_use_llm_ask(command, intent):
            return self._handle_unknown(intent.params, command=command)

        # If regex couldn't understand, try Gemini intent parsing for system commands
        if intent.name == "unknown" and self._llm and self._llm.available:
            logger.info("Regex returned unknown — trying LLM intent fallback...")
            llm_result = self._llm.parse_intent(command)
            if llm_result and llm_result.get("intent", "unknown") != "unknown":
                intent.name = llm_result["intent"]
                intent.params = llm_result.get("params", {})
                logger.info(f"LLM resolved → intent={intent.name}, params={intent.params}")
            else:
                return self._handle_unknown(intent.params, command=command)

        if intent.name == "unknown":
            return self._handle_unknown(intent.params, command=command)
        handler = getattr(self, f"_handle_{intent.name}", self._handle_unknown)
        return handler(intent.params)

    def _should_use_llm_ask(self, command: str, intent) -> bool:
        """Return True if this command should be answered conversationally via LLM."""
        if not self._llm or not self._llm.available:
            return False
        if intent.name == "unknown":
            return True
        question_starters = (
            "what", "who", "why", "how", "when", "where",
            "tell me", "explain", "can you",
        )
        cmd_lower = command.lower().strip()
        looks_like_question = any(cmd_lower.startswith(s) for s in question_starters)
        return looks_like_question and intent.confidence < 0.4

    # ── App ──────────────────────────────────────────────────
    def _handle_open_app(self, p):
        app = (p.get("app") or "").strip()
        app_lower = app.lower().rstrip(" folder").strip()

        from utils.helpers import get_known_user_folders
        if app_lower in get_known_user_folders() or app_lower.replace("my ", "") in get_known_user_folders():
            return self._handle_open_folder({"folder_path": app})

        if "." in app and not app_lower.startswith(("http://", "https://")):
            return self._handle_open_file({"filepath": app})

        if self._llm and self._llm.available:
            result = self.apps.open_app_with_llm_fallback(app)
        else:
            result = self.apps.open_app(app)
        if result["success"]:
            return {"success": True, "response": self.responses.launching(app)}
        return {"success": False, "response": self.responses.error(f"Could not open {app}")}

    def _handle_close_app(self, p):
        app = p.get("app", "")
        result = self.apps.close_app(app)
        if result["success"]:
            return {"success": True, "response": self.responses.closing(app)}
        return {"success": False, "response": self.responses.error(f"Could not close {app}")}

    # ── Web ──────────────────────────────────────────────────
    def _handle_open_website(self, p):
        site = p.get("site", "")
        result = self.web.open_website(site)
        if result.get("offline"):
            return {"success": False, "response": self.responses.offline_warning("Opening websites")}
        return {"success": True, "response": self.responses.success(f"Opening {site}")}

    def _handle_web_search(self, p):
        query = p.get("query", "")
        result = self.web.web_search(query)
        if result.get("offline"):
            return {"success": False, "response": self.responses.offline_warning("Web search")}
        return {"success": True, "response": self.responses.success(f"Searching for {query}")}

    def _handle_weather(self, p):
        city = p.get("city", "")
        result = self.web.get_weather(city)
        if result.get("offline"):
            return {"success": False, "response": self.responses.offline_warning("Weather")}
        if not result["success"]:
            return {"success": False, "response": self.responses.error(result.get("error", ""))}
        return {"success": True, "response": self.responses.weather_response(
            result["city"], result["temp"], result["description"])}

    # ── Volume ───────────────────────────────────────────────
    def _handle_volume_set(self, p):
        level = int(p.get("level", 50))
        self.system.set_volume(level)
        return {"success": True, "response": self.responses.success(f"Volume set to {level}%")}

    def _handle_volume_up(self, p):
        new = self.system.change_volume(10)
        return {"success": True, "response": self.responses.success(f"Volume increased to {new}%")}

    def _handle_volume_down(self, p):
        new = self.system.change_volume(-10)
        return {"success": True, "response": self.responses.success(f"Volume decreased to {new}%")}

    def _handle_mute(self, p):
        self.system.mute()
        return {"success": True, "response": self.responses.success("Muted")}

    def _handle_unmute(self, p):
        self.system.unmute()
        return {"success": True, "response": self.responses.success("Unmuted")}

    # ── System ───────────────────────────────────────────────
    def _handle_lock(self, p):
        self.system.lock_screen()
        return {"success": True, "response": self.responses.success("Locking screen")}

    def _handle_screenshot(self, p):
        result = self.system.take_screenshot()
        if result["success"]:
            return {"success": True, "response": self.responses.success(f"Screenshot saved as {result['file']}")}
        return {"success": False, "response": self.responses.error("Screenshot failed")}

    def _handle_system_info(self, p):
        info = self.system.get_system_info()
        response = (f"CPU is at {info['cpu']}%, RAM at {info['ram']}%, "
                    f"Disk at {info['disk']}%.")
        return {"success": True, "response": response}

    def _handle_battery(self, p):
        b = self.system.get_battery()
        if b["percent"] == -1:
            return {"success": False, "response": "Battery info not available."}
        return {"success": True, "response": self.responses.battery_response(b["percent"], b["plugged"])}

    def _handle_shutdown(self, p):
        self.system.shutdown()
        return {"success": True, "response": "Shutting down in 5 seconds. Goodbye!"}

    def _handle_restart(self, p):
        self.system.restart()
        return {"success": True, "response": "Restarting in 5 seconds."}

    def _handle_sleep(self, p):
        self.system.sleep()
        return {"success": True, "response": "Going to sleep. Goodnight!"}

    # ── Files ────────────────────────────────────────────────
    def _handle_find_file(self, p):
        filename = p.get("filename", "")
        result = self.files.find_file(filename)
        if result["success"]:
            files = result["files"][:3]
            return {"success": True, "response": f"Found: {', '.join(files)}"}
        return {"success": False, "response": f"No file matching '{filename}' found."}

    def _handle_open_file(self, p):
        filepath = p.get("filepath", "")
        result = self.files.open_file(filepath)
        if result["success"]:
            return {"success": True, "response": self.responses.success(f"Opening {result.get('path', filepath)}")}
        return {"success": False, "response": self.responses.error(f"Could not open file '{filepath}'")}

    def _handle_open_folder(self, p):
        """Open a folder — checks ApplicationManager's FOLDER_MAP first, then FileManager search."""
        folder_path = p.get("folder_path", "") or p.get("folder", "") or p.get("app", "")
        if not folder_path:
            return {"success": False, "response": "Please tell me which folder to open."}

        # Try ApplicationManager's named folder map (Desktop, Documents, Downloads…)
        result = self.apps.open_folder(folder_path)
        if result["success"]:
            return {"success": True, "response": self.responses.success(f"Opening {result['path']}")}

        # Fall back to a filesystem search for the folder
        result = self.files.open_folder(folder_path)
        if result["success"]:
            return {"success": True, "response": self.responses.success(f"Opening {result['path']}")}

        return {"success": False, "response": self.responses.error(f"Could not find folder '{folder_path}'")}

    def _handle_find_folder(self, p):
        folder_name = p.get("folder_name", "") or p.get("filename", "")
        result = self.files.find_folder(folder_name)
        if result["success"]:
            folders = result["folders"][:3]
            return {"success": True, "response": f"Found folders: {', '.join(folders)}"}
        return {"success": False, "response": f"No folder matching '{folder_name}' found."}

    def _handle_create_folder(self, p):
        folder = p.get("folder", "New Folder")
        result = self.files.create_folder(folder)
        if result["success"]:
            return {"success": True, "response": self.responses.success(f"Folder '{folder}' created on Desktop")}
        return {"success": False, "response": self.responses.error()}

    # ── Time / Date ──────────────────────────────────────────
    def _handle_time(self, p):
        return {"success": True, "response": self.responses.time_response(get_current_time())}

    def _handle_date(self, p):
        return {"success": True, "response": self.responses.date_response(get_current_date())}

    # ── Timer ────────────────────────────────────────────────
    def _handle_set_timer(self, p):
        seconds = p.get("seconds", 0)
        if not seconds:
            return {"success": False, "response": "I couldn't understand the duration. Try 'set timer for 5 minutes'."}
        self.timer.set_timer(seconds)
        return {"success": True, "response": self.responses.timer_set(seconds)}

    # ── Jokes ────────────────────────────────────────────────
    def _handle_joke(self, p):
        lang = self.language[:2].lower()
        joke = self.jokes.get_joke(language=lang)
        return {"success": True, "response": joke}

    # ── Greet / Exit ────────────────────────────────────────
    def _handle_hello(self, p):
        return {"success": True, "response": self.responses.greeting()}

    def _handle_goodbye(self, p):
        return {"success": True, "response": self.responses.goodbye(), "exit": True}

    # ── Language switch ──────────────────────────────────────
    def _handle_switch_language(self, p):
        lang = p.get("lang", "en")
        self.language = lang
        return {"success": True, "response": f"Language switched to {lang}."}

    # ── Unknown / conversational ─────────────────────────────
    def _handle_unknown(self, p, command: str = ""):
        if command and self._llm and self._llm.available:
            logger.info(f"Routing to Gemini ask: '{command}'")
            answer = self._llm.ask(command)
            return {"success": True, "response": answer}
        if command:
            q_words = ("what", "who", "why", "how", "when", "where", "tell me", "explain")
            if any(command.lower().startswith(w) for w in q_words):
                err = getattr(self._llm, "_last_error", "") if self._llm else ""
                if "429" in err or "quota" in err.lower():
                    msg = (
                        "Gemini rate limit reached. Wait a minute and try again, "
                        "or check your quota at aistudio.google.com."
                    )
                elif self._llm and not self._llm.available:
                    msg = (
                        "Gemini is not connected. Check api.gemini_api_key in config.json "
                        "and restart NOVA from the NOVA_updated folder."
                    )
                else:
                    msg = (
                        "I could not reach Gemini right now. Check your internet "
                        "and API key in config.json, then restart NOVA."
                    )
                return {"success": False, "response": msg}
        return {"success": False, "response": self.responses.not_understood()}
