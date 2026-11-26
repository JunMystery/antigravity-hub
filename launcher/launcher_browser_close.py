# -*- coding: utf-8 -*-
"""
Hỗ trợ tự động đóng tab trình duyệt sau khi OAuth thành công (Windows).
Các trình duyệt hiện đại chặn JS window.close() với tab mở từ bên ngoài, nên Launcher
chỉ gửi Ctrl+W khi cửa sổ đang active thực sự mang tiêu đề OAuth thành công của Antigravity Hub.
"""

import ctypes
import ctypes.wintypes
import sys

OAUTH_SUCCESS_TITLE_MARKERS = (
    "Antigravity Hub - Đăng nhập thành công!",
    "Antigravity Hub - Login Successful!",
)

_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_VK_CONTROL = 0x11
_VK_W = 0x57
_BLOCKING_MODIFIERS = (0x10, 0x12, 0x5B, 0x5C)  # Shift, Alt, LWin, RWin
_ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.wintypes.LONG),
        ("dy", ctypes.wintypes.LONG),
        ("mouseData", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.wintypes.DWORD),
        ("wParamL", ctypes.wintypes.WORD),
        ("wParamH", ctypes.wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.wintypes.DWORD), ("union", _INPUT_UNION)]


def is_oauth_success_window_title(title: str) -> bool:
    """Kiểm tra tiêu đề cửa sổ foreground có khớp trang báo OAuth thành công không."""
    if not isinstance(title, str) or not title:
        return False
    return any(marker in title for marker in OAUTH_SUCCESS_TITLE_MARKERS)


def get_foreground_window_title() -> str:
    """Lấy tiêu đề cửa sổ đang focus trên Windows."""
    if sys.platform != "win32":
        return ""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


def has_blocking_modifiers() -> bool:
    """Tránh gửi Ctrl+W nếu người dùng đang giữ Shift/Alt/Win (tránh Ctrl+Shift+W)."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        return any(bool(user32.GetAsyncKeyState(vk) & 0x8000) for vk in _BLOCKING_MODIFIERS)
    except Exception:
        return True


def _key_event(vk: int, flags: int = 0) -> INPUT:
    return INPUT(
        type=_INPUT_KEYBOARD,
        union=_INPUT_UNION(ki=_KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)),
    )


def send_ctrl_w() -> bool:
    """Gửi tổ hợp phím Ctrl+W qua Win32 SendInput."""
    if sys.platform != "win32":
        return False
    try:
        events = (INPUT * 4)(
            _key_event(_VK_CONTROL, 0),
            _key_event(_VK_W, 0),
            _key_event(_VK_W, _KEYEVENTF_KEYUP),
            _key_event(_VK_CONTROL, _KEYEVENTF_KEYUP),
        )
        sent = ctypes.windll.user32.SendInput(4, events, ctypes.sizeof(INPUT))
        return sent == 4
    except Exception:
        return False


def try_close_oauth_browser_tab() -> bool:
    """Chỉ đóng tab khi cửa sổ foreground là tab trình duyệt báo OAuth thành công."""
    if sys.platform != "win32":
        return False
    if not is_oauth_success_window_title(get_foreground_window_title()):
        return False
    if has_blocking_modifiers():
        return False
    return send_ctrl_w()
