"""雷神加速操作：通过界面自动化让雷神加速指定游戏。"""
from datetime import datetime
from typing import override

from actions.action import StartWithAction
from common.paths import ACC_LOG_FILE, ensure_dirs

DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_TIMEOUT_SECONDS = 600.0


def reset_log(name: str) -> None:
    try:
        ensure_dirs()
        ACC_LOG_FILE.write_text(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 雷神加速：{name}\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def append_log(message: str) -> None:
    try:
        with open(ACC_LOG_FILE, "a", encoding="utf-8") as file:
            file.write(f"[{datetime.now():%H:%M:%S}] {message}\n")
    except OSError:
        pass


def parse_args(raw) -> tuple[str, float]:
    """支持「游戏名称」或「游戏名称|超时秒数」两种写法。"""
    text = str(raw).strip()
    timeout = DEFAULT_TIMEOUT_SECONDS
    if "|" in text:
        text, _, timeout_text = text.partition("|")
        text = text.strip()
        try:
            timeout = float(timeout_text.strip())
        except ValueError:
            return text, -1.0
        timeout = max(5.0, min(timeout, MAX_TIMEOUT_SECONDS))
    return text, timeout


class LeigodAccAction(StartWithAction):
    label = "雷神加速"
    args_label = "游戏名称（可加 |超时秒数）"
    args_kind = "text"
    description = "打开雷神并加速指定游戏，等待出现「加速中」；游戏需在雷神「我的加速」列表中。"
    order = 25

    @override
    def run(self) -> bool:
        name, timeout = parse_args(self.args)
        if not name:
            print("雷神加速游戏名称不能为空")
            return False
        if timeout < 0:
            print(f"雷神加速超时无效: {self.args}")
            return False

        reset_log(name)

        def log(message: str) -> None:
            print(message)
            append_log(message)

        comtypes = None
        try:
            try:
                import comtypes as _comtypes

                _comtypes.CoInitialize()
                comtypes = _comtypes
            except Exception:
                comtypes = None

            from common.leigod_driver import AcceleratorError, LeiGodDriver

            driver = LeiGodDriver(log)
            try:
                driver.accelerate_game(name, timeout=timeout)
            except AcceleratorError as exc:
                log(f"雷神加速失败: {exc}")
                return False
            log(f"雷神加速 [{name}] 成功")
            return True
        except Exception as exc:
            log(f"雷神加速失败: {exc}")
            return False
        finally:
            if comtypes is not None:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass

    @override
    def should_run_as_admin(self) -> bool:
        # 雷神客户端以管理员权限运行，普通进程无法读取其 UIA 控件树
        return True
