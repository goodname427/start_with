"""等待固定时长，用于给加速器留出完成加速的时间。"""
import time
from typing import override

from actions.action import StartWithAction

MAX_WAIT_SECONDS = 600.0


def parse_seconds(value) -> float | None:
    try:
        seconds = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if seconds < 0 or seconds != seconds:
        return None
    return seconds


class WaitAction(StartWithAction):
    label = "等待"
    args_label = "等待秒数（支持小数）"
    args_kind = "duration"
    description = "暂停指定秒数，例如等加速器完成加速后再启动游戏。"
    order = 20

    @override
    def run(self) -> bool:
        seconds = parse_seconds(self.args)
        if seconds is None:
            print(f"等待时长无效: {self.args}")
            return False

        seconds = min(seconds, MAX_WAIT_SECONDS)
        print(f"等待 {seconds:g} 秒…")
        time.sleep(seconds)
        print(f"等待结束（{seconds:g} 秒）")
        return True
