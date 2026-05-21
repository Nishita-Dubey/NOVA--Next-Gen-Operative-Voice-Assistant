"""
core/intent_recognizer.py — Map spoken/text commands to intents via regex.

Flow:
  1. Match INTENT_PATTERNS (file/folder patterns before open_app)
  2. Reroute mistaken open_app → open_folder / open_file
  3. If no match and looks like a question → intent "unknown" (for Gemini)

Each handler in command_processor.py is named _handle_<intent_name>.
"""

import re
from dataclasses import dataclass, field


@dataclass
class Intent:
    """Recognized command: intent name, extracted params, match confidence 0–1."""
    name: str
    params: dict = field(default_factory=dict)
    confidence: float = 0.0

# Prefixes that indicate a general knowledge question (checked only when no intent matched)
_QUESTION_PREFIXES = (
    "what ", "who ", "why ", "how ", "when ", "where ",
    "explain ", "tell me about ", "tell me a ", "can you explain ",
    "describe ", "define ",
)

# File/folder intents MUST come before open_app — otherwise "open downloads" opens as an app
INTENT_PATTERNS = [
    ("find_file",       [r'\b(find|search|locate)\s+file\s+(?P<filename>.+)',
                         r'\bwhere is\s+(the\s+)?file\s+(?P<filename>.+)',
                         r'\bfind\s+(?P<filename>[\w\s\-\.]+\.\w{1,6})\b']),
    ("find_folder",     [r'\b(find|search|locate)\s+folder\s+(?P<folder_name>.+)',
                         r'\bwhere is\s+(the\s+)?folder\s+(?P<folder_name>.+)']),
    ("open_folder",     [r'\b(open|show|go to|launch)\s+(my\s+)?(?P<folder_path>desktop|documents|downloads|pictures|videos|music|home)\b',
                         r'\b(open|show|go to|launch)\s+(my\s+)?(?P<folder_path>downloads|documents|desktop|pictures|videos|music)\s+folder\b',
                         r'\b(open|show|go to)\s+folder\s+(?P<folder_path>.+)',
                         r'\b(open|show)\s+(?P<folder_path>.+)\s+folder\b']),
    ("open_file",       [r'\bopen\s+(the\s+)?file\s+(?P<filepath>.+)',
                         r'\bopen\s+(?P<filepath>[\w\s\-]+\.\w{2,6})\b',
                         r'\bopen\s+(?P<filepath>[\w\s\-]{2,})\s+file\b']),
    ("open_app",        [r'\b(open|launch|start|run)\s+(?P<app>.+)']),
    ("close_app",       [r'\b(close|quit|exit|kill|stop)\s+(?P<app>.+)']),
    ("open_website",    [r'\b(go to|open|visit|browse)\s+(?P<site>[\w\.\-]+(\.com|\.in|\.org|\.net|\.io|\.co|\.ai|\.app)[\S]*)']),
    ("web_search",      [r'\b(search|google|look up)\s+(for\s+)?(?P<query>.+)',
                         r'\bfind\s+(?P<query>.+)\s+on\s+(google|the web|internet)\b']),
    ("weather",         [r'\bweather\b(\s+in\s+(?P<city>[\w\s]+))?']),
    ("volume_set",      [r'\b(set|change)\s+(the\s+)?volume\s+(to\s+)?(?P<level>\d+)',
                         r'\bvolume\s+(?P<level>\d+)']),
    ("volume_up",       [r'\b(increase|raise|turn up)\s+(the\s+)?volume']),
    ("volume_down",     [r'\b(decrease|lower|turn down)\s+(the\s+)?volume']),
    ("mute",            [r'\b(mute|silence)\b']),
    ("unmute",          [r'\b(unmute|sound on)\b']),
    ("lock",            [r'\b(lock|lock screen)\b']),
    ("screenshot",      [r'\b(screenshot|take a screenshot|capture screen)\b']),
    ("system_info",     [r'\b(system info|cpu|ram|memory|disk|system stats)\b']),
    ("battery",         [r'\b(battery|battery level|charge level)\b']),
    ("shutdown",        [r'\b(shutdown|shut down|turn off the computer)\b']),
    ("restart",         [r'\b(restart|reboot)\b']),
    ("sleep",           [r'\b(sleep|hibernate)\b']),
    ("create_folder",   [r'\b(create|make|new)\s+folder\s+(?P<folder>.+)']),
    ("time",            [r'\b(what.s the time|tell me the time|current time|time)\b']),
    ("date",            [r'\b(what.s the date|today.s date|what day|date)\b']),
    ("set_timer",       [r'\b(set|start)\s+(a\s+)?timer\s+(for\s+)?(?P<duration>[\d\s\w]+)',
                         r'\btimer\s+(for\s+)?(?P<duration>[\d\s\w]+)']),
    ("joke",            [r'\b(tell me a joke|joke|make me laugh|say something funny)\b']),
    ("hello",           [r'\b(hello|hi|hey|howdy)\b']),
    ("goodbye",         [r'\b(bye|goodbye|see you|that.s all|close nova)\b']),
    ("switch_language", [r'\b(switch|change)\s+(language|lang)\s+(to\s+)?(?P<lang>[\w\-]+)']),
]

_KNOWN_FOLDER_WORDS = {
    "desktop", "documents", "downloads", "pictures", "videos", "music", "home",
    "my desktop", "my documents", "my downloads", "my pictures", "my videos", "my music",
}


def _is_general_question(command_lower: str) -> bool:
    return any(command_lower.startswith(prefix) for prefix in _QUESTION_PREFIXES)


def _looks_like_folder(name: str) -> bool:
    n = name.lower().strip().rstrip(" folder").strip()
    return n in _KNOWN_FOLDER_WORDS or n.replace("my ", "") in _KNOWN_FOLDER_WORDS


def _looks_like_file(name: str) -> bool:
    return "." in name and not name.lower().startswith(("http://", "https://", "www."))


def parse_duration(text: str) -> int:
    total = 0
    text = text.lower()
    for val, unit in re.findall(r'(\d+)\s*(hour|hr|minute|min|second|sec)', text):
        val = int(val)
        if 'hour' in unit or unit == 'hr':
            total += val * 3600
        elif 'min' in unit:
            total += val * 60
        else:
            total += val
    if total == 0:
        m = re.search(r'(\d+)', text)
        if m:
            total = int(m.group(1))
    return total

class IntentRecognizer:
    """Regex-based intent detection (fast, works offline)."""

    def recognize(self, command: str) -> Intent:
        """Return best matching Intent for the user's command string."""
        command_lower = command.lower().strip()

        for intent_name, patterns in INTENT_PATTERNS:
            for pattern in patterns:
                match = re.search(pattern, command_lower)
                if match:
                    params = {k: v.strip() if v else v
                              for k, v in match.groupdict().items() if v}
                    # open_app stole "open downloads" / "open resume.pdf" — reroute
                    if intent_name == "open_app":
                        target = params.get("app", "")
                        if _looks_like_folder(target):
                            return Intent(name="open_folder", params={"folder_path": target},
                                          confidence=0.9)
                        if _looks_like_file(target):
                            return Intent(name="open_file", params={"filepath": target},
                                          confidence=0.9)
                    if intent_name == "set_timer" and params.get("duration"):
                        params["seconds"] = parse_duration(params["duration"])
                    confidence = len(match.group(0)) / max(len(command_lower), 1)
                    return Intent(name=intent_name, params=params,
                                  confidence=round(confidence, 2))

        if _is_general_question(command_lower):
            return Intent(name="unknown", confidence=0.0)

        return Intent(name="unknown", confidence=0.0)
