"""从触发的进程和绑定推导配置参数（供 {key} 占位符自动填充）。"""
import os
from pathlib import Path


def _version_string(path: str, key: str) -> str:
    try:
        import win32api

        translations = win32api.GetFileVersionInfo(path, r"\VarFileInfo\Translation") or []
        for language, codepage in translations[:3]:
            try:
                value = win32api.GetFileVersionInfo(
                    path,
                    f"\\StringFileInfo\\{language:04x}{codepage:04x}\\{key}",
                )
            except Exception:
                continue
            if value:
                return str(value).strip()
    except Exception:
        return ""
    return ""


def describe_executable(path: str) -> dict[str, str]:
    if not path or not os.path.isfile(path):
        return {}
    return {
        "title": _version_string(path, "FileDescription"),
        "product": _version_string(path, "ProductName"),
        "internal": _version_string(path, "InternalName"),
    }


def build_context(binding, process) -> dict[str, str]:
    """生成配置动作可用的自动参数。"""
    path = process.path or ""
    stem = os.path.splitext(process.name)[0] if process.name else ""
    meta = describe_executable(path)
    folder = Path(path).parent.name if path else ""
    return {
        "app_name": process.name or "",
        "app_path": path,
        "app_stem": stem,
        "app_folder": folder,
        "app_title": meta.get("title") or "",
        "app_product": meta.get("product") or "",
        "app_internal": meta.get("internal") or "",
        "binding_target": binding.target,
        "binding_config": binding.config,
        "binding_close_config": binding.close_config,
        "process_id": str(process.pid),
    }
