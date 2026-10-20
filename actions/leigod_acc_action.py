"""雷神加速操作：通过界面自动化让雷神加速当前绑定/启动的应用。"""
from typing import override

from actions.action import StartWithAction
from common import accelerator_log

DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_TIMEOUT_SECONDS = 600.0
AUTO_TOKENS = {"", "auto", "自动"}
CONTEXT_KEYS = ("app_folder", "app_title", "app_product", "app_stem", "app_name")


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


def resolve_candidates(raw_name: str, variables: dict[str, str]) -> list[str]:
    """auto / 空参数时，从当前应用自动推导可能的雷神游戏名。"""
    if raw_name and raw_name.casefold() not in AUTO_TOKENS:
        return [raw_name]

    candidates: list[str] = []
    for key in CONTEXT_KEYS:
        value = str(variables.get(key) or "").strip()
        if value and value not in candidates:
            candidates.append(value)
    return candidates


class LeigodAccAction(StartWithAction):
    label = "雷神加速"
    args_label = "游戏名称 / auto（可加 |超时秒数）"
    args_kind = "text"
    description = "打开雷神并加速当前绑定的应用；auto 会根据启动的 exe 所在文件夹和文件描述自动匹配。"
    order = 25

    @override
    def run(self) -> bool:
        raw_name, timeout = parse_args(self.args)
        if timeout < 0:
            print(f"雷神加速超时无效: {self.args}")
            return False

        candidates = resolve_candidates(raw_name, getattr(self, "variables", {}) or {})
        if not candidates:
            print("雷神加速：无法从当前应用推断游戏名称，请填写名称或通过 --var 传入")
            return False

        accelerator_log.reset(f"雷神加速：{' / '.join(candidates)}")

        def log(message: str) -> None:
            print(message)
            accelerator_log.append(message)

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
                matched = driver.accelerate_game(candidates, timeout=timeout)
            except AcceleratorError as exc:
                log(f"雷神加速失败: {exc}")
                return False
            log(f"雷神加速 [{matched}] 成功")
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
