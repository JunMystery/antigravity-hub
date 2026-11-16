# -*- coding: utf-8 -*-
import sys
import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from launcher.launcher_tray import TrayManager


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


if __name__ == "__main__":
    unittest.main()
