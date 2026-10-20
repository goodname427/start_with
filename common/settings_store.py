"""GUI 设置持久化（data/settings.json）。"""
import json
import os
import threading

from common.paths import SETTINGS_FILE, ensure_dirs

DEFAULT_SETTINGS = {
    "monitor_enabled": True,
    "poll_interval": 2.0,
    "minimize_to_tray": True,
    "notify_on_trigger": True,
}

_lock = threading.Lock()


def _read_raw() -> dict:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    raw = _read_raw()
    for key in DEFAULT_SETTINGS:
        if key in raw:
            settings[key] = raw[key]

    settings["monitor_enabled"] = bool(settings["monitor_enabled"])
    settings["minimize_to_tray"] = bool(settings["minimize_to_tray"])
    settings["notify_on_trigger"] = bool(settings["notify_on_trigger"])
    try:
        settings["poll_interval"] = max(0.5, float(settings["poll_interval"]))
    except (TypeError, ValueError):
        settings["poll_interval"] = DEFAULT_SETTINGS["poll_interval"]
    return settings


def save_settings(settings: dict) -> dict:
    data = dict(DEFAULT_SETTINGS)
    data.update({k: v for k, v in settings.items() if k in DEFAULT_SETTINGS})
    with _lock:
        ensure_dirs()
        tmp = SETTINGS_FILE.with_name(SETTINGS_FILE.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        os.replace(tmp, SETTINGS_FILE)
    return load_settings()
