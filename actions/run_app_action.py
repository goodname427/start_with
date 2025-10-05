from typing import override
from actions.action import StartWithAction
from common.command_utils import CommandUtils, CMD_RETURN_CODE_SUCCESS


class RunAppAction(StartWithAction):
    @override
    def run(self)->bool:
        if not self._check_args_is_type(str):
            return False

        if CommandUtils.execute_command("cmd.exe", ["/c", "start", "", f"""{self.args}"""]).returncode == CMD_RETURN_CODE_SUCCESS:
            print(f"Run app [{self.args}] success")
            return True
        else:
            print(f"Run app [{self.args}] failed")
            return False

    @override
    def run_as_admin(self) -> bool:
        return True
