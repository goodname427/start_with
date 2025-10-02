from typing import override
from actions.action import StartWithAction


class RunAppAction(StartWithAction):
    @override
    def run(self)->bool:
        if not self.args:
            return False

        print(f"Running app: {self.args}")
        StartWithAction._execute_cmd(self.args)

        return True