# -*- coding: utf-8 -*-
"""
Cửa sổ chính của Antigravity Profile Launcher (PyQt6).
Điều phối Sidebar navigation và QStackedWidget (Dashboard, Accounts, Settings).
"""

import os
import sys
import time
import json
import signal
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QMessageBox, QWidget, QHBoxLayout, QStackedWidget
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIcon

from launcher_storage import (
    load_data, save_data, APP_ICON, delete_account_completely,
    PROFILES_BASE_DIR
)
from launcher_i18n import tr, set_language
from launcher_layout import apply_launcher_style
from launcher_treeview import (
    populate_treeview, get_selected_profile,
    update_row_quota_display, update_treeview_headers,
    select_active_profile_row
)
from launcher_monitor import send_proxy_cmd, STATUS_FILE
from launcher_proxy import (
    is_proxy_running, stop_proxy, ensure_proxy_running,
    launch_profile, stop_all_launched_apps
)
from launcher_quota_runner import (
    refresh_all_quota, auto_refresh_quota, stop_spinner_animation
)
from launcher_oauth import start_google_oauth_flow
from launcher_shortcut import create_desktop_shortcut
from launcher_log_manager import prune_logs
from launcher_sidebar import SidebarNav
from launcher_view_dashboard import DashboardView
from launcher_view_accounts import AccountsView
from launcher_view_logs import LogsView
from launcher_view_settings import SettingsView
from launcher_tray import TrayManager, handle_hide_on_launch, handle_close_event, clean_exit
from launcher_prompt_dialog import show_about_prompt

class LauncherWindow(QMainWindow):
    """Cửa sổ điều phối chính Antigravity Launcher với Sidebar Navigation."""

    def __init__(self):
        super().__init__()
        self.data = load_data()
        self.cooldown_remaining = 0
        self.auto_refresh_enabled = self.data.get("settings", {}).get("round_robin_enabled", True)
        self._last_manual_select_ms = 0
        self._live_active_email = ""

        set_language(self.data.get("settings", {}).get("language", "vi"))
        self.setWindowTitle(tr("app.title"))
        self.resize(940, 620)
        self.setMinimumSize(760, 480)
        if APP_ICON and os.path.exists(APP_ICON):
            self.setWindowIcon(QIcon(APP_ICON))

        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = SidebarNav(self)
        root_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget(self)
        self.view_dashboard = DashboardView(self)
        self.view_accounts = AccountsView(self)
        self.view_logs = LogsView(self)
        self.view_settings = SettingsView(self)
        self.stack.addWidget(self.view_dashboard)
        self.stack.addWidget(self.view_accounts)
        self.stack.addWidget(self.view_logs)
        self.stack.addWidget(self.view_settings)

        self.view_map = {
            "dashboard": self.view_dashboard,
            "accounts": self.view_accounts,
            "logs": self.view_logs,
            "settings": self.view_settings
        }
        self.sidebar.view_changed.connect(self.switch_view)
        root_layout.addWidget(self.stack, 1)

        self.btn_launch_app = self.view_dashboard.btn_launch_app
        self.btn_launch_ide = self.view_dashboard.btn_launch_ide
        self.btn_launch = self.btn_launch_app
        self.btn_next = self.view_dashboard.btn_next
        self.btn_toggle_proxy = self.view_dashboard.btn_toggle_proxy
        self.combo_active_account = self.view_dashboard.combo_active_account
        self.combo_lang = self.sidebar.combo_lang
        self.tray = TrayManager(self)

        self._refresh_list()
        self.update_live_monitor()

        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_live_monitor)
        self.monitor_timer.start(500)
        self.auto_quota_timer = QTimer(self)
        self.auto_quota_timer.timeout.connect(self.on_auto_quota_tick)
        self.auto_quota_timer.start(5 * 60 * 1000)

        QTimer.singleShot(2000, self.on_refresh_all_quota)
        QTimer.singleShot(300, ensure_proxy_running)
        QTimer.singleShot(1000, prune_logs)

        if not self.data.get("settings", {}).get("shortcut_created", False):
            create_desktop_shortcut()
            self.data.setdefault("settings", {})["shortcut_created"] = True
            save_data(self.data)

    def switch_view(self, view_id: str):
        target = self.view_map.get(view_id)
        if target:
            if view_id == "logs" and hasattr(target, "load_logs"):
                target.load_logs()
            elif view_id == "accounts":
                select_active_profile_row(self)
            self.stack.setCurrentWidget(target)
            self.sidebar.set_active_view(view_id)

    def on_language_changed(self, idx):
        code = self.combo_lang.itemData(idx)
        if code and code != self.data.get("settings", {}).get("language"):
            set_language(code)
            self.data.setdefault("settings", {})["language"] = code
            save_data(self.data)
            self.retranslate_ui()

    def retranslate_ui(self):
        self.setWindowTitle(tr("app.title"))
        self.sidebar.retranslate_ui()
        self.view_accounts.retranslate_ui()
        if hasattr(self, "view_dashboard"):
            self.view_dashboard.retranslate_ui()
        if hasattr(self, "view_logs"):
            self.view_logs.retranslate_ui()
        if hasattr(self, "view_settings"):
            self.view_settings.retranslate_ui()
        if hasattr(self, "tray"):
            self.tray.retranslate_ui()
        self._refresh_list()

    def _refresh_list(self, select_id=None):
        populate_treeview(self, select_id=select_id)
        self._sync_active_account_ui()
    def _get_selected(self): return get_selected_profile(self)
    def _update_row_quota(self, profile_id, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid, q5_reset="", qw_reset="", qa_val=0, qa_text="--", qa_valid=False, qa_reset=""):
        update_row_quota_display(
            self, profile_id, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid,
            q5_reset, qw_reset, qa_val, qa_text, qa_valid, qa_reset
        )

    def on_refresh_all_quota(self, widget=None): refresh_all_quota(self)
    def on_auto_quota_tick(self):
        if self.auto_refresh_enabled: auto_refresh_quota(self)

    def on_toggle_auto_quota(self):
        self.auto_refresh_enabled = not self.auto_refresh_enabled
        self.data.setdefault("settings", {})["round_robin_enabled"] = self.auto_refresh_enabled
        save_data(self.data)
        update_treeview_headers(self)

    def on_account_toggled(self, profile_id, enabled):
        for p in self.data.get("profiles", []):
            if p.get("id") == profile_id:
                p["enabled"] = enabled
                break
        save_data(self.data)
        self._refresh_list(select_id=profile_id)

    def on_spin_changed(self, val):
        self.data.setdefault("settings", {})["requests_per_account"] = val
        save_data(self.data)
        self._refresh_list()

    def on_manual_next_account(self):
        send_proxy_cmd(self, "next")
        self.update_live_monitor()

    def _apply_round_robin_ui_state(self, enabled: bool, sync_proxy: bool = True):
        """Đồng bộ trạng thái tắt/bật Round Robin giữa Tab Tài khoản, Dashboard và Proxy."""
        enabled = bool(enabled)
        self.data.setdefault("settings", {})["auto_rotation_enabled"] = enabled
        save_data(self.data)

        if hasattr(self, "toggle_round_robin"):
            self.toggle_round_robin.blockSignals(True)
            self.toggle_round_robin.setChecked(enabled)
            self.toggle_round_robin.setToolTip(
                tr("tooltip.toggle_round_robin_on") if enabled else tr("tooltip.toggle_round_robin_off")
            )
            self.toggle_round_robin.blockSignals(False)
        if hasattr(self, "rr_info"):
            self.rr_info.setText(tr("opt.mode") if enabled else tr("opt.mode_fixed"))
        if hasattr(self, "spin_reqs"):
            self.spin_reqs.setEnabled(enabled)

        if sync_proxy and is_proxy_running():
            send_proxy_cmd(self, "resume" if enabled else "pause")
        self.update_live_monitor()

    def on_toggle_round_robin(self, enabled: bool):
        self._apply_round_robin_ui_state(enabled, sync_proxy=True)

    def on_toggle_proxy_btn(self):
        if is_proxy_running():
            was_paused = not bool(self.data.get("settings", {}).get("auto_rotation_enabled", True))
            if os.path.exists(STATUS_FILE):
                try:
                    with open(STATUS_FILE, "r", encoding="utf-8") as f:
                        st = json.load(f)
                    was_paused = bool(st.get("paused", False) or st.get("status") == "paused")
                except Exception:
                    pass
            send_proxy_cmd(self, "toggle_pause")
            self._apply_round_robin_ui_state(was_paused, sync_proxy=False)
        else:
            ensure_proxy_running()
            self.update_live_monitor()

    def _sync_active_account_ui(self):
        """Nạp danh sách tài khoản vào Dropdown chọn nhanh trên Dashboard."""
        if not hasattr(self, "combo_active_account") or self.combo_active_account is None:
            return
        profiles = self.data.get("profiles", [])
        active_id = self.data.get("settings", {}).get("active_account_id", "")

        self.combo_active_account.blockSignals(True)
        try:
            self.combo_active_account.clear()
            if not profiles:
                self.combo_active_account.addItem(tr("dashboard.no_active_account"), "")
                self.combo_active_account.setEnabled(False)
                if hasattr(self, "btn_use_account"):
                    self.btn_use_account.setEnabled(False)
                return

            self.combo_active_account.setEnabled(True)
            if hasattr(self, "btn_use_account"):
                self.btn_use_account.setEnabled(True)

            target_idx = 0
            for idx, p in enumerate(profiles):
                pid = p.get("id", "")
                email = p.get("email") or p.get("name") or "Account"
                label = email if p.get("enabled", True) else f"{email} [OFF]"
                self.combo_active_account.addItem(label, pid)
                self.combo_active_account.setItemData(idx, email, Qt.ItemDataRole.UserRole + 1)
                if active_id and pid == active_id:
                    target_idx = idx
            self.combo_active_account.setCurrentIndex(target_idx)
        finally:
            self.combo_active_account.blockSignals(False)

    def on_select_active_account(self, profile_id: str):
        """Chuyển Proxy và profile khởi chạy sang đích danh tài khoản được chọn."""
        if not profile_id:
            return
        profiles = self.data.get("profiles", [])
        profile = next((p for p in profiles if p.get("id") == profile_id), None)
        if not profile:
            return

        self._last_manual_select_ms = int(time.time() * 1000)
        need_reload = False
        if not profile.get("enabled", True):
            profile["enabled"] = True
            need_reload = True

        self.data.setdefault("settings", {})["active_account_id"] = profile.get("id", "")
        save_data(self.data)

        if need_reload and is_proxy_running():
            send_proxy_cmd(self, "reload")

        target = profile.get("email") or profile.get("id") or ""
        if target and is_proxy_running():
            send_proxy_cmd(self, "select", {"target": target})

        self._refresh_list(select_id=profile.get("id"))
        if hasattr(self, "lbl_info"):
            self.lbl_info.setText(tr("msg.account_switched", label=profile.get("email") or profile.get("name") or "Account"))
        self.update_live_monitor()

    def on_use_selected_account(self):
        sel = self._get_selected()
        if sel:
            self.on_select_active_account(sel.get("id", ""))

    def on_dashboard_account_changed(self, idx: int):
        if idx < 0 or not hasattr(self, "combo_active_account"):
            return
        pid = self.combo_active_account.itemData(idx)
        if pid:
            self.on_select_active_account(pid)

    def update_live_monitor(self):
        if hasattr(self, "view_dashboard"): self.view_dashboard.update_dashboard()

    def on_add_account(self): start_google_oauth_flow(self)
    def on_delete_account(self):
        sel = self._get_selected()
        if not sel: return
        label = sel.get("email") or sel.get("name") or "Account"
        ans = QMessageBox.question(
            self, tr("dialog.delete_title").format(label=label), tr("dialog.delete_warning"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.data = delete_account_completely(sel)
            self._refresh_list()
            self.lbl_info.setText(tr("dialog.deleted_msg").format(label=label))

    def activate_window(self):
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        handle = self.windowHandle()
        if handle and hasattr(handle, "requestActivate"):
            handle.requestActivate()

    def on_settings_clicked(self): self.switch_view("settings")
    def on_launch_app_clicked(self): self._launch_target("app", getattr(self, "btn_launch_app", None), tr("btn.launch_app"))
    def on_launch_ide_clicked(self): self._launch_target("ide", getattr(self, "btn_launch_ide", None), tr("btn.launch_ide"))
    def on_launch_clicked(self): self.on_launch_app_clicked()

    def _launch_target(self, target: str, button, default_text: str):
        sel = self._get_selected()
        profiles = self.data.get("profiles", [])
        active_id = self.data.get("settings", {}).get("active_account_id", "")
        active_prof = next((p for p in profiles if p.get("id") == active_id), None) if active_id else None
        chosen = active_prof or sel or (profiles[0] if profiles else None)
        data_dir = chosen.get("data_dir") if chosen and chosen.get("data_dir") else os.path.join(PROFILES_BASE_DIR, "default")
        if button:
            button.setEnabled(False)
            button.setText(tr("msg.launching"))
        def restore_btn():
            if button:
                button.setEnabled(True)
                button.setText(default_text)
        if launch_profile(data_dir, target=target, use_proxy=True):
            QTimer.singleShot(1500, restore_btn)
            QTimer.singleShot(50, lambda: handle_hide_on_launch(self))
        else:
            restore_btn()
            label = "Antigravity App (2.0)" if target == "app" else "Antigravity IDE"
            QMessageBox.critical(self, tr("msg.launch_error_title"), tr("msg.launch_error_desc").format(target=label))

    def closeEvent(self, event): handle_close_event(self, event)
    def exit_app(self): clean_exit(self)
    def show_about(self): show_about_prompt(self)

def run_gui():
    from launcher_single_instance import check_single_instance, setup_single_instance_listener
    app = QApplication(sys.argv)
    app.setApplicationName("antigravity-launcher")
    app.setDesktopFileName("antigravity-launcher")
    is_primary, server = check_single_instance()
    if not is_primary:
        sys.exit(0)
    apply_launcher_style(app)
    if APP_ICON and os.path.exists(APP_ICON):
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
