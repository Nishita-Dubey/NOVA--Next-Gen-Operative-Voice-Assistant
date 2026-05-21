"""
modules/application_manager.py — Opens and closes Windows apps.

Changes vs original:
  * Static APP_MAP kept as fallback / quick-lookup.
  * Desktop scanner: reads all .lnk shortcuts from the user's Desktop
    and builds a dynamic map at startup.
  * Start-menu scanner: also walks Start Menu Programs folder.
  * Robust launch via os.startfile, PATH lookup, and exe scanning.
  * LLM fuzzy resolution: if the spoken name isn't in either map,
    ask Gemini to normalise it before giving up.
  * open_folder() helper added for the new open_folder intent.
"""

import difflib
import os
import shutil
import subprocess
import pathlib
import psutil
from utils.logger import get_logger

logger = get_logger("app_manager")

# ── Static known-apps map ────────────────────────────────────────────────────
APP_MAP = {
    # Browsers
    "chrome":               "chrome.exe",
    "google chrome":        "chrome.exe",
    "firefox":              "firefox.exe",
    "edge":                 "msedge.exe",
    "microsoft edge":       "msedge.exe",
    "brave":                "brave.exe",
    "opera":                "opera.exe",
    # Office
    "word":                 "WINWORD.EXE",
    "microsoft word":       "WINWORD.EXE",
    "ms word":              "WINWORD.EXE",
    "excel":                "EXCEL.EXE",
    "microsoft excel":      "EXCEL.EXE",
    "powerpoint":           "POWERPNT.EXE",
    "microsoft powerpoint": "POWERPNT.EXE",
    "onenote":              "ONENOTE.EXE",
    "outlook":              "OUTLOOK.EXE",
    # Windows built-ins
    "notepad":              "notepad.exe",
    "calculator":           "calc.exe",
    "calc":                 "calc.exe",
    "paint":                "mspaint.exe",
    "ms paint":             "mspaint.exe",
    "mspaint":              "mspaint.exe",
    "microsoft paint":      "mspaint.exe",
    "snipping tool":        "SnippingTool.exe",
    "cmd":                  "cmd.exe",
    "command prompt":       "cmd.exe",
    "terminal":             "wt.exe",
    "windows terminal":     "wt.exe",
    "powershell":           "powershell.exe",
    "file explorer":        "explorer.exe",
    "explorer":             "explorer.exe",
    "task manager":         "taskmgr.exe",
    "control panel":        "control.exe",
    "settings":             "ms-settings:",
    "registry":             "regedit.exe",
    "wordpad":              "wordpad.exe",
    "word pad":             "wordpad.exe",
    "sticky notes":         "StikyNot.exe",
    "character map":        "charmap.exe",
    "calendar":             "outlookcal.exe",
    "mail":                 "HxOutlook.exe",
    "camera":               "WindowsCamera.exe",
    "photos":               "Microsoft.Photos.exe",
    "maps":                 "Maps.exe",
    "store":                "WinStore.App.exe",
    "microsoft store":      "WinStore.App.exe",
    # Media / comms
    "vlc":                  "vlc.exe",
    "spotify":              "spotify.exe",
    "media player":         "wmplayer.exe",
    "windows media player": "wmplayer.exe",
    "zoom":                 "Zoom.exe",
    "teams":                "Teams.exe",
    "microsoft teams":      "Teams.exe",
    "skype":                "Skype.exe",
    "whatsapp":             "WhatsApp.exe",
    "telegram":             "Telegram.exe",
    "discord":              "Discord.exe",
    "slack":                "slack.exe",
    # Dev tools
    "vscode":               "code.exe",
    "vs code":              "code.exe",
    "visual studio code":   "code.exe",
    "visual studio":        "devenv.exe",
    "android studio":       "studio64.exe",
    "pycharm":              "pycharm64.exe",
    "postman":              "Postman.exe",
    "git bash":             "git-bash.exe",
    "notepad++":            "notepad++.exe",
    "sublime":              "sublime_text.exe",
    "sublime text":         "sublime_text.exe",
    # Other common apps
    "steam":                "steam.exe",
    "epic games":           "EpicGamesLauncher.exe",
    "obs":                  "obs64.exe",
    "obs studio":           "obs64.exe",
    "7zip":                 "7zFM.exe",
    "7 zip":                "7zFM.exe",
    "winrar":               "WinRAR.exe",
    "adobe reader":         "AcroRd32.exe",
    "acrobat":              "AcroRd32.exe",
    "photoshop":            "Photoshop.exe",
    "itunes":               "iTunes.exe",
    "blender":              "blender.exe",
    "gimp":                 "gimp-2.10.exe",
    "cursor":               "Cursor.exe",
}

# Directories to scan for .exe files when not in PATH
_EXE_SCAN_DIRS = [
    pathlib.Path("C:/Program Files"),
    pathlib.Path("C:/Program Files (x86)"),
]

def _folder_map():
    from utils.helpers import get_known_user_folders
    return get_known_user_folders()


def _fuzzy_match(name: str, candidates: dict, cutoff: float = 0.6) -> str | None:
    """Return the best matching value from candidates using difflib."""
    if not candidates:
        return None
    keys = list(candidates.keys())
    matches = difflib.get_close_matches(name, keys, n=1, cutoff=cutoff)
    if matches:
        return candidates[matches[0]]
    return None


def _scan_shortcuts(folders):
    """Walk given folders for .lnk files, return {lowercase_name: path}."""
    found = {}
    for folder in folders:
        folder = pathlib.Path(folder)
        if not folder.exists():
            continue
        try:
            for lnk in folder.rglob("*.lnk"):
                name = lnk.stem.lower().strip()
                if name not in found:
                    found[name] = str(lnk)
        except (PermissionError, OSError) as e:
            logger.debug(f"Shortcut scan skipped {folder}: {e}")
    return found


def _find_exe(exe_name: str) -> str | None:
    """Search Program Files and AppData for an executable."""
    exe_lower = exe_name.lower()
    scan_roots = list(_EXE_SCAN_DIRS)
    localappdata = os.environ.get("LOCALAPPDATA")
    appdata = os.environ.get("APPDATA")
    if localappdata:
        scan_roots.append(pathlib.Path(localappdata))
    if appdata:
        scan_roots.append(pathlib.Path(appdata))

    for root in scan_roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob(exe_name):
                if path.is_file() and path.name.lower() == exe_lower:
                    return str(path)
        except (PermissionError, OSError):
            continue
    return None


class ApplicationManager:
    """
    Launch and close Windows applications.

    Resolution order: APP_MAP → desktop .lnk → start menu .lnk → fuzzy match
    Launch order: .lnk / full .exe → PATH → Program Files scan → shell start
    """

    def __init__(self):
        # Build shortcut maps once at startup (desktop + start menu)
        desktop_dirs = [
            pathlib.Path.home() / "Desktop",
            pathlib.Path("C:/Users/Public/Desktop"),
        ]
        appdata = os.getenv("APPDATA", "")
        programdata = os.getenv("PROGRAMDATA", "C:/ProgramData")
        start_menu_dirs = [
            pathlib.Path(appdata) / "Microsoft/Windows/Start Menu/Programs" if appdata else None,
            pathlib.Path(programdata) / "Microsoft/Windows/Start Menu/Programs",
        ]
        start_menu_dirs = [d for d in start_menu_dirs if d]

        self._desktop_shortcuts = _scan_shortcuts(desktop_dirs)
        self._start_menu_shortcuts = _scan_shortcuts(start_menu_dirs)
        self._all_shortcuts = {**self._start_menu_shortcuts, **self._desktop_shortcuts}

        logger.info(
            f"App manager: {len(APP_MAP)} static, "
            f"{len(self._desktop_shortcuts)} desktop, "
            f"{len(self._start_menu_shortcuts)} start-menu shortcuts"
        )

    def _resolve(self, app_name):
        """Return exe/lnk/ms-settings path to launch, or the raw name as fallback."""
        key = app_name.lower().strip()
        # Static exact
        if key in APP_MAP:
            return APP_MAP[key]
        # Static partial
        for k, v in APP_MAP.items():
            if key in k or k in key:
                return v
        # Desktop exact
        if key in self._desktop_shortcuts:
            return self._desktop_shortcuts[key]
        # Desktop partial
        for k, v in self._desktop_shortcuts.items():
            if key in k or k in key:
                return v
        # Start-menu exact
        if key in self._start_menu_shortcuts:
            return self._start_menu_shortcuts[key]
        # Start-menu partial
        for k, v in self._start_menu_shortcuts.items():
            if key in k or k in key:
                return v
        # Fuzzy match across all maps
        for candidates in (APP_MAP, self._all_shortcuts):
            fuzzy = _fuzzy_match(key, candidates)
            if fuzzy:
                return fuzzy
        # Raw fallback
        return key

    def _launch(self, resolved: str) -> bool:
        """Launch using the best available strategy. Returns True on success."""
        # 1. .lnk shortcut path
        if resolved.lower().endswith(".lnk") and os.path.isfile(resolved):
            os.startfile(resolved)
            return True

        # 2. Full .exe path that exists
        if resolved.lower().endswith(".exe") and os.path.isfile(resolved):
            os.startfile(resolved)
            return True

        # ms-settings: URI scheme
        if resolved.startswith("ms-"):
            os.startfile(resolved)
            return True

        exe_name = resolved if resolved.lower().endswith(".exe") else f"{resolved}.exe"

        # 3. PATH lookup
        which_path = shutil.which(exe_name)
        if which_path and os.path.isfile(which_path):
            os.startfile(which_path)
            return True

        # 4. Recursive scan in Program Files / AppData
        found = _find_exe(exe_name)
        if found:
            os.startfile(found)
            return True

        # 5. Last resort — start command
        subprocess.Popen(f'start "" "{resolved}"', shell=True)
        return True

    def open_app(self, app_name):
        resolved = self._resolve(app_name)
        logger.info(f"open_app '{app_name}' → '{resolved}'")
        try:
            self._launch(resolved)
            return {"success": True}
        except Exception as e:
            logger.error(f"Launch failed: {e}")
            return {"success": False, "error": str(e)}

    def open_app_with_llm_fallback(self, app_name):
        """Normal resolution → if it fails, ask Gemini, try again."""
        result = self.open_app(app_name)
        if result["success"]:
            return result
        try:
            from modules.llm_bridge import get_llm_bridge
            bridge = get_llm_bridge()
            if bridge.available:
                resolved = bridge.resolve_app_name(app_name)
                if resolved and resolved.lower() != app_name.lower():
                    logger.info(f"LLM suggested '{resolved}', retrying…")
                    return self.open_app(resolved)
        except Exception as e:
            logger.error(f"LLM fallback error: {e}")
        return result

    def close_app(self, app_name):
        key = app_name.lower().strip()
        exe = APP_MAP.get(key, key)
        process_stem = pathlib.Path(exe).stem.lower()
        killed = False
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                if process_stem in proc.info["name"].lower():
                    proc.kill()
                    killed = True
                    logger.info(f"Killed: {proc.info['name']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return {"success": killed}

    def open_folder(self, folder_path):
        """Open a folder in Windows Explorer."""
        key = folder_path.lower().strip().rstrip(" folder").strip()
        folder_map = _folder_map()
        target = folder_map.get(key)
        if target is None:
            for k, v in folder_map.items():
                if key in k or k in key:
                    target = v
                    break
        if target is None:
            from utils.helpers import resolve_user_folder
            target = resolve_user_folder(folder_path)
        logger.info(f"Opening folder: {target}")
        try:
            os.startfile(str(target))
            return {"success": True, "path": str(target)}
        except Exception as e:
            logger.error(f"Open folder error: {e}")
            return {"success": False, "error": str(e)}

    def refresh_shortcuts(self):
        self.__init__()
        logger.info("Shortcuts refreshed.")
