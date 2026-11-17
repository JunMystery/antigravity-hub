# -*- coding: utf-8 -*-
"""
Headless unit tests for Sidebar Navigation, Dashboard, Accounts, and Settings views.
"""

import sys
import unittest
sys.path.insert(0, "launcher")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from launcher_sidebar import SidebarNav
from launcher_view_dashboard import DashboardView
from launcher_view_accounts import AccountsView
from launcher_view_settings import SettingsView
from launcher_window import LauncherWindow

app = QApplication.instance() or QApplication(["-platform", "offscreen"])

class TestViewNavigation(unittest.TestCase):
    """Kiểm tra điều hướng Sidebar và các view chuyên trách."""

    @classmethod
    def setUpClass(cls):
        cls.win = LauncherWindow()

    def test_sidebar_signal_and_active_state(self):
        """Xác nhận SidebarNav phát tín hiệu view_changed và cập nhật nút active không chứa emoji rác."""
        sidebar = self.win.sidebar
        received_views = []
        sidebar.view_changed.connect(lambda v: received_views.append(v))

        sidebar.buttons["accounts"].click()
        self.assertIn("accounts", received_views)
        self.assertTrue(sidebar.buttons["accounts"].view_id == "accounts")
        self.assertIsNotNone(sidebar.lbl_footer)
        from launcher import __version__
        self.assertIn(__version__, sidebar.lbl_footer.text())
        self.assertIn("JunMystery", sidebar.lbl_footer.text())
        self.assertIn(sidebar.buttons["dashboard"].text(), ["Dashboard", "Tổng quan"])
        self.assertIn(sidebar.buttons["accounts"].text(), ["Accounts", "Tài khoản"])
        self.assertIn(sidebar.buttons["logs"].text(), ["Logs", "Nhật ký"])
        self.assertIn(sidebar.buttons["settings"].text(), ["Settings", "Cài đặt"])

    def test_window_stacked_view_switching(self):
        """Xác nhận LauncherWindow chuyển đổi view qua QStackedWidget chính xác."""
        self.win.switch_view("dashboard")
        self.assertEqual(self.win.stack.currentWidget(), self.win.view_dashboard)

        self.win.switch_view("accounts")
        self.assertEqual(self.win.stack.currentWidget(), self.win.view_accounts)

        self.win.switch_view("logs")
        self.assertEqual(self.win.stack.currentWidget(), self.win.view_logs)

        self.win.switch_view("settings")
        self.assertEqual(self.win.stack.currentWidget(), self.win.view_settings)

    def test_dashboard_components_and_filtering(self):
        """Xác nhận DashboardView chứa CompactStatusBar, grouped buttons và bảng feed."""
        dash = self.win.view_dashboard
        self.assertIsNotNone(dash.status_bar)
        self.assertIsNotNone(dash.card_status)
        self.assertIsNotNone(dash.card_acc)
        self.assertIsNotNone(dash.card_turn)
        self.assertIsNotNone(dash.card_total)

        # Kiểm tra action buttons và objectNames (không chứa emoji rác)
        self.assertEqual(dash.btn_launch_app.objectName(), "btn_launch_app")
        self.assertEqual(dash.btn_launch_ide.objectName(), "btn_launch_ide")
        self.assertEqual(dash.btn_next.objectName(), "btn_proxy_next")
        self.assertEqual(dash.btn_toggle_proxy.objectName(), "btn_proxy_toggle")
        self.assertNotIn("🚀", dash.btn_launch_app.text())
        self.assertNotIn("💻", dash.btn_launch_ide.text())
        self.assertNotIn("⏭", dash.btn_next.text())

        # Kiểm tra thuộc tính trên LauncherWindow
        self.assertIs(self.win.btn_launch_app, dash.btn_launch_app)
        self.assertIs(self.win.btn_launch_ide, dash.btn_launch_ide)
        self.assertIs(self.win.btn_next, dash.btn_next)
        self.assertIs(self.win.btn_toggle_proxy, dash.btn_toggle_proxy)

        # Kiểm tra bảng activity và tương thích ngược
        self.assertIsNotNone(dash.table_chat)
        self.assertIsNotNone(dash.table_subagent)
        self.assertIsNotNone(dash.table_feed)

        # Kiểm tra lọc tag
        dash._set_filter("MAIN")
        self.assertEqual(dash.active_filter, "MAIN")
        dash._set_filter("SUBAGENT")
        self.assertEqual(dash.active_filter, "SUBAGENT")
        dash._set_filter("ALL")
        self.assertEqual(dash.active_filter, "ALL")

    def test_accounts_view_table_and_actions(self):
        """Xác nhận AccountsView chứa bảng tài khoản và nút chức năng."""
        acc_view = self.win.view_accounts
        self.assertIsNotNone(acc_view.treeview)
        self.assertEqual(acc_view.treeview.columnCount(), 6)
        self.assertIsNotNone(acc_view.btn_add)
        self.assertIsNotNone(acc_view.btn_del)
        self.assertIsNotNone(acc_view.btn_refresh_all)
        self.assertIsNotNone(acc_view.spin_reqs)

    def test_settings_view_retention_and_clear(self):
        """Xác nhận SettingsView quản lý retention period, nút clear log và nút mở data folder."""
        from unittest.mock import patch
        settings = self.win.view_settings
        self.assertIsNotNone(settings.txt_app)
        self.assertIsNotNone(settings.txt_ide)
        self.assertIsNotNone(settings.combo_retention)
        self.assertEqual(settings.combo_retention.count(), 3)
        self.assertIsNotNone(settings.btn_clear_log)
        self.assertIsNotNone(settings.btn_open_data)
        self.assertIn("Data", settings.btn_open_data.text())

        # Kiểm tra đổi retention days cập nhật win.data và lưu trữ
        idx_90 = settings.combo_retention.findData(90)
        settings.combo_retention.setCurrentIndex(idx_90)
        self.assertEqual(self.win.data.get("settings", {}).get("log_retention_days"), 90)

        # Kiểm tra _save_settings lưu trọn vẹn cả paths và retention days
        with patch("launcher_view_settings.QMessageBox.information"):
            settings._save_settings()
        self.assertEqual(self.win.data.get("settings", {}).get("log_retention_days"), 90)

        # Kiểm tra bấm nút mở thư mục dữ liệu gọi QDesktopServices.openUrl
        with patch("launcher_view_settings.QDesktopServices.openUrl") as mock_open:
            settings.btn_open_data.click()
            mock_open.assert_called_once()

    def test_settings_application_paths_row_height_not_squished(self):
        """Xác nhận SettingsView bọc QScrollArea và hàng Application Paths giữ chiều cao >= 32px ở kích thước nhỏ nhất."""
        from PyQt6.QtWidgets import QScrollArea
        self.win.switch_view("settings")
        self.win.resize(760, 480)
        self.win.show()
        app.processEvents()

        settings = self.win.view_settings
        self.assertIsInstance(settings.scroll_area, QScrollArea)
        for widget in (
            settings.txt_app, settings.btn_browse_app, settings.btn_detect_app,
            settings.txt_ide, settings.btn_browse_ide, settings.btn_detect_ide
        ):
            self.assertGreaterEqual(widget.minimumHeight(), 32)
            self.assertGreaterEqual(widget.height(), 32)

    def test_launch_buttons_retain_labels_after_restore(self):
        """Xác nhận nhãn nút không bị mất sau khi hoàn tất chu trình khởi chạy (không chứa emoji rác)."""
        from unittest.mock import patch
        import time

        win = self.win
        self.assertNotIn("🚀", win.btn_launch_app.text())
        self.assertNotIn("💻", win.btn_launch_ide.text())

        with patch.object(win, "_get_selected", return_value={"data_dir": "/fake/profile"}), \
             patch("launcher_window.launch_profile", return_value=True):
            win.on_launch_app_clicked()
            self.assertFalse(win.btn_launch_app.isEnabled())

            start_t = time.time()
            while time.time() - start_t < 1.6:
                app.processEvents()
                time.sleep(0.05)

            self.assertTrue(win.btn_launch_app.isEnabled())
            self.assertNotIn("🚀", win.btn_launch_app.text())

        with patch.object(win, "_get_selected", return_value={"data_dir": "/fake/profile"}), \
             patch("launcher_window.launch_profile", return_value=True):
            win.on_launch_ide_clicked()
            start_t = time.time()
            while time.time() - start_t < 1.6:
                app.processEvents()
                time.sleep(0.05)
            self.assertTrue(win.btn_launch_ide.isEnabled())
            self.assertNotIn("💻", win.btn_launch_ide.text())

    def test_dashboard_dynamic_retranslation(self):
        """Xác nhận DashboardView.retranslate_ui() cập nhật đúng text theo ngôn ngữ EN / VI."""
        from launcher_i18n import set_language
        dash = self.win.view_dashboard

        set_language("en")
        self.win.retranslate_ui()
        self.assertEqual(dash.btn_launch_app.text(), "Launch App (2.0)")
        self.assertEqual(dash.btn_launch_ide.text(), "Launch IDE")
        self.assertEqual(dash.btn_next.text(), "Next")
        self.assertEqual(dash.card_status.lbl_title.text(), "Status")
        self.assertEqual(dash.card_acc.lbl_title.text(), "Account")
        self.assertEqual(dash.card_turn.lbl_title.text(), "Turn")
        self.assertEqual(dash.card_total.lbl_title.text(), "Total")
        self.assertEqual(self.win.view_settings.btn_open_data.text(), "Open Data Directory")
        self.assertEqual(self.win.view_settings.btn_clear_log.text(), "Clear Log")
        self.assertEqual(self.win.view_settings.grp_logs.title(), "Log Management & Retention")
        self.assertEqual(self.win.sidebar.buttons["accounts"].text(), "Accounts")
        self.assertEqual(self.win.sidebar.buttons["logs"].text(), "Logs")
        self.assertEqual(self.win.sidebar.buttons["settings"].text(), "Settings")

        set_language("vi")
        self.win.retranslate_ui()
        self.assertEqual(dash.btn_launch_app.text(), "Khởi chạy App (2.0)")
        self.assertEqual(dash.btn_launch_ide.text(), "Khởi chạy IDE")
        self.assertEqual(dash.btn_next.text(), "Kế tiếp")
        self.assertEqual(dash.card_status.lbl_title.text(), "Trạng thái")
        self.assertEqual(dash.card_acc.lbl_title.text(), "Tài khoản")
        self.assertEqual(dash.card_turn.lbl_title.text(), "Lượt")
        self.assertEqual(dash.card_total.lbl_title.text(), "Tổng")
        self.assertEqual(self.win.view_settings.btn_open_data.text(), "Mở thư mục Data")
        self.assertEqual(self.win.view_settings.btn_clear_log.text(), "Xóa Log")
        self.assertEqual(self.win.view_settings.grp_logs.title(), "Quản lý & Lưu trữ Nhật ký")
        self.assertEqual(self.win.sidebar.buttons["accounts"].text(), "Tài khoản")
        self.assertEqual(self.win.sidebar.buttons["logs"].text(), "Nhật ký")
        self.assertEqual(self.win.sidebar.buttons["settings"].text(), "Cài đặt")

    def test_logs_view_features(self):
        """Xác nhận LogsView có bảng 5 cột, toolbar và hỗ trợ lọc tìm kiếm."""
        from launcher_token_delegate import TokenInOutDelegate
        logs_view = self.win.view_logs
        self.assertIsNotNone(logs_view)
        self.assertEqual(logs_view.table.columnCount(), 5)
        self.assertEqual(logs_view.table.horizontalHeaderItem(2).text(), "Model")
        self.assertIsInstance(logs_view.table.itemDelegateForColumn(4), TokenInOutDelegate)
        self.assertIsNotNone(logs_view.txt_search)
        self.assertIsNotNone(logs_view.btn_refresh)
        self.assertIsNotNone(logs_view.btn_open_file)
        self.assertIsNotNone(logs_view.btn_copy)
        self.assertIsNotNone(logs_view.btn_clear)

        # Kiểm tra nạp dữ liệu mẫu bao gồm cả sự kiện hệ thống
        logs_view._entries = [
            {"time": "12:00:01", "thread": "MAIN", "action": "POST streamGenerateContent", "acc": "user@gmail.com", "tokens": "1.8K / 420"},
            {"time": "12:00:02", "thread": "SUBAGENT", "action": "GET models", "acc": "sub@gmail.com", "tokens": "-- / --"},
            {"time": "12:00:03", "thread": "MAIN", "action": "Client Abort", "acc": "user@gmail.com", "tokens": "--"},
            {"time": "12:00:04", "thread": "MAIN", "action": "Rotator Restore", "acc": "user@gmail.com", "tokens": "--"}
        ]
        logs_view._populate_table()
        self.assertEqual(logs_view.table.rowCount(), 4)

        # Lọc tìm kiếm
        logs_view.txt_search.setText("SUBAGENT")
        self.assertEqual(logs_view.table.rowCount(), 1)
        logs_view.txt_search.setText("")
        self.assertEqual(logs_view.table.rowCount(), 4)

if __name__ == "__main__":
    unittest.main()
