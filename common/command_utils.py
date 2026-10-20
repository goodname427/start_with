import ctypes
import os
import subprocess
import sys

CMD_RETURN_CODE_SUCCESS = 0
CMD_RETURN_CODE_ERROR = -1
# GUI 以 pythonw 运行时没有控制台，子进程默认会弹出一个新控制台窗口；统一隐藏
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

class CommandUtils:
    has_run_as_admin = False

    @staticmethod
    def execute_command(cmd: str, args: list = None, encoding: str | None = None) -> subprocess.CompletedProcess:
        combined = [
            cmd,
            *(args if args is not None else []),
        ]

        try:
            return subprocess.run(
                combined,
                capture_output=True,
                text=True,
                errors="replace",
                encoding=encoding,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception as e:
            print(f"Error when executing command [{combined}]: {e}")
            return subprocess.CompletedProcess(combined, CMD_RETURN_CODE_ERROR, "", str(e))

    @staticmethod
    def open(cmd: str, args: list = None, encoding: str | None = None) -> subprocess.Popen | None:
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
                encoding=encoding,
                creationflags=CREATE_NO_WINDOW,
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
        workdir = os.path.dirname(script) if script else None

        # 提权时使用 pythonw，避免弹出一个空的 cmd/控制台窗口
        executable = sys.executable
        pythonw = os.path.join(os.path.dirname(executable), "pythonw.exe")
        if os.path.exists(pythonw):
            executable = pythonw

        shell32 = ctypes.windll.shell32
        shell32.ShellExecuteW.restype = ctypes.c_void_p
        result = shell32.ShellExecuteW(None, "runas", executable, params, workdir, 1)
        if not result or int(result) <= 32:
            print("需要管理员权限，但未获得授权，操作已取消。")
            sys.exit(1)
        sys.exit(0)
