"""
modules/system_controller.py — OS-level controls (Windows-focused).

Volume via pycaw; screenshot via Pillow; power actions via shell commands.
"""

import os
import sys
import psutil
from utils.logger import get_logger

logger = get_logger("system")


class SystemController:
    """Volume, lock, screenshot, system stats, battery, shutdown/restart/sleep."""

    def get_volume(self) -> int:
        """Return master volume 0–100, or -1 on error."""
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            scalar = volume.GetMasterVolumeLevelScalar()
            return int(scalar * 100)
        except Exception as e:
            logger.error(f"Get volume error: {e}")
            return -1

    def set_volume(self, level: int) -> bool:
        """Set master volume to level (clamped 0–100)."""
        level = max(0, min(100, level))
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(level / 100, None)
            logger.info(f"Volume set to {level}%")
            return True
        except Exception as e:
            logger.error(f"Set volume error: {e}")
            os.system(f"nircmd.exe setsysvolume {int(level * 655.35)}")
            return False

    def change_volume(self, delta: int) -> int:
        """Increase or decrease volume by delta; returns new level."""
        current = self.get_volume()
        new_level = max(0, min(100, current + delta))
        self.set_volume(new_level)
        return new_level

    def mute(self):
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMute(1, None)
            return True
        except Exception as e:
            logger.error(f"Mute error: {e}")
            return False

    def unmute(self):
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMute(0, None)
            return True
        except Exception as e:
            logger.error(f"Unmute error: {e}")
            return False

    def lock_screen(self):
        """Lock workstation (Win) or equivalent on other OS."""
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        elif sys.platform == "darwin":
            os.system("pmset displaysleepnow")
        else:
            os.system("gnome-screensaver-command -l")

    def take_screenshot(self):
        """Save full-screen PNG in current working directory."""
        try:
            from PIL import ImageGrab
            import datetime
            filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            img = ImageGrab.grab()
            img.save(filename)
            logger.info(f"Screenshot saved: {filename}")
            return {"success": True, "file": filename}
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return {"success": False}

    def get_system_info(self) -> dict:
        """CPU, RAM, and disk usage percentages."""
        return {
            "cpu": psutil.cpu_percent(interval=1),
            "ram": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage("/").percent,
        }

    def get_battery(self) -> dict:
        """Battery percent and charging state; percent=-1 if unavailable."""
        battery = psutil.sensors_battery()
        if battery:
            return {"percent": int(battery.percent), "plugged": battery.power_plugged}
        return {"percent": -1, "plugged": False}

    def shutdown(self):
        if sys.platform == "win32":
            os.system("shutdown /s /t 5")
        else:
            os.system("shutdown -h now")

    def restart(self):
        if sys.platform == "win32":
            os.system("shutdown /r /t 5")
        else:
            os.system("reboot")

    def sleep(self):
        if sys.platform == "win32":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        elif sys.platform == "darwin":
            os.system("pmset sleepnow")
        else:
            os.system("systemctl suspend")
