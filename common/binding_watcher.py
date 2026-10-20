"""后台进程监听：检测到新进程启动时匹配绑定规则。"""
import logging
import threading
import time

from common.binding_store import AppBinding, find_matching_binding
from common.process_monitor import ProcessInfo, list_processes

logger = logging.getLogger(__name__)


class BindingWatcher(threading.Thread):
    def __init__(self, on_process_started, interval: float = 2.0, recent_window: float = 10.0):
        super().__init__(name="binding-watcher", daemon=True)
        self._on_process_started = on_process_started
        self._interval = max(0.5, float(interval))
        self._recent_window = recent_window
        self._bindings: list[AppBinding] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._recent: dict[str, float] = {}
        self._known_pids: set[int] = set()

    def update_bindings(self, bindings: list[AppBinding]) -> None:
        with self._lock:
            self._bindings = list(bindings)

    def set_interval(self, seconds: float) -> None:
        with self._lock:
            self._interval = max(0.5, float(seconds))

    def stop(self) -> None:
        self._stop_event.set()

    def _get_interval(self) -> float:
        with self._lock:
            return self._interval

    def run(self) -> None:
        try:
            self._known_pids = {p.pid for p in list_processes()}
        except Exception:
            logger.exception("初始化进程基线失败")
            self._known_pids = set()

        while not self._stop_event.is_set():
            if self._stop_event.wait(self._get_interval()):
                break
            try:
                self._scan()
            except Exception:
                logger.exception("扫描进程失败")
        logger.info("进程监听已停止")

    def _scan(self) -> None:
        processes = list_processes()
        with self._lock:
            bindings = list(self._bindings)

        current_pids = {p.pid for p in processes}
        new_processes = [p for p in processes if p.pid not in self._known_pids]
        self._known_pids = current_pids

        if not bindings or not new_processes:
            return

        now = time.monotonic()
        self._recent = {k: t for k, t in self._recent.items() if now - t <= self._recent_window}

        for process in new_processes:
            if not process.name:
                continue
            binding = find_matching_binding(bindings, process)
            if binding is None:
                continue

            # 同一条绑定的多个子进程在短时间内只触发一次，避免重复应用配置
            key = binding.id
            if key in self._recent:
                continue
            self._recent[key] = now

            try:
                self._on_process_started(binding, process)
            except Exception:
                logger.exception("处理进程启动事件失败")
