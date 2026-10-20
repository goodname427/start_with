"""Windows 系统托盘图标（基于 pywin32），支持右键菜单与气泡通知。"""
import logging
import threading
import time

import win32api
import win32con
import win32gui

from common.paths import GUI_ASSETS_DIR

logger = logging.getLogger(__name__)


def _build_icon_image():
    """绘制应用图标：深蓝渐变底 + 斜向起飞的火箭，表达“启动/应用配置”。"""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    size = 1024
    center = size // 2
    top = (67, 56, 202)
    bottom = (29, 78, 216)

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gradient = Image.new("RGBA", (size, size))
    gradient_draw = ImageDraw.Draw(gradient)
    for y in range(size):
        ratio = y / (size - 1)
        color = tuple(round(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)) + (255,)
        gradient_draw.line([(0, y), (size, y)], fill=color)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (28, 28, size - 28, size - 28), radius=236, fill=255
    )
    image.paste(gradient, (0, 0), mask)

    # 中心柔光
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        (center - 360, center - 360, center + 360, center + 360),
        fill=(129, 140, 248, 95),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    glow.putalpha(ImageChops.multiply(glow.getchannel("A"), mask))
    image = Image.alpha_composite(image, glow)

    # 背景轨道
    orbit = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(orbit).ellipse(
        (center - 430, center - 310, center + 430, center + 310),
        outline=(255, 255, 255, 38),
        width=6,
    )
    orbit = orbit.rotate(24, resample=Image.Resampling.BICUBIC, center=(center, center))
    orbit.putalpha(ImageChops.multiply(orbit.getchannel("A"), mask))
    image = Image.alpha_composite(image, orbit)

    # 顶部高光
    gloss = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(gloss).ellipse(
        (-280, -760, size + 280, 460), fill=(255, 255, 255, 30)
    )
    gloss = gloss.filter(ImageFilter.GaussianBlur(60))
    gloss.putalpha(ImageChops.multiply(gloss.getchannel("A"), mask))
    image = Image.alpha_composite(image, gloss)

    rocket = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(rocket)

    # 尾焰
    draw.polygon(
        [(center - 60, center + 290), (center, center + 470), (center + 60, center + 290)],
        fill=(251, 146, 60, 255),
    )
    draw.polygon(
        [(center - 28, center + 300), (center, center + 400), (center + 28, center + 300)],
        fill=(254, 240, 138, 255),
    )

    # 机身与尾翼
    silhouette = [
        (center, center - 330),
        (center + 95, center - 170),
        (center + 95, center + 70),
        (center + 180, center + 230),
        (center + 95, center + 245),
        (center + 95, center + 260),
        (center - 95, center + 260),
        (center - 95, center + 245),
        (center - 180, center + 230),
        (center - 95, center + 70),
        (center - 95, center - 170),
    ]
    draw.polygon(silhouette, fill=(248, 250, 252, 255))

    # 机身侧面阴影
    body_shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(body_shadow).polygon(
        [
            (center + 40, center - 220),
            (center + 95, center - 170),
            (center + 95, center + 245),
            (center + 40, center + 245),
        ],
        fill=(15, 23, 42, 26),
    )
    body_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(body_mask).polygon(silhouette, fill=255)
    body_shadow.putalpha(ImageChops.multiply(body_shadow.getchannel("A"), body_mask))
    rocket = Image.alpha_composite(rocket, body_shadow)
    draw = ImageDraw.Draw(rocket)

    # 喷口
    draw.rounded_rectangle(
        (center - 64, center + 230, center + 64, center + 300),
        radius=22,
        fill=(203, 213, 225, 255),
    )

    # 舷窗
    draw.ellipse((center - 78, center - 120, center + 78, center + 36), fill=(30, 64, 175, 255))
    draw.ellipse((center - 64, center - 106, center + 64, center + 22), fill=(37, 99, 235, 255))
    draw.ellipse(
        (center - 46, center - 88, center + 12, center - 18),
        fill=(147, 197, 253, 185),
    )

    rocket = rocket.rotate(-40, resample=Image.Resampling.BICUBIC, center=(center, center))
    image = Image.alpha_composite(image, rocket)
    return image.resize((512, 512), Image.Resampling.LANCZOS)


def ensure_tray_icon() -> str | None:
    """生成/复用托盘与应用图标，返回 ico 路径。"""
    icon_path = GUI_ASSETS_DIR / "icon.ico"
    if icon_path.exists():
        return str(icon_path)

    try:
        from PIL import Image  # noqa: F401
    except Exception:
        logger.warning("未安装 Pillow，跳过图标生成")
        return None

    try:
        GUI_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        image = _build_icon_image()
        image.save(
            icon_path,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
        return str(icon_path)
    except Exception:
        logger.exception("生成托盘图标失败")
        return None


class TrayIcon:
    """隐藏窗口 + Shell_NotifyIcon，实现右下角托盘图标。"""

    WM_TRAY = win32con.WM_USER + 20

    def __init__(self, tooltip: str, menu_provider, on_command):
        self._tooltip = tooltip
        self._menu_provider = menu_provider
        self._on_command = on_command
        self._icon_path = ensure_tray_icon()

        self._hwnd = None
        self._hicon = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: Exception | None = None
        self._taskbar_created = 0
        self._class_name = f"StartWithTrayWnd_{win32api.GetCurrentProcessId()}"
        self._menu_ids: dict[int, str] = {}
        self._menu_counter = 1000
        self._last_menu_time = 0.0

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="tray-icon", daemon=True)
        self._thread.start()
        if not self._ready.wait(5):
            raise RuntimeError("系统托盘初始化超时")
        if self._error is not None:
            raise self._error

    def stop(self) -> None:
        hwnd = self._hwnd
        if not hwnd:
            return
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (hwnd, 0))
        except Exception:
            pass
        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        except Exception:
            pass

    def set_tooltip(self, text: str) -> None:
        self._tooltip = text
        if not self._hwnd:
            return
        try:
            win32gui.Shell_NotifyIcon(
                win32gui.NIM_MODIFY,
                (self._hwnd, 0, win32gui.NIF_TIP, self.WM_TRAY, self._hicon, text),
            )
        except Exception:
            logger.warning("更新托盘提示失败", exc_info=True)

    def notify(self, title: str, message: str) -> None:
        if not self._hwnd:
            return
        try:
            # pywin32 的 NOTIFYICONDATA 元组顺序：
            # (hwnd, id, flags, callbackMessage, hicon, tip, info, timeout, infoTitle, infoFlags)
            win32gui.Shell_NotifyIcon(
                win32gui.NIM_MODIFY,
                (
                    self._hwnd,
                    0,
                    win32gui.NIF_INFO,
                    self.WM_TRAY,
                    self._hicon,
                    self._tooltip,
                    message,
                    5000,
                    title,
                    win32gui.NIIF_INFO,
                ),
            )
        except Exception:
            logger.warning("显示托盘通知失败", exc_info=True)

    # ---------------------------------------------------------------- 内部实现

    def _run(self) -> None:
        try:
            wc = win32gui.WNDCLASS()
            wc.hInstance = win32api.GetModuleHandle(None)
            wc.lpszClassName = self._class_name
            wc.lpfnWndProc = self._wnd_proc
            win32gui.RegisterClass(wc)

            self._hwnd = win32gui.CreateWindow(
                self._class_name,
                "StartWith",
                win32con.WS_OVERLAPPED,
                0,
                0,
                0,
                0,
                0,
                0,
                wc.hInstance,
                None,
            )
            if not self._hwnd:
                raise RuntimeError("创建托盘窗口失败")

            try:
                self._taskbar_created = win32gui.RegisterWindowMessage("TaskbarCreated")
            except Exception:
                self._taskbar_created = 0

            self._hicon = self._load_icon()
            self._add_icon()
            self._ready.set()
            win32gui.PumpMessages()
        except Exception as exc:
            self._error = exc
            logger.exception("系统托盘初始化失败")
            self._ready.set()

    def _load_icon(self):
        if self._icon_path:
            try:
                icon_w = win32api.GetSystemMetrics(win32con.SM_CXSMICON) or 16
                icon_h = win32api.GetSystemMetrics(win32con.SM_CYSMICON) or 16
                handle = win32gui.LoadImage(
                    0,
                    self._icon_path,
                    win32con.IMAGE_ICON,
                    icon_w,
                    icon_h,
                    win32con.LR_LOADFROMFILE,
                )
                if handle:
                    return handle
            except Exception:
                logger.warning("加载托盘图标失败", exc_info=True)
        return win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

    def _add_icon(self) -> None:
        if not self._hwnd:
            return
        try:
            flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
            win32gui.Shell_NotifyIcon(
                win32gui.NIM_ADD,
                (self._hwnd, 0, flags, self.WM_TRAY, self._hicon, self._tooltip),
            )
        except Exception:
            logger.exception("添加托盘图标失败")

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == self.WM_TRAY:
                mouse_msg = lparam & 0xFFFF
                if mouse_msg in (win32con.WM_RBUTTONUP, win32con.WM_CONTEXTMENU):
                    self._show_menu()
                elif mouse_msg in (win32con.WM_LBUTTONUP, win32con.WM_LBUTTONDBLCLK):
                    self._emit("open")
            elif self._taskbar_created and msg == self._taskbar_created:
                self._add_icon()
            elif msg == win32con.WM_CLOSE:
                try:
                    win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (hwnd, 0))
                except Exception:
                    pass
                win32gui.DestroyWindow(hwnd)
            elif msg == win32con.WM_DESTROY:
                win32gui.PostQuitMessage(0)
        except Exception:
            logger.exception("托盘消息处理失败")
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _build_menu(self, items: list[dict]):
        menu = win32gui.CreatePopupMenu()
        for item in items:
            if item.get("separator"):
                win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
                continue

            flags = win32con.MF_STRING
            if item.get("checked"):
                flags |= win32con.MF_CHECKED
            if item.get("enabled") is False:
                flags |= win32con.MF_GRAYED

            children = item.get("children")
            if children:
                submenu = self._build_menu(children)
                win32gui.AppendMenu(menu, flags | win32con.MF_POPUP, submenu, item.get("label", ""))
            else:
                self._menu_counter += 1
                command_id = self._menu_counter
                key = item.get("key")
                if key:
                    self._menu_ids[command_id] = key
                win32gui.AppendMenu(menu, flags, command_id, item.get("label", ""))
        return menu

    def _show_menu(self) -> None:
        now = time.monotonic()
        if now - self._last_menu_time < 0.25:
            return
        self._last_menu_time = now

        try:
            items = self._menu_provider() or []
        except Exception:
            logger.exception("生成托盘菜单失败")
            items = [
                {"label": "打开控制面板", "key": "open"},
                {"separator": True},
                {"label": "退出", "key": "quit"},
            ]

        self._menu_ids = {}
        self._menu_counter = 1000
        menu = self._build_menu(items)
        try:
            win32gui.SetForegroundWindow(self._hwnd)
        except Exception:
            pass

        x, y = win32gui.GetCursorPos()
        try:
            command_id = win32gui.TrackPopupMenu(
                menu,
                win32con.TPM_LEFTALIGN
                | win32con.TPM_TOPALIGN
                | win32con.TPM_RIGHTBUTTON
                | win32con.TPM_RETURNCMD,
                x,
                y,
                0,
                self._hwnd,
                None,
            )
            win32gui.PostMessage(self._hwnd, win32con.WM_NULL, 0, 0)
        finally:
            win32gui.DestroyMenu(menu)

        key = self._menu_ids.get(command_id) if command_id else None
        if key:
            self._emit(key)

    def _emit(self, key: str) -> None:
        try:
            self._on_command(key)
        except Exception:
            logger.exception("执行托盘命令失败: %s", key)
