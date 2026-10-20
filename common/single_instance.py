"""单实例保护：避免同时运行多个面板/监听器。"""
import ctypes
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183
_handle = None


def acquire(name: str = "StartWithGUI_single_instance") -> bool:
    """获取命名互斥体。返回 False 表示已有实例在运行。"""
    global _handle
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    handle = kernel32.CreateMutexW(None, False, f"Local\\{name}")
    if not handle:
        return True
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _handle = handle
    return True
