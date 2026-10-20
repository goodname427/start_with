"""停止雷神加速，可选关闭雷神客户端。"""
from typing import override

from actions.action import StartWithAction
from common import accelerator_log
from common.command_utils import CommandUtils

QUIT_TOKENS = {"quit", "exit", "close", "关闭", "退出"}


class LeigodStopAction(StartWithAction):
    label = "停止雷神加速"
    args_label = "stop / quit（quit 同时关闭雷神）"
    args_kind = "text"
    description = "停止雷神当前的加速；参数写 quit 时会同时关闭雷神客户端。"
    order = 26

    @override
    def run(self) -> bool:
        mode = str(self.args).strip().lower()
        quit_client = mode in QUIT_TOKENS
        accelerator_log.reset("停止雷神加速" + ("并关闭客户端" if quit_client else ""))

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
                if driver.find_window() is None:
                    log("雷神未运行，跳过停止加速")
                else:
                    driver.stop()
            except AcceleratorError as exc:
                log(f"停止雷神加速失败: {exc}")

            if quit_client:
                self._quit_leigod(log)
            log("停止雷神加速完成")
            return True
        except Exception as exc:
            log(f"停止雷神加速失败: {exc}")
            return False
        finally:
            if comtypes is not None:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass

    @staticmethod
    def _quit_leigod(log) -> None:
        for name in ("leigod.exe", "leishenSdk.exe"):
            result = CommandUtils.execute_command("taskkill", ["/F", "/IM", name])
            if result.returncode == 0:
                log(f"已关闭进程 {name}")

    @override
    def should_run_as_admin(self) -> bool:
        return True
