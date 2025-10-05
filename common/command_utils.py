import ctypes
import subprocess
import sys

CMD_RETURN_CODE_SUCCESS = 0
CMD_RETURN_CODE_ERROR = -1

class CommandUtils:
    has_run_as_admin = False

    @staticmethod
    def execute_command(cmd: str, args: list = None) -> subprocess.CompletedProcess:
        combined = [
            cmd,
            *(args if args is not None else []),
        ]

        try:
            return subprocess.run(combined, check=True, capture_output=True, text=True)
        except Exception as e:
            print(f"Error when executing command [{combined}]: {e}")
            return subprocess.CompletedProcess(combined, CMD_RETURN_CODE_ERROR, "", str(e))

    @staticmethod
    def is_run_as_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    @staticmethod
    def require_admin():
        if CommandUtils.is_run_as_admin():
            return

        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            " ".join(sys.argv),
            None,
            1
        )
        sys.exit()
