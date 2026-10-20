import ctypes
import os
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
            return subprocess.run(combined, capture_output=True, text=True, errors="replace")
        except Exception as e:
            print(f"Error when executing command [{combined}]: {e}")
            return subprocess.CompletedProcess(combined, CMD_RETURN_CODE_ERROR, "", str(e))

    @staticmethod
    def open(cmd: str, args: list = None) -> subprocess.Popen | None:
        combined = [
            cmd,
            *(args if args is not None else []),
        ]

        try:
            return subprocess.Popen(
                combined,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
            )
        except Exception as e:
            print(f"Error when opening command [{combined}]: {e}")
            return None

    @staticmethod
    def is_run_as_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    @staticmethod
    def require_admin():
        if CommandUtils.is_run_as_admin():
            print("Run as admin")
            return

        script = os.path.abspath(sys.argv[0]) if sys.argv else ""
        params = subprocess.list2cmdline([script, *sys.argv[1:]]) if script else ""
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            os.path.dirname(script) if script else None,
            1
        )
        sys.exit()
