# -*- coding: utf-8 -*-
"""
Headless unit tests for Sidebar Navigation, Dashboard, Accounts, and Settings views.
"""

import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER_DIR = os.path.join(ROOT_DIR, "launcher")
if LAUNCHER_DIR not in sys.path:
    sys.path.insert(0, LAUNCHER_DIR)

from PyQt6.QtWidgets import QApplication, QComboBox
from PyQt6.QtCore import Qt

import launcher_storage, launcher_log_manager, launcher_view_settings, launcher_window
from launcher_window import LauncherWindow

app = QApplication.instance() or QApplication(["-platform", "offscreen"])

class TestViewNavigation(unittest.TestCase):
    """Kiểm tra điều hướng Sidebar và các view chuyên trách."""

    @classmethod
    def setUpClass(cls):
        cls._tmp_dir = tempfile.mkdtemp()
        cfg_dir = os.path.join(cls._tmp_dir, "config")
        prof_base = os.path.join(cls._tmp_dir, "profiles_base")
        os.makedirs(cfg_dir, exist_ok=True)
        patch_specs = [
            (launcher_storage, "CONFIG_DIR", cfg_dir),
            (launcher_storage, "PROFILES_FILE", os.path.join(cfg_dir, "profiles.json")),
            (launcher_storage, "ACCOUNTS_FILE", os.path.join(cfg_dir, "accounts.json")),
            (launcher_storage, "PROFILES_BASE_DIR", prof_base),
            (launcher_log_manager, "CONFIG_DIR", cfg_dir),
            (launcher_view_settings, "CONFIG_DIR", cfg_dir),
            (launcher_window, "PROFILES_BASE_DIR", prof_base),
        ]
        cls._patches = [patch.object(m, k, v) for m, k, v in patch_specs] + [
            patch.object(launcher_window, fn) for fn in ("ensure_proxy_running", "prune_logs", "create_desktop_shortcut")
        ]
        for p in cls._patches:
            p.start()
        cls.win = LauncherWindow()
        cls.win.monitor_timer.stop()
        cls.win.auto_quota_timer.stop()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "win") and cls.win:
            cls.win.close()
        for p in reversed(getattr(cls, "_patches", [])):
            p.stop()
        shutil.rmtree(getattr(cls, "_tmp_dir", ""), ignore_errors=True)

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
        """Xác nhận Sidebar có lockup + nút icon Launch và DashboardView có StatusBar + Dropdown gọn."""
        dash = self.win.view_dashboard
        sidebar = self.win.sidebar
        self.assertIsNotNone(sidebar.logo_lockup)
        self.assertFalse(sidebar.logo_lockup.pixmap().isNull())
        self.assertIn("#6c7086", sidebar.logo_lockup.styleSheet())
        self.assertIn("#1e1e2e", sidebar.logo_lockup.styleSheet())
        self.assertIsNotNone(dash.status_bar)
        self.assertFalse(dash.status_bar.lbl_acc.isHidden())
        self.assertIsInstance(dash.combo_account, QComboBox)
        self.assertEqual(dash.combo_account.height(), 30)
        self.assertIsNotNone(dash.card_status)
        self.assertIsNotNone(dash.card_acc)
        self.assertIsNotNone(dash.card_turn)
        self.assertIsNotNone(dash.card_total)

        # Kiểm tra nút Launch trên Sidebar (icon + nhãn ngắn) và thuộc tính tương thích trên LauncherWindow
        self.assertEqual(sidebar.btn_launch_app.objectName(), "btn_launch_app")
        self.assertEqual(sidebar.btn_launch_ide.objectName(), "btn_launch_ide")
        self.assertTrue(sidebar.btn_launch_app.property("keep_short_label"))
        self.assertTrue(sidebar.btn_launch_ide.property("keep_short_label"))
        self.assertEqual(sidebar.btn_launch_app.text(), "App")
        self.assertEqual(sidebar.btn_launch_ide.text(), "IDE")
        self.assertFalse(sidebar.btn_launch_app.icon().isNull())
        self.assertFalse(sidebar.btn_launch_ide.icon().isNull())
        self.assertEqual(dash.btn_next.objectName(), "btn_proxy_next")
        self.assertEqual(dash.btn_toggle_proxy.objectName(), "btn_proxy_toggle")

        self.assertIs(self.win.btn_launch_app, sidebar.btn_launch_app)
        self.assertIs(self.win.btn_launch_ide, sidebar.btn_launch_ide)
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
        """Xác nhận nút Launch giữ nguyên nhãn ngắn App/IDE và cập nhật tooltip khi chạy."""
        from unittest.mock import patch
        import time

        win = self.win
        self.assertEqual(win.btn_launch_app.text(), "App")
        self.assertEqual(win.btn_launch_ide.text(), "IDE")

        with patch.object(win, "_get_selected", return_value={"data_dir": "/fake/profile"}), \
             patch("launcher_window.launch_profile", return_value=True):
            win.on_launch_app_clicked()
            self.assertFalse(win.btn_launch_app.isEnabled())

            start_t = time.time()
            while time.time() - start_t < 1.6:
                app.processEvents()
                time.sleep(0.05)

            self.assertTrue(win.btn_launch_app.isEnabled())
            self.assertEqual(win.btn_launch_app.text(), "App")
            self.assertIn("App", win.btn_launch_app.toolTip())

        with patch.object(win, "_get_selected", return_value={"data_dir": "/fake/profile"}), \
             patch("launcher_window.launch_profile", return_value=True):
            win.on_launch_ide_clicked()
            start_t = time.time()
            while time.time() - start_t < 1.6:
                app.processEvents()
                time.sleep(0.05)
            self.assertTrue(win.btn_launch_ide.isEnabled())
            self.assertEqual(win.btn_launch_ide.text(), "IDE")
            self.assertIn("IDE", win.btn_launch_ide.toolTip())

    def test_dashboard_dynamic_retranslation(self):
        """Xác nhận SidebarNav và DashboardView.retranslate_ui() cập nhật đúng text/tooltip EN / VI."""
        from launcher_i18n import set_language
        dash = self.win.view_dashboard
        sidebar = self.win.sidebar

        set_language("en")
        self.win.retranslate_ui()
        self.assertEqual(sidebar.btn_launch_app.toolTip(), "Launch App (2.0)")
        self.assertEqual(sidebar.btn_launch_ide.toolTip(), "Launch IDE")
        self.assertEqual(dash.btn_next.text(), "Next")
        self.assertEqual(dash.card_status.lbl_title.text(), "Status")
        self.assertEqual(dash.card_acc.lbl_title.text(), "Account")
        self.assertEqual(dash.card_turn.lbl_title.text(), "Turn")
        self.assertEqual(dash.card_total.lbl_title.text(), "Total")
        self.assertEqual(self.win.view_settings.btn_open_data.text(), "Open Data Directory")
        self.assertEqual(self.win.view_settings.btn_clear_log.text(), "Clear Log")
        self.assertEqual(self.win.view_settings.grp_logs.title(), "Log Management & Retention")
        self.assertEqual(sidebar.buttons["accounts"].text(), "Accounts")
        self.assertEqual(sidebar.buttons["logs"].text(), "Logs")
        self.assertEqual(sidebar.buttons["settings"].text(), "Settings")

        set_language("vi")
        self.win.retranslate_ui()
        self.assertEqual(sidebar.btn_launch_app.toolTip(), "Khởi chạy App (2.0)")
        self.assertEqual(sidebar.btn_launch_ide.toolTip(), "Khởi chạy IDE")
        self.assertEqual(dash.btn_next.text(), "Kế tiếp")
        self.assertEqual(dash.card_status.lbl_title.text(), "Trạng thái")
        self.assertEqual(dash.card_acc.lbl_title.text(), "Tài khoản")
        self.assertEqual(dash.card_turn.lbl_title.text(), "Lượt")
        self.assertEqual(dash.card_total.lbl_title.text(), "Tổng")
        self.assertEqual(self.win.view_settings.btn_open_data.text(), "Mở thư mục Data")
        self.assertEqual(self.win.view_settings.btn_clear_log.text(), "Xóa Log")
        self.assertEqual(self.win.view_settings.grp_logs.title(), "Quản lý & Lưu trữ Nhật ký")
        self.assertEqual(sidebar.buttons["accounts"].text(), "Tài khoản")
        self.assertEqual(sidebar.buttons["logs"].text(), "Nhật ký")
        self.assertEqual(sidebar.buttons["settings"].text(), "Cài đặt")

    def test_logs_view_features(self):
        """Xác nhận LogsView có bảng 4 cột, toolbar và hỗ trợ lọc tìm kiếm."""
        from launcher_token_delegate import TokenInOutDelegate
        logs_view = self.win.view_logs
        self.assertIsNotNone(logs_view)
        self.assertEqual(logs_view.table.columnCount(), 4)
        headers = [logs_view.table.horizontalHeaderItem(c).text() for c in range(4)]
        self.assertEqual(headers[1], "Model")
        self.assertFalse(any(h in headers for h in ("Thread", "Luồng")))
        self.assertIsInstance(logs_view.table.itemDelegateForColumn(3), TokenInOutDelegate)
        self.assertIsNotNone(logs_view.txt_search)
        self.assertIsNotNone(logs_view.btn_refresh)
        self.assertIsNotNone(logs_view.btn_open_file)
        self.assertIsNotNone(logs_view.btn_copy)
        self.assertIsNotNone(logs_view.btn_clear)

        # Kiểm tra nạp dữ liệu mẫu bao gồm cả sự kiện hệ thống
        logs_view._entries = [
            {"time": "12:00:01", "action": "POST streamGenerateContent", "acc": "user@gmail.com", "tokens": "1.8K / 420"},
            {"time": "12:00:02", "action": "GET models", "acc": "sub@gmail.com", "tokens": "-- / --"},
            {"time": "12:00:03", "action": "Client Abort", "acc": "user@gmail.com", "tokens": "--"},
            {"time": "12:00:04", "action": "Rotator Restore", "acc": "user@gmail.com", "tokens": "--"}
        ]
        logs_view._populate_table()
        self.assertEqual(logs_view.table.rowCount(), 4)

        # Lọc tìm kiếm
        logs_view.txt_search.setText("sub@gmail.com")
        self.assertEqual(logs_view.table.rowCount(), 1)
        logs_view.txt_search.setText("")
        self.assertEqual(logs_view.table.rowCount(), 4)

if __name__ == "__main__":
    unittest.main()
