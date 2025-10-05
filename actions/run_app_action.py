from typing import override
from actions.action import StartWithAction
from common.command_utils import CommandUtils, CMD_RETURN_CODE_SUCCESS


class RunAppAction(StartWithAction):
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
