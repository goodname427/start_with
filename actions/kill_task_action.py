from typing import override

from actions.action import StartWithAction
from common.command_utils import CommandUtils, CMD_RETURN_CODE_SUCCESS


class KillTaskAction(StartWithAction):
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
    def run_as_admin(self)->bool:
        return True
