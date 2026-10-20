"""应用绑定数据模型与匹配规则（data/bindings.json）。"""
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from common.paths import BINDINGS_FILE, ensure_dirs
from common.process_monitor import ProcessInfo

BINDING_TYPE_APP = "app"
BINDING_TYPE_FOLDER = "folder"
TYPE_LABELS = {BINDING_TYPE_APP: "单个应用", BINDING_TYPE_FOLDER: "文件夹"}

_lock = threading.Lock()


@dataclass
class AppBinding:
    id: str
    type: str
    target: str
    config: str
    close_config: str = ""
    enabled: bool = True
    recursive: bool = True
    # 手动启动时应用的配置；配置内的动作参数可以用 {key} 由 params 填充
    launch_config: str = ""
    params: dict[str, str] = field(default_factory=dict)

    def display_type(self) -> str:
        return TYPE_LABELS.get(self.type, self.type)

    def display_configs(self) -> str:
        parts: list[str] = []
        if self.launch_config:
            parts.append(f"启动 {self.launch_config}")
        if self.config:
            parts.append(self.config)
        if self.close_config:
            parts.append(f"退出后 {self.close_config}")
        return " / ".join(parts) or "—"

    def display_launch(self) -> str:
        if not self.launch_config:
            return "—"
        if not self.params:
            return self.launch_config
        return f"{self.launch_config}（{len(self.params)} 个参数）"

    def display_params(self) -> str:
        if not self.params:
            return "—"
        return "，".join(f"{key}={value}" for key, value in self.params.items())

    def display_target(self) -> str:
        if self.type == BINDING_TYPE_APP:
            name = os.path.basename(self.target.rstrip("\\/")) or self.target
            return f"{name}   ·   {self.target}"
        suffix = "   （含子文件夹）" if self.recursive else ""
        return f"{self.target}{suffix}"


def new_binding(
    btype: str,
    target: str,
    config: str,
    recursive: bool = True,
    close_config: str = "",
    launch_config: str = "",
    params: dict[str, str] | None = None,
) -> AppBinding:
    return AppBinding(
        id=uuid.uuid4().hex,
        type=btype,
        target=target.strip(),
        config=config.strip(),
        close_config=close_config.strip(),
        recursive=recursive,
        launch_config=launch_config.strip(),
        params=dict(params or {}),
    )


def load_bindings() -> list[AppBinding]:
    try:
        raw = json.loads(BINDINGS_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []

    items = raw.get("bindings") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []

    bindings: list[AppBinding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        btype = str(item.get("type", "")).strip()
        target = str(item.get("target", "")).strip()
        config = str(item.get("config", "")).strip()
        close_config = str(item.get("close_config", "")).strip()
        launch_config = str(item.get("launch_config", "")).strip()
        params: dict[str, str] = {}
        raw_params = item.get("params")
        if isinstance(raw_params, dict):
            for key, value in raw_params.items():
                key_text = str(key).strip()
                if key_text:
                    params[key_text] = str(value)
        if btype not in TYPE_LABELS or not target:
            continue
        if not (config or close_config or launch_config):
            continue
        bindings.append(
            AppBinding(
                id=str(item.get("id") or uuid.uuid4().hex),
                type=btype,
                target=target,
                config=config,
                close_config=close_config,
                enabled=bool(item.get("enabled", True)),
                recursive=bool(item.get("recursive", True)),
                launch_config=launch_config,
                params=params,
            )
        )
    return bindings


def save_bindings(bindings: list[AppBinding]) -> None:
    payload = {
        "version": 1,
        "bindings": [
            {
                "id": b.id,
                "type": b.type,
                "target": b.target,
                "config": b.config,
                "close_config": b.close_config,
                "enabled": b.enabled,
                "recursive": b.recursive,
                "launch_config": b.launch_config,
                "params": b.params,
            }
            for b in bindings
        ],
    }
    with _lock:
        ensure_dirs()
        tmp = BINDINGS_FILE.with_name(BINDINGS_FILE.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        os.replace(tmp, BINDINGS_FILE)


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def binding_matches(binding: AppBinding, process: ProcessInfo) -> bool:
    if not binding.enabled or not binding.target:
        return False

    if binding.type == BINDING_TYPE_APP:
        target_name = os.path.basename(binding.target.strip())
        return bool(target_name and process.name and target_name.lower() == process.name.lower())

    if binding.type == BINDING_TYPE_FOLDER:
        if not process.path:
            return False
        try:
            folder = _norm(binding.target)
            exe_path = _norm(process.path)
        except (OSError, ValueError):
            return False
        if binding.recursive:
            prefix = folder if folder.endswith(os.sep) else folder + os.sep
            return exe_path.startswith(prefix)
        return os.path.dirname(exe_path) == folder

    return False


def _binding_specificity(binding: AppBinding) -> tuple[int, int, int]:
    """越具体的规则优先级越高：单个应用 > 子文件夹 > 上级文件夹。"""
    if binding.type == BINDING_TYPE_APP:
        target = binding.target.strip()
        # 带完整路径的应用规则比只写进程名更具体
        return 2, 1 if os.path.dirname(target) else 0, len(target)
    if binding.type == BINDING_TYPE_FOLDER:
        return 1, len(_norm(binding.target)), 0
    return 0, 0, 0


def find_matching_binding(bindings: list[AppBinding], process: ProcessInfo) -> AppBinding | None:
    """按类似 .gitignore 的覆盖规则选择规则：子级覆盖父级，同级时后添加的生效。"""
    best: AppBinding | None = None
    best_key: tuple[int, int, int, int] | None = None

    for index, binding in enumerate(bindings):
        if not binding_matches(binding, process):
            continue
        key = (*_binding_specificity(binding), index)
        if best_key is None or key >= best_key:
            best = binding
            best_key = key

    return best


def count_folder_executables(folder: str, recursive: bool = True, limit: int = 20000) -> int:
    """统计文件夹下的 exe 数量，用于绑定时的批量提示。"""
    count = 0
    try:
        stack = [Path(folder)]
        visited = 0
        while stack and visited < limit:
            current = stack.pop()
            try:
                entries = list(os.scandir(current))
            except OSError:
                continue
            for entry in entries:
                visited += 1
                if visited >= limit:
                    break
                try:
                    if entry.is_file(follow_symlinks=False):
                        if entry.name.lower().endswith(".exe"):
                            count += 1
                    elif recursive and entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                except OSError:
                    continue
    except OSError:
        pass
    return count
