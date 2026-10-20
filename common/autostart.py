"""开机自启动（写入 HKCU Run 项）。"""
import sys
import winreg
from pathlib import Path

from common.paths import APP_ROOT

APP_RUN_NAME = "StartWithGUI"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _pythonw() -> str:
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return str(candidate if candidate.exists() else exe)


def build_command() -> str:
    script = APP_ROOT / "start_with_gui.py"
    return f'"{_pythonw()}" "{script}" --silent'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_RUN_NAME)
    except OSError:
        return False
    return str(value).strip().lower() == build_command().strip().lower()


def set_enabled(enabled: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_RUN_NAME, 0, winreg.REG_SZ, build_command())
        else:
            try:
                winreg.DeleteValue(key, APP_RUN_NAME)
            except FileNotFoundError:
                pass
