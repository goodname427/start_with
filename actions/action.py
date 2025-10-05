import subprocess
from typing import List


class StartWithAction:
    def __init__(self, args, run_while_prev_action_success=False):
        self.args = args
        self.run_while_prev_action_success = run_while_prev_action_success

    def run(self)->bool:
        return True

    def run_as_admin(self)->bool:
        return False

    def _check_args_is_type(self, expected_type):
        if type(self.args) != expected_type:
            print(f"Error: args is not {expected_type}")
            return False

        return True
