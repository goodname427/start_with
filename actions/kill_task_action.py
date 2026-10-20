from typing import override

from actions.action import StartWithAction
from common.command_utils import CommandUtils, CMD_RETURN_CODE_SUCCESS


class KillTaskAction(StartWithAction):
    label = "结束进程"
    args_label = "进程名称（如 game.exe）"
    args_kind = "process"
    description = "强制结束指定名称的进程，应用时需要管理员权限。"
    order = 30

    @override
    def run(self)-> bool:
        if not self._check_args_is_type(str):
            return False

        if CommandUtils.execute_command("taskkill", ["/F", "/IM", self.args]).returncode == CMD_RETURN_CODE_SUCCESS:
            print(f"Kill task [{self.args}] success")
            return True
        else:
            print(f"Kill task [{self.args}] failed")
            return False

    @override
    def should_run_as_admin(self)->bool:
        return True
