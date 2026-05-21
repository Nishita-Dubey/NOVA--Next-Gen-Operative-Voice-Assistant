"""
personality/response_generator.py — Natural-language replies for NOVA.

Picks random phrasing from templates so responses feel less robotic.
Reads assistant name and how to address the user from config.json.
"""

import random
from utils.config_manager import get_config


class ResponseGenerator:
    """Builds spoken-friendly response strings for each command outcome."""

    def __init__(self):
        cfg = get_config()
        self.name = cfg.get("assistant.name", "NOVA")
        self.address = cfg.get("assistant.address_as", "boss")

    def _pick(self, options):
        """Return one random line from a list of template strings."""
        return random.choice(options)

    def greeting(self):
        from utils.helpers import get_time_greeting
        greet = get_time_greeting()
        return self._pick([
            f"{greet}, {self.address}! I'm {self.name}, online and ready.",
            f"{greet}! {self.name} at your service, {self.address}.",
            f"Hey {self.address}! {self.name} is up and ready to help.",
        ])

    def success(self, action=""):
        options = [f"Done, {self.address}.", "Right away.", "Consider it done.", "Sure thing."]
        if action:
            options.append(f"{action}, {self.address}.")
        return self._pick(options)

    def launching(self, app):
        return self._pick([
            f"Opening {app} for you, {self.address}.",
            f"Launching {app} right away.",
            f"Starting {app} now.",
        ])

    def closing(self, app):
        return self._pick([f"Closing {app}.", f"Shutting down {app} now."])

    def error(self, reason=""):
        msg = f" {reason}" if reason else ""
        return self._pick([
            f"Sorry, I couldn't do that.{msg}",
            f"Something went wrong.{msg}",
        ])

    def offline_warning(self, feature="That"):
        return self._pick([
            f"You're offline, {self.address}. {feature} requires internet access.",
            f"No internet connection. Can't do that right now.",
        ])

    def not_understood(self):
        return self._pick([
            "I didn't quite catch that. Could you rephrase?",
            "Hmm, I'm not sure what you mean.",
            "Sorry, I don't know how to do that yet.",
        ])

    def time_response(self, t):
        return f"It's {t}, {self.address}."

    def date_response(self, d):
        return f"Today is {d}."

    def battery_response(self, pct, plugged):
        status = "charging" if plugged else "on battery"
        return f"Battery is at {pct} percent and {status}."

    def timer_set(self, seconds):
        mins, secs = divmod(seconds, 60)
        if mins:
            return f"Timer set for {mins} minute{'s' if mins > 1 else ''} and {secs} seconds."
        return f"Timer set for {seconds} seconds."

    def timer_done(self):
        return f"Time's up, {self.address}! Your timer is done."

    def weather_response(self, city, temp, desc):
        return f"In {city}, it's {temp}°C with {desc}."

    def goodbye(self):
        return self._pick([
            f"Goodbye, {self.address}! Have a great day.",
            "See you later! Stay awesome.",
            f"Shutting down. Take care, {self.address}.",
        ])
