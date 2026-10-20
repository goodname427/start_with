"""等待指定进程出现，例如等待加速器完全启动。"""
import os
import time
from typing import override

from actions.action import StartWithAction
from common.process_monitor import list_processes

DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_TIMEOUT_SECONDS = 600.0
POLL_INTERVAL_SECONDS = 0.5


def parse_args(raw) -> tuple[str, float]:
    """支持「进程名」或「进程名|超时秒数」两种写法。"""
    text = str(raw).strip()
    timeout = DEFAULT_TIMEOUT_SECONDS
    if "|" in text:
        text, _, timeout_text = text.partition("|")
        text = text.strip()
        try:
            timeout = float(timeout_text.strip())
        except ValueError:
            return text, -1.0
        timeout = max(1.0, min(timeout, MAX_TIMEOUT_SECONDS))
    return text, timeout


class WaitProcessAction(StartWithAction):
    label = "等待进程启动"
    args_label = "进程名（可加 |超时秒数）"
    args_kind = "process"
    description = "等待指定进程出现后再继续（默认最多 120 秒），可用于等待加速器启动。"
    order = 21

    @override
    def run(self) -> bool:
        name, timeout = parse_args(self.args)
        if not name:
            print("进程名不能为空")
            return False
        if timeout < 0:
            print(f"超时时间无效: {self.args}")
            return False

        target = os.path.basename(name).lower()
        deadline = time.monotonic() + timeout
        print(f"等待进程 [{target}] 启动（最多 {timeout:g} 秒）…")
        while True:
            try:
                processes = list_processes()
            except Exception as exc:
                print(f"读取进程列表失败: {exc}")
                return False

            if any(p.name and p.name.lower() == target for p in processes):
                print(f"进程 [{target}] 已启动")
                return True

            if time.monotonic() >= deadline:
                print(f"等待进程 [{target}] 超时（{timeout:g} 秒）")
                return False
            time.sleep(POLL_INTERVAL_SECONDS)
