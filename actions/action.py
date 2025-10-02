import subprocess


class StartWithAction:
    def __init__(self, args, run_while_prev_action_success=False):
        self.args = args
        self.run_while_prev_action_success = run_while_prev_action_success

    def run(self)->bool:
        return True

    @staticmethod
    def _execute_cmd(cmd, args=""):
        combined_args = [
            cmd,
            args,
        ]

        try:
            result = subprocess.run(combined_args, check=True, capture_output=True, text=True)
            print(f"Command output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            print(f"Error executing command: {e}")
            print(f"Command output: {e.output}")
            return False

        return True