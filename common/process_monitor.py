"""进程枚举（ctypes 实现，无需额外依赖）。"""
import ctypes
import os
from ctypes import wintypes as wt
from dataclasses import dataclass

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_psapi = ctypes.WinDLL("psapi", use_last_error=True)

_psapi.EnumProcesses.argtypes = [ctypes.POINTER(wt.DWORD), wt.DWORD, ctypes.POINTER(wt.DWORD)]
_psapi.EnumProcesses.restype = wt.BOOL

_kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_kernel32.OpenProcess.restype = wt.HANDLE

_kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
_kernel32.QueryFullProcessImageNameW.restype = wt.BOOL

_kernel32.CloseHandle.argtypes = [wt.HANDLE]


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str
    path: str | None


def _enum_pids() -> list[int]:
    count = 1024
    while count <= 65536:
        array = (wt.DWORD * count)()
        needed = wt.DWORD()
        if not _psapi.EnumProcesses(array, ctypes.sizeof(array), ctypes.byref(needed)):
            return []
        used = needed.value // ctypes.sizeof(wt.DWORD)
        if used < count:
            return [pid for pid in array[:used] if pid]
        count *= 2
    return []


def _query_image_path(pid: int) -> str | None:
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = wt.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if _kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value or None
        return None
    finally:
        _kernel32.CloseHandle(handle)


def list_processes() -> list[ProcessInfo]:
    processes: list[ProcessInfo] = []
    for pid in _enum_pids():
        path = _query_image_path(pid)
        name = os.path.basename(path) if path else ""
        processes.append(ProcessInfo(pid=pid, name=name, path=path))
    return processes


def list_process_names() -> list[str]:
    """当前运行进程名（用于编辑器下拉提示）。"""
    try:
        names = {p.name for p in list_processes() if p.name}
    except Exception:
        return []
    return sorted(names, key=str.lower)
