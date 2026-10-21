"""应用绑定数据模型与匹配规则（data/bindings.json）。"""
import fnmatch
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
    # 仅文件夹绑定使用：忽略的 exe 通配符，例如 UnityCrashHandler*.exe
    ignore: list[str] = field(default_factory=list)

    def display_type(self) -> str:
        return TYPE_LABELS.get(self.type, self.type)

    def display_configs(self) -> str:
        if self.close_config:
            return f"{self.config} / 退出后 {self.close_config}"
        return self.config

    def display_target(self) -> str:
        if self.type == BINDING_TYPE_APP:
            name = os.path.basename(self.target.rstrip("\\/")) or self.target
            return f"{name}   ·   {self.target}"
        suffix = "   （含子文件夹）" if self.recursive else ""
        if self.ignore:
            suffix += f"   （忽略 {len(self.ignore)} 项）"
        return f"{self.target}{suffix}"


def new_binding(
    btype: str,
    target: str,
    config: str,
    recursive: bool = True,
    close_config: str = "",
    ignore: list[str] | None = None,
) -> AppBinding:
    return AppBinding(
        id=uuid.uuid4().hex,
        type=btype,
        target=target.strip(),
        config=config.strip(),
        close_config=close_config.strip(),
        recursive=recursive,
        ignore=list(ignore or []),
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
        raw_ignore = item.get("ignore")
        ignore: list[str] = []
        if isinstance(raw_ignore, list):
            ignore = [str(pattern).strip() for pattern in raw_ignore if str(pattern).strip()]
        elif isinstance(raw_ignore, str):
            ignore = [part.strip() for part in raw_ignore.replace(",", "\n").splitlines() if part.strip()]
        if btype not in TYPE_LABELS or not target or not config:
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
                ignore=ignore if btype == BINDING_TYPE_FOLDER else [],
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
                "ignore": b.ignore if b.type == BINDING_TYPE_FOLDER else [],
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


def _is_ignored(binding: AppBinding, process: ProcessInfo) -> bool:
    """文件夹绑定的忽略规则：支持 exe 名、相对路径和完整路径通配符。"""
    if not binding.ignore:
        return False

    name = (process.name or "").casefold()
    full_path = (process.path or "").replace("/", "\\").casefold()
    relative = ""
    if process.path:
        try:
            relative = os.path.relpath(process.path, binding.target).replace("/", "\\").casefold()
        except (OSError, ValueError):
            relative = ""

    for raw_pattern in binding.ignore:
        pattern = str(raw_pattern).strip().replace("/", "\\").casefold()
        if not pattern:
            continue
        if "\\" in pattern:
            if full_path and fnmatch.fnmatch(full_path, pattern):
                return True
            if relative and fnmatch.fnmatch(relative, pattern):
                return True
        elif name and fnmatch.fnmatch(name, pattern):
            return True
    return False


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
        matched = (
            exe_path.startswith(folder if folder.endswith(os.sep) else folder + os.sep)
            if binding.recursive
            else os.path.dirname(exe_path) == folder
        )
        if not matched:
            return False
        return not _is_ignored(binding, process)

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
