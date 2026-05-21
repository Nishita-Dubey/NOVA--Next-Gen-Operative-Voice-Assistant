"""
modules/file_manager.py — File and folder search + open for NOVA.

Search order: Desktop → Documents → Downloads → … → PowerShell → shallow walk.
open_folder: KNOWN_FOLDERS first (via utils.helpers), then search by name.
open_file: os.startfile() after resolving path on disk.
"""

import os
import pathlib
import subprocess
import time
from utils.helpers import get_known_user_folders, resolve_user_folder
from utils.logger import get_logger

logger = get_logger("file_manager")

HOME = pathlib.Path.home()


def _known_folders() -> dict[str, pathlib.Path]:
    return get_known_user_folders()


def _priority_dirs() -> list[pathlib.Path]:
    folders = _known_folders()
    order = ["desktop", "documents", "downloads", "pictures", "videos", "music"]
    dirs = []
    seen = set()
    for key in order:
        p = folders.get(key)
        if p and p.exists() and str(p) not in seen:
            dirs.append(p)
            seen.add(str(p))
    if HOME.exists() and str(HOME) not in seen:
        dirs.append(HOME)
    return dirs


SKIP_DIRS = {
    "$recycle.bin", "windows", "system32", "syswow64",
    "programdata", "recovery", "boot", "__pycache__",
    "node_modules", ".git", "appdata", "program files",
}


def _should_skip(path: pathlib.Path) -> bool:
    return path.name.lower() in SKIP_DIRS or path.name.startswith(".")


def _powershell_search(name: str, timeout: int = 8, files_only: bool = True) -> list[str]:
    """Search user profile via PowerShell."""
    safe_name = name.replace("'", "''").replace('"', '')
    type_filter = "-File" if files_only else ""
    cmd = (
        f"$dirs = @($env:USERPROFILE, "
        f"'$env:USERPROFILE\\Desktop', '$env:USERPROFILE\\Documents', "
        f"'$env:USERPROFILE\\Downloads', '$env:USERPROFILE\\OneDrive'); "
        f"foreach ($d in $dirs) {{ if (Test-Path $d) {{ "
        f"Get-ChildItem -Path $d -Recurse -Filter '*{safe_name}*' {type_filter} "
        f"-ErrorAction SilentlyContinue -Depth 6 | "
        f"Select-Object -First 5 -ExpandProperty FullName }}}}"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.stdout.strip():
            return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.warning(f"PowerShell search failed: {e}")
    return []


def _search_dir_shallow(directory: pathlib.Path, name: str, is_dir: bool,
                        max_depth: int = 4) -> list[str]:
    results = []
    name_lower = name.lower()

    def _walk(path: pathlib.Path, depth: int):
        if depth > max_depth or len(results) >= 10:
            return
        try:
            for entry in path.iterdir():
                if _should_skip(entry):
                    continue
                if is_dir and entry.is_dir() and name_lower in entry.name.lower():
                    results.append(str(entry))
                elif not is_dir and entry.is_file() and name_lower in entry.name.lower():
                    results.append(str(entry))
                if len(results) >= 10:
                    return
                if entry.is_dir() and depth < max_depth:
                    _walk(entry, depth + 1)
        except (PermissionError, OSError):
            pass

    if directory.exists():
        _walk(directory, 0)
    return results


class FileManager:
    """Find, open, and create files/folders on the local machine."""

    def find_file(self, filename: str, max_results: int = 10) -> dict:
        """Partial name search; returns up to max_results full paths."""
        filename = filename.strip().lower()
        results = []
        seen = set()

        for directory in _priority_dirs():
            if len(results) >= max_results:
                break
            for path in _search_dir_shallow(directory, filename, is_dir=False):
                if path not in seen:
                    seen.add(path)
                    results.append(path)

        if len(results) < max_results:
            for path in _powershell_search(filename, timeout=8, files_only=True):
                if path not in seen and os.path.isfile(path):
                    seen.add(path)
                    results.append(path)
                    if len(results) >= max_results:
                        break

        logger.info(f"find_file('{filename}'): {len(results)} results")
        return {"success": bool(results), "files": results}

    def find_folder(self, folder_name: str, max_results: int = 5) -> dict:
        folder_name = folder_name.strip().lower()
        results = []
        seen = set()

        for directory in _priority_dirs():
            if len(results) >= max_results:
                break
            for path in _search_dir_shallow(directory, folder_name, is_dir=True):
                if path not in seen:
                    seen.add(path)
                    results.append(path)

        if len(results) < max_results:
            for path in _powershell_search(folder_name, timeout=8, files_only=False):
                if path not in seen and os.path.isdir(path):
                    seen.add(path)
                    results.append(path)
                    if len(results) >= max_results:
                        break

        logger.info(f"find_folder('{folder_name}'): {len(results)} results")
        return {"success": bool(results), "folders": results}

    def open_file(self, filepath: str) -> dict:
        """Open with default app; search disk if only a filename was given."""
        filepath = filepath.strip()
        p = pathlib.Path(filepath)

        if p.exists() and p.is_file():
            return self._start_file(p)

        search_name = p.name if p.name else filepath
        ps_results = _powershell_search(search_name, timeout=8, files_only=True)
        for candidate in ps_results:
            if os.path.isfile(candidate):
                logger.info(f"PowerShell resolved '{filepath}' → '{candidate}'")
                return self._start_file(pathlib.Path(candidate))

        found = self.find_file(search_name)
        if found["success"]:
            p = pathlib.Path(found["files"][0])
            logger.info(f"Search resolved '{filepath}' → '{p}'")
            return self._start_file(p)

        return {"success": False, "error": f"File '{filepath}' not found on this device."}

    def _start_file(self, p: pathlib.Path) -> dict:
        try:
            os.startfile(str(p))
            return {"success": True, "path": str(p)}
        except Exception as e:
            logger.error(f"open_file error: {e}")
            return {"success": False, "error": str(e)}

    def open_folder(self, folder_path: str) -> dict:
        """Open folder in Explorer; resolve known names or search by name."""
        folder_path = folder_path.strip()
        key = folder_path.lower().strip().rstrip(" folder").strip()
        known = _known_folders()

        p = known.get(key)
        if p is None:
            for k, v in known.items():
                if key in k or k in key:
                    p = v
                    break

        if p is None:
            p = resolve_user_folder(folder_path)

        if not p.exists():
            found = self.find_folder(folder_path)
            if found["success"]:
                p = pathlib.Path(found["folders"][0])
                logger.info(f"Resolved folder '{folder_path}' → '{p}'")
            else:
                return {"success": False, "error": f"Folder '{folder_path}' not found."}

        try:
            os.startfile(str(p))
            return {"success": True, "path": str(p)}
        except Exception as e:
            logger.error(f"open_folder error: {e}")
            return {"success": False, "error": str(e)}

    def create_folder(self, folder_name: str) -> dict:
        try:
            desktop = resolve_user_folder("Desktop")
            target = desktop / folder_name
            target.mkdir(parents=True, exist_ok=True)
            logger.info(f"Folder created: {target}")
            return {"success": True, "path": str(target)}
        except Exception as e:
            logger.error(f"create_folder error: {e}")
            return {"success": False, "error": str(e)}
