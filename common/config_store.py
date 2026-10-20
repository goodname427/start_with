"""配置文件的读取、保存与删除。配置位于 config/<name>.json。"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from common.paths import CONFIG_DIR, ensure_dirs

CONFIG_SUFFIX = ".json"
# action_list.json 是操作说明示例，不参与配置列表
EXCLUDED_FILES = {"action_list.json"}
INVALID_NAME_CHARS = '\\/:*?"<>|'


@dataclass
class ConfigInfo:
    name: str
    path: Path
    action_count: int = 0
    actions: list[dict] = field(default_factory=list)
    error: str | None = None


def is_valid_name(name: str) -> bool:
    name = name.strip()
    if not name or name.startswith("."):
        return False
    if any(ch in INVALID_NAME_CHARS for ch in name):
        return False
    return True


def config_path(name: str) -> Path:
    return CONFIG_DIR / f"{name}{CONFIG_SUFFIX}"


def list_configs() -> list[ConfigInfo]:
    ensure_dirs()
    result: list[ConfigInfo] = []
    for path in CONFIG_DIR.glob(f"*{CONFIG_SUFFIX}"):
        if path.name in EXCLUDED_FILES or path.name.startswith("."):
            continue

        info = ConfigInfo(name=path.stem, path=path)
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            info.error = f"JSON 解析失败：{exc}"
        else:
            actions = data.get("actions") if isinstance(data, dict) else None
            if not isinstance(actions, list):
                info.error = "配置缺少 actions 列表"
            else:
                info.actions = [a for a in actions if isinstance(a, dict)]
                info.action_count = len(info.actions)
        result.append(info)

    result.sort(key=lambda c: c.name.lower())
    return result


def read_actions(name: str) -> tuple[list[dict] | None, str | None]:
    path = config_path(name)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return None, str(exc)
    actions = data.get("actions") if isinstance(data, dict) else None
    if not isinstance(actions, list):
        return None, "配置缺少 actions 列表"
    return [a for a in actions if isinstance(a, dict)], None


def save_config(name: str, actions: list[dict]) -> Path:
    name = name.strip()
    if not is_valid_name(name):
        raise ValueError("配置名称不合法")
    if name.lower() == "action_list":
        raise ValueError("action_list 为保留名称")

    ensure_dirs()
    path = config_path(name)
    payload = {"actions": list(actions)}
    tmp = CONFIG_DIR / f"{name}{CONFIG_SUFFIX}.tmp"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def delete_config(name: str) -> None:
    path = config_path(name)
    if path.exists():
        path.unlink()
