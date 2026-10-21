"""游戏启动项（先应用配置，再启动游戏）的数据模型。"""
import json
import os
import threading
import uuid
from dataclasses import dataclass

from common.paths import DATA_DIR, ensure_dirs

LAUNCHES_FILE = DATA_DIR / "launches.json"
_lock = threading.Lock()


@dataclass
class LaunchItem:
    id: str
    name: str
    target: str
    config: str
    close_config: str = ""
    enabled: bool = True

    def display_name(self) -> str:
        return self.name or os.path.basename(self.target.rstrip("\\/")) or self.target

    def display_target(self) -> str:
        return self.target

    def display_configs(self) -> str:
        if self.close_config:
            return f"{self.config} / 退出后 {self.close_config}"
        return self.config


def new_launch(
    name: str,
    target: str,
    config: str,
    close_config: str = "",
    enabled: bool = True,
) -> LaunchItem:
    target = target.strip()
    return LaunchItem(
        id=uuid.uuid4().hex,
        name=name.strip() or os.path.basename(target.rstrip("\\/")),
        target=target,
        config=config.strip(),
        close_config=close_config.strip(),
        enabled=enabled,
    )


def load_launches() -> list[LaunchItem]:
    try:
        raw = json.loads(LAUNCHES_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []

    items = raw.get("launches") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []

    launches: list[LaunchItem] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        target = str(item.get("target", "")).strip()
        config = str(item.get("config", "")).strip()
        if not target or not config:
            continue
        launches.append(
            LaunchItem(
                id=str(item.get("id") or uuid.uuid4().hex),
                name=str(item.get("name", "")).strip(),
                target=target,
                config=config,
                close_config=str(item.get("close_config", "")).strip(),
                enabled=bool(item.get("enabled", True)),
            )
        )
    return launches


def save_launches(launches: list[LaunchItem]) -> None:
    payload = {
        "version": 1,
        "launches": [
            {
                "id": item.id,
                "name": item.name,
                "target": item.target,
                "config": item.config,
                "close_config": item.close_config,
                "enabled": item.enabled,
            }
            for item in launches
        ],
    }
    with _lock:
        ensure_dirs()
        tmp = LAUNCHES_FILE.with_name(LAUNCHES_FILE.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        os.replace(tmp, LAUNCHES_FILE)
