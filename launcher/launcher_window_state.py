# -*- coding: utf-8 -*-
"""
Module lưu và khôi phục kích thước, vị trí và trạng thái Maximized của cửa sổ chính
khi ẩn/mở lại từ System Tray hoặc tắt/mở lại ứng dụng.
"""

import base64
from PyQt6.QtCore import QByteArray, Qt

from launcher_storage import update_settings_fields

DEFAULT_WIN_SIZE = (840, 620)


def restore_window_state(win):
    """Khôi phục geometry và trạng thái phóng to đã lưu khi khởi tạo cửa sổ."""
    settings = win.data.get("settings", {}) if isinstance(getattr(win, "data", None), dict) else {}
    win._saved_geometry = None
    win._was_maximized = bool(settings.get("window_maximized", False))

    raw_geom = settings.get("window_geometry")
    restored = False
    if isinstance(raw_geom, str) and raw_geom.strip():
        try:
            geom_bytes = base64.b64decode(raw_geom.encode("ascii"))
            if geom_bytes:
                win._saved_geometry = geom_bytes
                restored = bool(win.restoreGeometry(QByteArray(geom_bytes)))
        except Exception:
            win._saved_geometry = None

    if not restored:
        win.resize(*DEFAULT_WIN_SIZE)


def capture_window_state(win, persist: bool = False):
    """Chụp lại geometry/trạng thái hiện tại (không ghi đè khi cửa sổ đang ẩn ở Tray)."""
    if not hasattr(win, "saveGeometry"):
        return
    if win.isVisible():
        win._was_maximized = bool(win.windowState() & Qt.WindowState.WindowMaximized)
        win._saved_geometry = bytes(win.saveGeometry())

    if persist and getattr(win, "_saved_geometry", None):
        geom_b64 = base64.b64encode(win._saved_geometry).decode("ascii")
        was_max = bool(getattr(win, "_was_maximized", False))
        if isinstance(getattr(win, "data", None), dict):
            settings = win.data.setdefault("settings", {})
            settings["window_geometry"] = geom_b64
            settings["window_maximized"] = was_max
        update_settings_fields({"window_geometry": geom_b64, "window_maximized": was_max})


def hide_window_to_tray(win):
    """Lưu trạng thái cửa sổ hiện tại trước khi ẩn vào System Tray."""
    capture_window_state(win, persist=True)
    win.hide()


def restore_window_from_tray(win):
    """Hiển thị lại cửa sổ từ System Tray mà không làm mất kích thước hoặc trạng thái Maximized."""
    is_hidden = not win.isVisible()
    saved_geom = getattr(win, "_saved_geometry", None)
    if is_hidden:
        was_max = bool(getattr(win, "_was_maximized", False))
        if saved_geom:
            win.restoreGeometry(QByteArray(saved_geom))
    else:
        was_max = bool(win.windowState() & Qt.WindowState.WindowMaximized)

    win._was_maximized = was_max
    if was_max:
        win.setWindowState(
            (win.windowState() & ~Qt.WindowState.WindowMinimized)
            | Qt.WindowState.WindowMaximized
            | Qt.WindowState.WindowActive
        )
        win.showMaximized()
    else:
        win.setWindowState(
            (win.windowState() & ~Qt.WindowState.WindowMinimized)
            | Qt.WindowState.WindowActive
        )
        win.show()

    win.raise_()
    win.activateWindow()
    handle = win.windowHandle()
    if handle and hasattr(handle, "requestActivate"):
        handle.requestActivate()
