import os
from typing import override

from actions.action import StartWithAction
from common.command_utils import CommandUtils, CMD_RETURN_CODE_SUCCESS


class ApplyConfigAction(StartWithAction):
    @override
    def run(self):
        if not self._check_args_is_type(str):
            return False

        if CommandUtils.execute_command("cmd.exe", ["/c", "python", "apply_config.py", "--config", self.args]).returncode == CMD_RETURN_CODE_SUCCESS:
            print(f"Apply config [{self.args}] success")
            return True
        else:
            print(f"Apply config [{self.args}] failed")
            return False
