import subprocess
from typing import List


class StartWithAction:
    def __init__(self, args, run_while_prev_action_success=False):
        self.args = args
        self.run_while_prev_action_success = run_while_prev_action_success

    def run(self)->bool:
        return True

    def _check_args_is_type(self, expected_type):
        if type(self.args) != expected_type:
            print(f"Error: args is not {expected_type}")
            return False

        return True

    @staticmethod
    def _execute_cmd(cmd, args:List[str]=None) -> {bool, str}:
        combined_args = [
            cmd,
            *(args if args is not None else []),
        ]

        try:
            result = subprocess.run(combined_args, check=True, capture_output=True, text=True)
            return {"success": True, "output": result.stdout}
        except Exception as e:
            print(f"Error when executing command {combined_args}: {e}")
            return { "success": False, "output": str(e) }
