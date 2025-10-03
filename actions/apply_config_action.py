import os
from typing import override

from actions.action import StartWithAction


class ApplyConfigAction(StartWithAction):
    @override
    def run(self):
        if not self._check_args_is_type(str):
            return False

        if StartWithAction._execute_cmd("cmd.exe", ["/c", "python", "apply_config.py", "--config", self.args])["success"]:
            print(f"Apply Config: {self.args} success")
            return True
        else:
            print(f"Apply Config: {self.args} failed")
            return False
