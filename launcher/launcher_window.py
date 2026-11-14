# -*- coding: utf-8 -*-
"""
Cửa sổ chính của Antigravity Profile Launcher (PyQt6).
Hỗ trợ đầy đủ Windows và Linux với 1 codebase thống nhất.
"""

import os
import sys
import signal
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QMessageBox
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIcon

from launcher_storage import (
    load_data, save_data, APP_ICON, delete_account_completely,
    get_app_binary, get_ide_binary
)
from launcher_i18n import tr, set_language
from launcher_layout import build_launcher_layout, retranslate_layout, apply_launcher_style
from launcher_treeview import (
    setup_treeview, populate_treeview, get_selected_profile,
    update_row_quota_display, update_treeview_headers
)
from launcher_monitor import update_monitor_ui, send_proxy_cmd
from launcher_proxy import (
    is_proxy_running, stop_proxy, ensure_proxy_running,
    launch_profile, stop_all_launched_apps
)
from launcher_quota_runner import (
    refresh_all_quota, auto_refresh_quota, stop_spinner_animation
)
from launcher_oauth import start_google_oauth_flow
from launcher_shortcut import create_desktop_shortcut
from launcher_settings_dialog import LauncherSettingsDialog

class LauncherWindow(QMainWindow):
    """Cửa sổ điều khiển chính Antigravity Launcher."""

    def __init__(self):
        super().__init__()
        self.data = load_data()
        self.cooldown_remaining = 0
        self.auto_refresh_enabled = self.data.get("settings", {}).get("round_robin_enabled", True)

        self.setWindowTitle(tr("app.title"))
        self.resize(760, 640)
        if APP_ICON:
            self.setWindowIcon(QIcon(APP_ICON))

        build_launcher_layout(self)
        setup_treeview(self)
        self._refresh_list()

        # Timers
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_live_monitor)
        self.monitor_timer.start(500)

        self.auto_quota_timer = QTimer(self)
        self.auto_quota_timer.timeout.connect(self.on_auto_quota_tick)
        self.auto_quota_timer.start(5 * 60 * 1000)

        # Quét Quota ngầm sau khi mở ứng dụng 2 giây
        QTimer.singleShot(2000, self.on_refresh_all_quota)

        # Tự động kích hoạt Micro-Proxy ở chế độ STANDBY sau khi mở Launcher
        QTimer.singleShot(300, ensure_proxy_running)

        # Tự động tạo desktop shortcut lần đầu khởi chạy (nếu chưa tạo)
        if not self.data.get("settings", {}).get("shortcut_created", False):
            create_desktop_shortcut()
            self.data.setdefault("settings", {})["shortcut_created"] = True
            save_data(self.data)

        # Kiểm tra tự động phát hiện đường dẫn: nếu cả 2 đều không tìm thấy thì mở Cài đặt
        app_bin = get_app_binary(self.data)
        ide_bin = get_ide_binary(self.data)
        if (not app_bin or not os.path.exists(app_bin)) and (not ide_bin or not os.path.exists(ide_bin)):
            QTimer.singleShot(600, self.on_settings_clicked)

    def on_language_changed(self, idx):
        """Xử lý sự kiện người dùng đổi ngôn ngữ từ ComboBox."""
        code = self.combo_lang.itemData(idx)
        if not code or code == self.data.get("settings", {}).get("language"):
            return
        set_language(code)
        self.data.setdefault("settings", {})["language"] = code
        save_data(self.data)
        self.retranslate_ui()

    def retranslate_ui(self):
        """Cập nhật lại văn bản trên toàn bộ giao diện."""
        retranslate_layout(self)
        update_treeview_headers(self)
        self._refresh_list()

    def _refresh_list(self, select_id=None):
        """Làm mới dữ liệu hiển thị trên bảng tài khoản."""
        populate_treeview(self, select_id=select_id)

    def _get_selected(self):
        """Lấy profile của dòng đang chọn."""
        return get_selected_profile(self)

    def _update_row_quota(self, profile_id, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid):
        """Cập nhật Quota một dòng trên bảng."""
        update_row_quota_display(self, profile_id, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid)

    def on_refresh_all_quota(self, widget=None):
        """Làm mới Quota toàn bộ tài khoản."""
        refresh_all_quota(self)

    def on_auto_quota_tick(self):
        """Sự kiện quét Quota định kỳ."""
        if self.auto_refresh_enabled:
            auto_refresh_quota(self)

    def on_toggle_auto_quota(self):
        """Bật/tắt tự động làm mới Quota định kỳ."""
        self.auto_refresh_enabled = not self.auto_refresh_enabled
        self.data.setdefault("settings", {})["round_robin_enabled"] = self.auto_refresh_enabled
        save_data(self.data)
        update_treeview_headers(self)

    def on_account_toggled(self, profile_id, enabled):
        """Bật hoặc tắt trạng thái kích hoạt của một tài khoản."""
        for p in self.data.get("profiles", []):
            if p.get("id") == profile_id:
                p["enabled"] = enabled
                break
        save_data(self.data)
        self._refresh_list(select_id=profile_id)

    def on_spin_changed(self, val):
        """Cập nhật số lượt request tối đa trên mỗi tài khoản."""
        self.data.setdefault("settings", {})["requests_per_account"] = val
        save_data(self.data)
        self._refresh_list()

    def on_manual_next_account(self):
        """Gửi lệnh chuyển ngay sang tài khoản tiếp theo."""
        send_proxy_cmd(self, "next")
        self.update_live_monitor()

    def on_toggle_proxy_btn(self):
        """Bật hoặc tạm dừng/tiếp tục xoay vòng Micro-Proxy."""
        if is_proxy_running():
            send_proxy_cmd(self, "toggle_pause")
        else:
            ensure_proxy_running()
        self.update_live_monitor()

    def update_live_monitor(self):
        """Cập nhật trạng thái hiển thị của khung Monitor."""
        update_monitor_ui(self)

    def on_add_account(self):
        """Khởi động quy trình đăng nhập Google OAuth."""
        start_google_oauth_flow(self)

    def on_delete_account(self):
        """Xóa tài khoản đang chọn kèm cảnh báo."""
        sel = self._get_selected()
        if not sel:
            return

        label = sel.get("email") or sel.get("name") or "Account"
        ans = QMessageBox.question(
            self,
            tr("dialog.delete_title").format(label=label),
            tr("dialog.delete_warning"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.data = delete_account_completely(sel)
            self._refresh_list()
            self.lbl_info.setText(tr("dialog.deleted_msg").format(label=label))

    def activate_window(self):
        """Kích hoạt và đưa cửa sổ launcher lên tiền cảnh (Single-Instance)."""
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        handle = self.windowHandle()
        if handle and hasattr(handle, "requestActivate"):
            handle.requestActivate()

    def on_settings_clicked(self):
        """Mở hộp thoại Cài đặt (Settings Dialog)."""
        dlg = LauncherSettingsDialog(self)
        dlg.exec()

    def on_launch_app_clicked(self):
        """Khởi chạy Antigravity App (2.0) với tài khoản đang chọn."""
        self._launch_target("app", self.btn_launch_app, "🚀 " + tr("btn.launch_app"))

    def on_launch_ide_clicked(self):
        """Khởi chạy Antigravity IDE với tài khoản đang chọn."""
        self._launch_target("ide", self.btn_launch_ide, "💻 " + tr("btn.launch_ide"))

    def on_launch_clicked(self):
        """Hàm tương thích ngược với nút launch cũ."""
        self.on_launch_app_clicked()

    def _launch_target(self, target: str, button, default_text: str):
        """Khởi chạy App hoặc IDE kèm trạng thái nút bấm."""
        sel = self._get_selected()
        if not sel:
            QMessageBox.warning(self, tr("msg.no_account_title"), tr("msg.no_account_desc"))
            return

        data_dir = sel.get("data_dir")
        if not data_dir:
            return

        button.setEnabled(False)
        button.setText(tr("msg.launching"))

        def restore_btn():
            button.setEnabled(True)
            button.setText(default_text)

        ok = launch_profile(data_dir, target=target, use_proxy=True)
        if ok:
            QTimer.singleShot(1500, restore_btn)
        else:
            restore_btn()
            label = "Antigravity App (2.0)" if target == "app" else "Antigravity IDE"
            QMessageBox.critical(self, tr("msg.launch_error_title"), tr("msg.launch_error_desc").format(target=label))

    def closeEvent(self, event):
        """Xử lý sự kiện đóng cửa sổ."""
        self.monitor_timer.stop()
        self.auto_quota_timer.stop()
        stop_spinner_animation(self)
        event.accept()

def run_gui():
    """Hàm khởi động ứng dụng giao diện chính."""
    from launcher_single_instance import check_single_instance, setup_single_instance_listener

    app = QApplication(sys.argv)
    app.setApplicationName("antigravity-launcher")
    app.setDesktopFileName("antigravity-launcher")
    is_primary, server = check_single_instance()
    if not is_primary:
        sys.exit(0)

    apply_launcher_style(app)
    app.setWindowIcon(QIcon(APP_ICON))
    win = LauncherWindow()
    if server:
        setup_single_instance_listener(server, win.activate_window)
    win.show()

    def handle_signal(sig, frame):
        stop_all_launched_apps()
        stop_proxy()
        QApplication.quit()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        ret = app.exec()
    finally:
        stop_all_launched_apps()
        stop_proxy()
    sys.exit(ret)

if __name__ == "__main__":
    run_gui()
