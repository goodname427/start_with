"""加速器动作的运行日志，GUI 会在应用完成后读取展示。"""
from datetime import datetime

from common.paths import ACC_LOG_FILE, ensure_dirs


def reset(header: str) -> None:
    try:
        ensure_dirs()
        ACC_LOG_FILE.write_text(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {header}\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def append(message: str) -> None:
    try:
        with open(ACC_LOG_FILE, "a", encoding="utf-8") as file:
            file.write(f"[{datetime.now():%H:%M:%S}] {message}\n")
    except OSError:
        pass
