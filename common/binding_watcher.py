"""后台进程监听：检测绑定应用的启动与退出，触发对应配置。"""
import logging
import threading
import time

from common.binding_store import AppBinding, find_matching_binding
from common.process_monitor import ProcessInfo, list_processes

logger = logging.getLogger(__name__)


class BindingWatcher(threading.Thread):
    def __init__(
        self,
        on_process_started,
        on_process_stopped=None,
        interval: float = 2.0,
        recent_window: float = 10.0,
        close_grace: float = 3.0,
    ):
        super().__init__(name="binding-watcher", daemon=True)
        self._on_process_started = on_process_started
        self._on_process_stopped = on_process_stopped
        self._interval = max(0.5, float(interval))
        self._recent_window = recent_window
        self._close_grace = max(0.0, float(close_grace))

        self._bindings: list[AppBinding] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        self._recent: dict[str, float] = {}
        self._known_pids: set[int] = set()

        # 已匹配并需要跟踪退出的进程：pid -> (绑定 ID, 进程信息)
        self._tracked: dict[int, tuple[str, ProcessInfo]] = {}
        self._binding_counts: dict[str, int] = {}
        # 绑定 ID -> 关闭配置的触发时间 / 最后退出的进程
        self._pending_close: dict[str, float] = {}
        self._pending_process: dict[str, ProcessInfo] = {}

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
        current_pids = {p.pid for p in processes}
        exited_pids = [pid for pid in self._known_pids if pid not in current_pids]
        new_processes = [p for p in processes if p.pid not in self._known_pids]
        self._known_pids = current_pids

        with self._lock:
            bindings = list(self._bindings)

        now = time.monotonic()
        self._recent = {k: t for k, t in self._recent.items() if now - t <= self._recent_window}

        for pid in exited_pids:
            self._release_process(pid, bindings, now)

        for process in new_processes:
            if not process.name:
                continue
            binding = find_matching_binding(bindings, process)
            if binding is None:
                continue
            self._handle_started(binding, process, now)

        self._flush_pending_closes(bindings, now)

    def _handle_started(self, binding: AppBinding, process: ProcessInfo, now: float) -> None:
        # 有新进程启动时，取消该绑定正在等待的“退出”动作（例如游戏重启）
        self._pending_close.pop(binding.id, None)
        self._pending_process.pop(binding.id, None)

        if binding.config:
            if binding.id not in self._recent:
                self._recent[binding.id] = now
                try:
                    self._on_process_started(binding, process)
                except Exception:
                    logger.exception("处理进程启动事件失败")

        if binding.close_config:
            self._tracked[process.pid] = (binding.id, process)
            self._binding_counts[binding.id] = self._binding_counts.get(binding.id, 0) + 1

    def _release_process(self, pid: int, bindings: list[AppBinding], now: float) -> None:
        entry = self._tracked.pop(pid, None)
        if entry is None:
            return

        binding_id, process = entry
        count = self._binding_counts.get(binding_id, 1) - 1
        if count > 0:
            self._binding_counts[binding_id] = count
            return
        self._binding_counts.pop(binding_id, None)

        current = next((b for b in bindings if b.id == binding_id), None)
        if current is None or not current.enabled or not current.close_config:
            return

        # 稍等几秒再应用退出配置，避免启动器退出而主程序仍在启动时误切配置
        self._pending_close[binding_id] = now + self._close_grace
        self._pending_process[binding_id] = process

    def _flush_pending_closes(self, bindings: list[AppBinding], now: float) -> None:
        for binding_id, deadline in list(self._pending_close.items()):
            if now < deadline:
                continue
            if self._binding_counts.get(binding_id, 0) > 0:
                self._pending_close.pop(binding_id, None)
                self._pending_process.pop(binding_id, None)
                continue

            self._pending_close.pop(binding_id, None)
            process = self._pending_process.pop(binding_id, None)
            if process is None:
                continue

            current = next((b for b in bindings if b.id == binding_id), None)
            if current is None or not current.enabled or not current.close_config:
                continue
            if self._on_process_stopped is None:
                continue

            # 允许下一次启动重新触发打开配置
            self._recent.pop(binding_id, None)
            try:
                self._on_process_stopped(current, process)
            except Exception:
                logger.exception("处理进程退出事件失败")
