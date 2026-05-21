"""
modules/timer_module.py — Background countdown timers.

Uses threading.Timer; speaks via callback when time expires.
"""

import threading
import time
from utils.logger import get_logger

logger = get_logger("timer")


class TimerModule:
    """Manages one or more concurrent countdown timers."""

    def __init__(self, speak_callback=None):
        self._speak = speak_callback  # nova.say passed from CommandProcessor
        self._timers = []  # keep references so timers are not garbage-collected

    def set_timer(self, seconds: int, label: str = "Timer") -> dict:
        """Start a timer for `seconds`; call speak_callback when done."""
        if seconds <= 0:
            return {"success": False, "error": "Duration must be > 0"}
        t = threading.Timer(seconds, self._on_timer_done, args=[label])
        t.daemon = True
        t.start()
        self._timers.append(t)
        logger.info(f"Timer set for {seconds}s")
        return {"success": True, "seconds": seconds}

    def _on_timer_done(self, label: str):
        message = f"Time's up! Your {label} is done."
        logger.info(message)
        if self._speak:
            self._speak(message)
        else:
            print(f"\n🔔 {message}\n")
