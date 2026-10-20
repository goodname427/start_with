"""应用绑定数据模型与匹配规则（data/bindings.json）。"""
import json
import os
import threading
import uuid
from dataclasses import dataclass
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
    enabled: bool = True
    recursive: bool = True

    def display_type(self) -> str:
        return TYPE_LABELS.get(self.type, self.type)

    def display_target(self) -> str:
        if self.type == BINDING_TYPE_APP:
            name = os.path.basename(self.target.rstrip("\\/")) or self.target
            return f"{name}   ·   {self.target}"
        suffix = "   （含子文件夹）" if self.recursive else ""
        return f"{self.target}{suffix}"


def new_binding(btype: str, target: str, config: str, recursive: bool = True) -> AppBinding:
    return AppBinding(id=uuid.uuid4().hex, type=btype, target=target.strip(), config=config.strip(), recursive=recursive)


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
        if btype not in TYPE_LABELS or not target or not config:
            continue
        bindings.append(
            AppBinding(
                id=str(item.get("id") or uuid.uuid4().hex),
                type=btype,
                target=target,
                config=config,
                enabled=bool(item.get("enabled", True)),
                recursive=bool(item.get("recursive", True)),
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
                "enabled": b.enabled,
                "recursive": b.recursive,
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


def find_matching_binding(bindings: list[AppBinding], process: ProcessInfo) -> AppBinding | None:
    matched = [b for b in bindings if binding_matches(b, process)]
    if not matched:
        return None
    # 单应用优先，其次匹配路径最长的文件夹（更精确）
    matched.sort(key=lambda b: (0 if b.type == BINDING_TYPE_APP else 1, -len(b.target)))
    return matched[0]


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
