from typing import override
from actions.action import StartWithAction
from common.command_utils import CommandUtils, CMD_RETURN_CODE_SUCCESS


class RunAppAction(StartWithAction):
    label = "运行程序"
    args_label = "程序或文件路径"
    args_kind = "file"
    description = "启动指定的程序、快捷方式或文件。"
    order = 10

    @override
    def run(self)->bool:
        if not self._check_args_is_type(str):
            return False

        if CommandUtils.open("cmd.exe", ["/c", "start", "", self.args]) is not None:
            print(f"Run app [{self.args}] success")
            return True
        else:
            print(f"Run app [{self.args}] failed")
            return False

    @override
    def should_run_as_admin(self) -> bool:
        return True
