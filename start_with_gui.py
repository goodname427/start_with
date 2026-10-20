"""StartWith 控制面板启动入口。"""
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _setup_logging() -> None:
    try:
        from common.paths import LOG_FILE, ensure_dirs

        ensure_dirs()
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
        )
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    silent = "--silent" in args or "--background" in args

    os.chdir(ROOT)
    _setup_logging()

    from gui.dpi import enable_dpi_awareness

    enable_dpi_awareness()

    import tkinter as tk
    from tkinter import messagebox

    from common.single_instance import acquire
    from gui.app import StartWithApp

    if not acquire():
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("StartWith", "StartWith 已经在运行了，请查看右下角的系统托盘图标。")
        root.destroy()
        return 0

    try:
        root = tk.Tk()
        StartWithApp(root, silent=silent)
        root.mainloop()
        return 0
    except Exception:
        logging.exception("启动失败")
        raise


if __name__ == "__main__":
    sys.exit(main())
