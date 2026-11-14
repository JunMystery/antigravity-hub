# -*- coding: utf-8 -*-
"""
Cửa sổ chính của Antigravity Profile Launcher (PyQt6).
Hỗ trợ đầy đủ Windows và Linux với 1 codebase thống nhất.
"""

import sys
import signal
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QMessageBox
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIcon

from launcher_storage import (
    load_data, save_data, APP_ICON, delete_account_completely
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
from launcher_quota_runner import refresh_all_quota, auto_refresh_quota
from launcher_oauth import start_google_oauth_flow

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
        """Bật hoặc dừng tiến trình Micro-Proxy."""
        if is_proxy_running():
            stop_proxy()
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

        label = sel.get("name") or sel.get("email") or "Account"
        ans = QMessageBox.question(
            self,
            f"Xác nhận xóa tài khoản '{label}'?",
            f"Cảnh báo: Hành động này sẽ xóa hoàn toàn profile, thu hồi token và dữ liệu đĩa.\n\nBạn có chắc chắn muốn xóa không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.data = delete_account_completely(sel)
            self._refresh_list()
            self.lbl_info.setText(f"<b><span style='color:#f38ba8;'>Đã xóa tài khoản {label}.</span></b>")

    def on_row_double_clicked(self, item):
        """Mở nhanh Antigravity khi nhấp đúp vào một dòng tài khoản."""
        self.on_launch_clicked()

    def on_launch_clicked(self):
        """Khởi chạy Antigravity IDE với tài khoản đang chọn."""
        sel = self._get_selected()
        if not sel:
            QMessageBox.warning(self, "Chưa chọn tài khoản", "Vui lòng chọn một tài khoản để khởi chạy.")
            return

        data_dir = sel.get("data_dir")
        if not data_dir:
            return

        self.btn_launch.setEnabled(False)
        self.btn_launch.setText("Đang khởi chạy...")

        def restore_btn():
            self.btn_launch.setEnabled(True)
            self.btn_launch.setText(tr("btn.launch"))

        ok = launch_profile(data_dir, use_proxy=True)
        if ok:
            QTimer.singleShot(1500, restore_btn)
        else:
            restore_btn()
            QMessageBox.critical(self, "Lỗi khởi chạy", "Không thể khởi chạy Antigravity IDE. Kiểm tra log hệ thống.")

    def closeEvent(self, event):
        """Xử lý sự kiện đóng cửa sổ."""
        self.monitor_timer.stop()
        self.auto_quota_timer.stop()
        event.accept()

def run_gui():
    """Hàm khởi động ứng dụng giao diện chính."""
    app = QApplication(sys.argv)
    apply_launcher_style(app)
    win = LauncherWindow()
    win.show()

    def handle_signal(sig, frame):
        stop_all_launched_apps()
        stop_proxy()
        QApplication.quit()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    sys.exit(app.exec())

if __name__ == "__main__":
    run_gui()
