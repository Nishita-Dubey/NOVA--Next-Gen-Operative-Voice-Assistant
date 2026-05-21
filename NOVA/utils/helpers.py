"""
utils/helpers.py — Shared helpers for paths, time, and network checks.

Used by file_manager, application_manager, web_module, and response_generator.
"""

import datetime
import pathlib
import socket


def resolve_user_folder(folder_name: str) -> pathlib.Path:
    """
    Resolve a standard Windows user folder (Desktop, Documents, …),
    including OneDrive redirection when the folder lives under OneDrive.
    """
    key = folder_name.lower().strip().replace("my ", "")
    if key in ("home", ""):
        return pathlib.Path.home()
    if key in ("c drive", "c:"):
        return pathlib.Path("C:/")

    # Map spoken names to Windows folder names
    win_name = {
        "desktop": "Desktop",
        "documents": "Documents",
        "downloads": "Downloads",
        "pictures": "Pictures",
        "videos": "Videos",
        "music": "Music",
    }.get(key, folder_name.strip().title())

    home = pathlib.Path.home()
    candidates = [home / win_name]
    candidates.extend(home.glob(f"OneDrive*/{win_name}"))
    candidates.append(home / "OneDrive" / win_name)

    for path in candidates:
        if path.exists():
            return path
    return home / win_name  # fallback even if missing


def get_known_user_folders() -> dict[str, pathlib.Path]:
    """Spoken folder names → resolved paths on this PC (for open_folder intent)."""
    mapping = {
        "desktop": "Desktop",
        "documents": "Documents",
        "downloads": "Downloads",
        "pictures": "Pictures",
        "videos": "Videos",
        "music": "Music",
    }
    folders = {
        "home": pathlib.Path.home(),
        "c drive": pathlib.Path("C:/"),
        "c:": pathlib.Path("C:/"),
    }
    for spoken, win_name in mapping.items():
        path = resolve_user_folder(win_name)
        folders[spoken] = path
        folders[f"my {spoken}"] = path  # e.g. "my downloads"
    return folders


def get_time_greeting() -> str:
    """Morning / afternoon / evening based on local clock."""
    hour = datetime.datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"


def is_online() -> bool:
    """Quick connectivity check (Google DNS). Used before web/weather/STT."""
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except (socket.error, OSError):
        return False


def get_current_time() -> str:
    """12-hour clock string for time intent."""
    return datetime.datetime.now().strftime("%I:%M %p")


def get_current_date() -> str:
    """Long date string for date intent."""
    return datetime.datetime.now().strftime("%A, %d %B %Y")
