# -*- coding: utf-8 -*-
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import Qt

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER_DIR = os.path.join(ROOT_DIR, "launcher")
if LAUNCHER_DIR not in sys.path:
    sys.path.insert(0, LAUNCHER_DIR)

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

import launcher_window_state
from launcher_tray import TrayManager
from launcher_window_state import (
    restore_window_state, capture_window_state, hide_window_to_tray, restore_window_from_tray
)


class TestTrayManager(unittest.TestCase):
    def setUp(self):
        self.mock_win = MagicMock()
        self.mock_win.data = {"settings": {}}

    def test_notify_minimized_only_once(self):
        tray = TrayManager(self.mock_win)
        tray.tray_icon.showMessage = MagicMock()

        with patch("PyQt6.QtWidgets.QSystemTrayIcon.supportsMessages", return_value=True):
            with patch.object(tray.tray_icon, "isVisible", return_value=True):
                # Lần gọi thứ nhất: hiển thị thông báo
                tray.notify_minimized()
                self.assertEqual(tray.tray_icon.showMessage.call_count, 1)

                # Các lần gọi tiếp theo: bị chặn để chống spam
                tray.notify_minimized()
                tray.notify_minimized()
                self.assertEqual(tray.tray_icon.showMessage.call_count, 1)

    def test_notify_minimized_suppressed_when_fully_configured(self):
        self.mock_win.data = {
            "settings": {
                "hide_on_launch": "always",
                "close_action": "hide"
            }
        }
        tray = TrayManager(self.mock_win)
        tray.tray_icon.showMessage = MagicMock()

        with patch("PyQt6.QtWidgets.QSystemTrayIcon.supportsMessages", return_value=True):
            with patch.object(tray.tray_icon, "isVisible", return_value=True):
                # Người dùng đã chọn luôn ẩn cả 2 mục thì hoàn toàn không thông báo
                tray.notify_minimized()
                self.assertEqual(tray.tray_icon.showMessage.call_count, 0)

    def test_tray_hide_restore_and_restart_preserve_size_and_maximized(self):
        with patch.object(launcher_window_state, "update_settings_fields") as mock_upd:
            win = QMainWindow()
            win.data = {"settings": {}}
            restore_window_state(win)
            win.resize(780, 720)
            win.show()
            app.processEvents()

            hide_window_to_tray(win)
            self.assertFalse(win.isVisible())
            self.assertIn("window_geometry", win.data["settings"])

            restore_window_from_tray(win)
            app.processEvents()
            self.assertEqual((win.width(), win.height()), (780, 720))

            # Thoát lúc đang ẩn trong Tray không được ghi đè mất geometry đã lưu
            hide_window_to_tray(win)
            saved_geom = win.data["settings"]["window_geometry"]
            capture_window_state(win, persist=True)
            self.assertEqual(win.data["settings"]["window_geometry"], saved_geom)

            # Khởi động lại cửa sổ mới khôi phục kích thước cũ
            win2 = QMainWindow()
            win2.data = {"settings": dict(win.data["settings"])}
            restore_window_state(win2)
            self.assertEqual((win2.width(), win2.height()), (780, 720))
            self.assertGreaterEqual(mock_upd.call_count, 2)
            win.close()
            win2.close()

    def test_tray_restore_preserves_maximized_state(self):
        with patch.object(launcher_window_state, "update_settings_fields"):
            win = QMainWindow()
            win.data = {"settings": {}}
            restore_window_state(win)
            win._was_maximized = True
            with patch.object(win, "showMaximized") as mock_max, \
                 patch.object(win, "showNormal") as mock_norm:
                restore_window_from_tray(win)
                mock_max.assert_called_once()
                mock_norm.assert_not_called()

            # Khi cửa sổ đang hiện và đã bỏ Maximize, không được ép Maximize lại
            win._was_maximized = True
            win.showNormal()
            win.resize(760, 600)
            win.show()
            app.processEvents()
            restore_window_from_tray(win)
            self.assertEqual((win.width(), win.height()), (760, 600))
            self.assertFalse(win._was_maximized)
            win.close()


if __name__ == "__main__":
    unittest.main()
