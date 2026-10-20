"""雷神加速器自动化驱动（基于 Windows UIA，需要管理员权限）。

雷神客户端是 Electron 应用且以管理员权限运行，普通权限进程无法读取其
UIA 控件树，也无法向窗口发送输入，因此调用方必须先提权。
"""
from __future__ import annotations

import os
import re
import subprocess
import time
import winreg
from pathlib import Path
from typing import Callable

WINDOW_TITLE = "雷神加速器"
LAUNCHER_NAME = "leigod_launcher.exe"
SIDEBAR_WIDTH = 220
START_TEXTS = {"开始加速"}
LAUNCH_TEXTS = {"启动游戏"}
RUNNING_TEXTS = {"加速中", "已加速"}
STOP_TEXTS = {"停止加速", "结束加速", "暂停时长"}


class AcceleratorError(RuntimeError):
    """雷神加速过程中的可预期错误。"""


def _iter_install_locations():
    roots = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
    subkeys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    views = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)
    for root in roots:
        for subkey in subkeys:
            for view in views:
                try:
                    key = winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | view)
                except OSError:
                    continue
                try:
                    for index in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            name = winreg.EnumKey(key, index)
                            with winreg.OpenKey(key, name) as item:
                                try:
                                    display = str(winreg.QueryValueEx(item, "DisplayName")[0])
                                except OSError:
                                    continue
                                if "雷神" not in display and "leigod" not in display.lower():
                                    continue
                                for value_name in ("InstallLocation", "DisplayIcon"):
                                    try:
                                        raw = str(winreg.QueryValueEx(item, value_name)[0]).strip()
                                    except OSError:
                                        continue
                                    if not raw:
                                        continue
                                    candidate = Path(raw.split(",")[0].strip().strip('"'))
                                    if candidate.suffix.lower() == ".exe":
                                        candidate = candidate.parent
                                    yield candidate
                        except OSError:
                            continue
                finally:
                    key.Close()


def find_launcher() -> Path | None:
    """查找 leigod_launcher.exe：优先注册表，其次常见安装目录。"""
    candidates: list[Path] = []
    for directory in _iter_install_locations():
        candidates.append(directory / LAUNCHER_NAME)
    for env_name in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(env_name)
        if not base:
            continue
        candidates.append(Path(base) / "LeiGod_Acc" / LAUNCHER_NAME)
        if env_name == "LOCALAPPDATA":
            candidates.append(Path(base) / "Programs" / "LeiGod_Acc" / LAUNCHER_NAME)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class LeiGodDriver:
    """通过 UIA 操作雷神客户端：打开指定游戏并开始加速。"""

    def __init__(self, log: Callable[[str], None] | None = None):
        self._log_callback = log
        self._desktop = None
        self._window = None

    # ------------------------------------------------------------------ 日志

    def _log(self, message: str) -> None:
        if self._log_callback is not None:
            try:
                self._log_callback(message)
            except Exception:
                pass

    # ------------------------------------------------------------------ 窗口

    @staticmethod
    def _desktop_backend():
        from pywinauto import Desktop

        return Desktop(backend="uia")

    def find_window(self):
        if self._desktop is None:
            self._desktop = self._desktop_backend()
        for window in self._desktop.windows():
            try:
                if WINDOW_TITLE in window.window_text():
                    return window
            except Exception:
                continue
        return None

    def ensure_running(self, timeout: float = 60.0) -> bool:
        window = self.find_window()
        if window is not None:
            self._window = window
            return True

        launcher = find_launcher()
        if launcher is None:
            raise AcceleratorError("未找到雷神加速器启动器，请先安装雷神加速器或手动启动客户端")
        self._log(f"启动雷神加速器：{launcher}")
        try:
            subprocess.Popen(
                [str(launcher)],
                cwd=str(launcher.parent),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            raise AcceleratorError(f"启动雷神加速器失败：{exc}") from exc

        deadline = time.monotonic() + max(5.0, float(timeout))
        while time.monotonic() < deadline:
            time.sleep(1.0)
            window = self.find_window()
            if window is not None:
                self._window = window
                self._log("雷神加速器已启动")
                return True
        raise AcceleratorError(f"等待雷神加速器窗口超时（{timeout:g} 秒）")

    def _focus(self):
        window = self._window or self.find_window()
        if window is None:
            raise AcceleratorError("雷神加速器未运行")
        self._window = window
        try:
            window.set_focus()
        except Exception:
            pass
        time.sleep(0.3)
        return window

    # ------------------------------------------------------------------ 控件

    def _visible_controls(self, types: set[str] | None = None):
        window = self._window
        if window is None:
            return []
        controls = []
        for child in window.descendants():
            try:
                info = child.element_info
                if types is not None and info.control_type not in types:
                    continue
                rect = child.rectangle()
                if rect.width() <= 0 or rect.height() <= 0:
                    continue
                controls.append((child, info.control_type, child.window_text(), rect))
            except Exception:
                continue
        return controls

    def _find_text(self, names: set[str], sidebar: bool | None = None):
        window = self._window
        if window is None:
            return None
        window_rect = window.rectangle()
        sidebar_edge = window_rect.left + SIDEBAR_WIDTH
        for child, control_type, text, rect in self._visible_controls({"Text", "Button"}):
            if text not in names:
                continue
            if sidebar is True and rect.left >= sidebar_edge:
                continue
            if sidebar is False and rect.left < sidebar_edge:
                continue
            return child, text, rect
        return None

    @staticmethod
    def _normalize_game_name(value: str) -> str:
        return re.sub(r"[\s:：\-_·™®©]+", "", value).casefold()

    def _find_game_item(self, names: list[str]):
        window = self._window
        if window is None:
            return None
        window_rect = window.rectangle()
        sidebar_edge = window_rect.left + SIDEBAR_WIDTH

        candidates = [
            self._normalize_game_name(str(name))
            for name in names
            if str(name).strip()
        ]
        items = []
        for child, control_type, text, rect in self._visible_controls({"Text", "Button"}):
            if rect.left >= sidebar_edge:
                continue
            normalized = self._normalize_game_name(text)
            if normalized:
                items.append((child, text.strip(), rect, normalized))

        for candidate in candidates:
            for item in items:
                if item[3] == candidate:
                    return item[0], item[1], item[2]

        for candidate in candidates:
            if len(candidate) < 4:
                continue
            for item in items:
                if len(item[3]) < 4:
                    continue
                if candidate in item[3] or item[3] in candidate:
                    return item[0], item[1], item[2]
        return None

    def _is_accelerating(self) -> bool:
        for _, _, text, _ in self._visible_controls({"Text"}):
            if text in RUNNING_TEXTS:
                return True
        return False

    def _status_texts(self, limit: int = 12) -> str:
        texts = [
            text
            for _, _, text, _ in self._visible_controls({"Text"})
            if text and len(text) <= 24
        ]
        return "、".join(texts[-limit:])

    # ------------------------------------------------------------------ 操作

    def open_game(self, game_names: str | list[str]) -> str:
        names = [game_names] if isinstance(game_names, str) else list(game_names)
        names = [str(name).strip() for name in names if str(name).strip()]
        if not names:
            raise AcceleratorError("未填写雷神加速游戏名称")
        self._focus()

        found = self._find_game_item(names)
        if found is None:
            raise AcceleratorError(
                f"未在雷神「我的加速」中找到 [{' / '.join(names)}]，"
                "请先在雷神客户端打开该游戏并加入「我的加速」"
            )

        child, text, rect = found
        self._log(f"打开雷神游戏：{text}（匹配：{' / '.join(names)}）")
        child.click_input()
        time.sleep(1.5)
        if self._find_text(START_TEXTS | LAUNCH_TEXTS, sidebar=False) is None:
            time.sleep(1.0)
            if self._find_text(START_TEXTS | LAUNCH_TEXTS, sidebar=False) is None:
                raise AcceleratorError(f"打开游戏 [{text}] 失败，未进入游戏详情页")
        return text

    def start(self, timeout: float = 120.0) -> bool:
        self._focus()
        if self._is_accelerating():
            self._log("雷神已经在加速中，跳过开始加速")
            return True

        found = self._find_text(START_TEXTS, sidebar=False)
        if found is None:
            raise AcceleratorError("未找到雷神「开始加速」按钮，请确认已进入游戏详情页")
        self._log("点击雷神「开始加速」")
        found[0].click_input()

        deadline = time.monotonic() + max(5.0, float(timeout))
        while time.monotonic() < deadline:
            time.sleep(0.8)
            if self._is_accelerating():
                self._log("雷神已开始加速")
                return True
        raise AcceleratorError(
            f"等待雷神加速超时（{timeout:g} 秒）。当前界面：{self._status_texts()}"
        )

    def accelerate_game(self, game_names: str | list[str], timeout: float = 120.0) -> str:
        self.ensure_running()
        matched = self.open_game(game_names)
        self.start(timeout)
        return matched

    def launch_game(self) -> bool:
        self._focus()
        found = self._find_text(LAUNCH_TEXTS, sidebar=False)
        if found is None:
            raise AcceleratorError("未找到雷神「启动游戏」按钮")
        found[0].click_input()
        self._log("已点击雷神「启动游戏」")
        time.sleep(1.0)
        return True

    def stop(self) -> bool:
        self._focus()
        found = self._find_text(STOP_TEXTS, sidebar=False)
        if found is None:
            return False
        found[0].click_input()
        time.sleep(1.0)
        for name in ("确定", "确认", "暂停"):
            dialog = self._find_text({name})
            if dialog is not None:
                try:
                    dialog[0].click_input()
                except Exception:
                    pass
                break
        self._log("已停止雷神加速")
        return True
