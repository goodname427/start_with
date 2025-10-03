from typing import override
from actions.action import StartWithAction


class RunAppAction(StartWithAction):
    @override
    def run(self)->bool:
        if not self._check_args_is_type(str):
            return False

        if StartWithAction._execute_cmd("cmd.exe", ["/c", "start", "", f"{self.args}"])["success"]:
            print(f"Running app: {self.args}")
            return True
        else:
            print(f"Failed to run app: {self.args}")
            return False
