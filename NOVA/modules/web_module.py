"""
modules/web_module.py — Browser, search, and weather.

- open_website / web_search: default browser via webbrowser module
- get_weather: OpenWeatherMap API (key in config.json)
"""

import webbrowser
import requests
from utils.helpers import is_online
from utils.config_manager import get_config
from utils.logger import get_logger

logger = get_logger("web")

# Spoken site names → full URLs (faster than guessing)
COMMON_SITES = {
    "youtube":   "https://youtube.com",
    "google":    "https://google.com",
    "github":    "https://github.com",
    "instagram": "https://instagram.com",
    "twitter":   "https://twitter.com",
    "x":         "https://x.com",
    "linkedin":  "https://linkedin.com",
    "whatsapp":  "https://web.whatsapp.com",
    "gmail":     "https://mail.google.com",
    "amazon":    "https://amazon.in",
    "flipkart":  "https://flipkart.com",
    "netflix":   "https://netflix.com",
    "chatgpt":   "https://chat.openai.com",
}


class WebModule:
    """Handles internet-dependent features."""

    def __init__(self):
        cfg = get_config()
        self._api_key = cfg.get("api.weather_api_key", "")
        self._default_city = cfg.get("api.weather_city", "Indore")

    def open_website(self, site: str) -> dict:
        """Open URL in default browser. Returns offline flag if no network."""
        if not is_online():
            return {"success": False, "offline": True}
        site_clean = site.lower().strip().replace("www.", "")
        for key, url in COMMON_SITES.items():
            if key in site_clean:
                webbrowser.open(url)
                logger.info(f"Opened: {url}")
                return {"success": True, "url": url}
        if not site_clean.startswith("http"):
            site_clean = "https://" + site_clean
        webbrowser.open(site_clean)
        return {"success": True, "url": site_clean}

    def web_search(self, query: str) -> dict:
        """Open Google search results for query."""
        if not is_online():
            return {"success": False, "offline": True}
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(url)
        logger.info(f"Searched: {query}")
        return {"success": True}

    def get_weather(self, city: str = "") -> dict:
        """Fetch current weather from OpenWeatherMap."""
        if not is_online():
            return {"success": False, "offline": True}
        city = city or self._default_city
        if not self._api_key or self._api_key == "YOUR_OPENWEATHERMAP_KEY":
            return {"success": False, "error": "No API key set in config.json"}
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={self._api_key}&units=metric"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            if data.get("cod") != 200:
                return {"success": False, "error": data.get("message", "City not found")}
            return {
                "success": True,
                "city": data["name"],
                "temp": round(data["main"]["temp"]),
                "description": data["weather"][0]["description"],
            }
        except Exception as e:
            logger.error(f"Weather error: {e}")
            return {"success": False, "error": str(e)}
