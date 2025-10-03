from typing import override

from actions.action import StartWithAction


class KillTaskAction(StartWithAction):
    @override
    def run(self)-> bool:
        if not self._check_args_is_type(str):
            return False

        if StartWithAction._execute_cmd("taskkill", ["/F", "/IM", self.args])["success"]:
            print(f"Kill Task: {self.args} success")
            return True
        else:
            print(f"Kill Task: {self.args} failed")
            return False
