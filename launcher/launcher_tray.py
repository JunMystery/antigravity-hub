# -*- coding: utf-8 -*-
"""
Module quản lý Khay hệ thống (System Tray / Top Panel) cho Antigravity Launcher.
Hỗ trợ Windows System Tray và Linux Top Panel/AppIndicator qua QSystemTrayIcon.
"""

import os
from PyQt6.QtWidgets import (
    QSystemTrayIcon, QMenu, QApplication, QGroupBox,
    QVBoxLayout, QComboBox
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QObject

from launcher_i18n import tr
from launcher_paths import APP_ICON
from launcher_widget import SettingRow
from launcher_prompt_dialog import ask_hide_on_launch_prompt, ask_close_action_prompt, show_about_prompt
from launcher_window_state import hide_window_to_tray, capture_window_state

class TrayManager(QObject):
    """Quản lý biểu tượng khay hệ thống, menu ngữ cảnh và tương tác kích hoạt."""

    def __init__(self, win):
        q_parent = win if isinstance(win, QObject) else None
        super().__init__(q_parent)
        self.win = win
        self.tray_icon = QSystemTrayIcon(q_parent)

        self.icon = QIcon(APP_ICON) if APP_ICON and os.path.exists(APP_ICON) else QIcon()
        if not self.icon.isNull():
            self.tray_icon.setIcon(self.icon)

        self.menu = QMenu()
        self._build_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.setToolTip(tr("app.title"))

        self.tray_icon.activated.connect(self._on_activated)
        self.tray_icon.show()
        self._has_notified = False

    def _build_menu(self):
        """Khởi tạo menu ngữ cảnh chuột phải."""
        self.menu.clear()

        self.act_app = self.menu.addAction(tr("tray.launch_app"))
        self.act_app.triggered.connect(self.win.on_launch_app_clicked)

        self.act_ide = self.menu.addAction(tr("tray.launch_ide"))
        self.act_ide.triggered.connect(self.win.on_launch_ide_clicked)

        self.menu.addSeparator()

        self.act_open = self.menu.addAction(tr("tray.open_launcher"))
        self.act_open.triggered.connect(self.win.activate_window)

        self.act_about = self.menu.addAction(tr("tray.about"))
        self.act_about.triggered.connect(self.win.show_about)

        self.menu.addSeparator()

        self.act_exit = self.menu.addAction(tr("tray.exit"))
        self.act_exit.triggered.connect(self.win.exit_app)

    def retranslate_ui(self):
        """Cập nhật lại nhãn menu khi chuyển đổi ngôn ngữ giao diện."""
        self.tray_icon.setToolTip(tr("app.title"))
        self._build_menu()

    def _on_activated(self, reason):
        """Xử lý sự kiện click trái hoặc nhấp đúp vào icon khay hệ thống."""
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick
        ):
            self.win.activate_window()

    def notify_minimized(self):
        """Hiển thị thông báo khi thu nhỏ vào khay hệ thống (tối đa 1 lần mỗi phiên để chống spam)."""
        if getattr(self, "_has_notified", False):
            return
        self._has_notified = True
        settings = getattr(self.win, "data", {}).get("settings", {})
        if settings.get("hide_on_launch") == "always" and settings.get("close_action") == "hide":
            return
        if self.tray_icon.isVisible() and QSystemTrayIcon.supportsMessages():
            self.tray_icon.showMessage(
                tr("tray.minimized_title"),
                tr("tray.minimized_msg"),
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )

class TraySettingsGroup(QGroupBox):
    """Nhóm cấu hình hành vi Cửa sổ & Khay hệ thống trong Settings."""

    def __init__(self, win, parent=None):
        super().__init__(tr("settings.tray_group"), parent)
        self.win = win
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.combo_hide = QComboBox()
        self.row_hide = SettingRow(tr("settings.hide_on_launch_label"), self.combo_hide, tr("settings.hide_on_launch_desc"))
        layout.addWidget(self.row_hide)

        self.combo_close = QComboBox()
        self.row_close = SettingRow(tr("settings.close_action_label"), self.combo_close, tr("settings.close_action_desc"))
        layout.addWidget(self.row_close)

        self.populate()

    def populate(self):
        """Nạp dữ liệu lựa chọn từ cấu hình."""
        self.combo_hide.blockSignals(True)
        self.combo_hide.clear()
        curr_hide = self.win.data.get("settings", {}).get("hide_on_launch", "ask")
        for val, key in [("ask", "settings.opt_ask"), ("always", "settings.opt_hide_always"), ("never", "settings.opt_hide_never")]:
            self.combo_hide.addItem(tr(key), val)
            if val == curr_hide:
                self.combo_hide.setCurrentIndex(self.combo_hide.count() - 1)
        self.combo_hide.blockSignals(False)

        self.combo_close.blockSignals(True)
        self.combo_close.clear()
        curr_close = self.win.data.get("settings", {}).get("close_action", "ask")
        for val, key in [("ask", "settings.opt_ask"), ("hide", "settings.opt_close_hide"), ("exit", "settings.opt_close_exit")]:
            self.combo_close.addItem(tr(key), val)
            if val == curr_close:
                self.combo_close.setCurrentIndex(self.combo_close.count() - 1)
        self.combo_close.blockSignals(False)

    def save(self):
        """Lưu lựa chọn vào đối tượng win.data."""
        h = self.combo_hide.currentData()
        c = self.combo_close.currentData()
        if h:
            self.win.data.setdefault("settings", {})["hide_on_launch"] = h
        if c:
            self.win.data.setdefault("settings", {})["close_action"] = c

    def retranslate_ui(self):
        """Cập nhật ngôn ngữ cho nhóm Cài đặt Khay."""
        self.setTitle(tr("settings.tray_group"))
        self.row_hide.lbl_main.setText(tr("settings.hide_on_launch_label"))
        if hasattr(self.row_hide, "lbl_desc"):
            self.row_hide.lbl_desc.setText(tr("settings.hide_on_launch_desc"))
        self.row_close.lbl_main.setText(tr("settings.close_action_label"))
        if hasattr(self.row_close, "lbl_desc"):
            self.row_close.lbl_desc.setText(tr("settings.close_action_desc"))
        self.populate()

def handle_hide_on_launch(win):
    """Điều phối hành vi ẩn Launcher khi khởi chạy ứng dụng/IDE."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return
    choice = win.data.get("settings", {}).get("hide_on_launch", "ask")
    if choice == "always":
        hide_window_to_tray(win)
        win.tray.notify_minimized()
    elif choice == "never":
        pass
    else:
        should_hide, remember = ask_hide_on_launch_prompt(win)
        if remember:
            from launcher_storage import save_data
            win.data.setdefault("settings", {})["hide_on_launch"] = "always" if should_hide else "never"
            save_data(win.data)
        if should_hide:
            hide_window_to_tray(win)
            win.tray.notify_minimized()

def handle_close_event(win, event):
    """Điều phối hành vi khi người dùng bấm nút [X] đóng cửa sổ Launcher."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        clean_exit(win, event)
        return
    action = win.data.get("settings", {}).get("close_action", "ask")
    if action == "hide":
        event.ignore()
        hide_window_to_tray(win)
        win.tray.notify_minimized()
        return
    if action == "exit":
        clean_exit(win, event)
        return

    chosen, remember = ask_close_action_prompt(win)
    if chosen == "hide":
        if remember:
            from launcher_storage import save_data
            win.data.setdefault("settings", {})["close_action"] = "hide"
            save_data(win.data)
        event.ignore()
        hide_window_to_tray(win)
        win.tray.notify_minimized()
    elif chosen == "exit":
        if remember:
            from launcher_storage import save_data
            win.data.setdefault("settings", {})["close_action"] = "exit"
            save_data(win.data)
        clean_exit(win, event)
    else:
        event.ignore()

def clean_exit(win, event=None):
    """Dọn dẹp tài nguyên và thoát ứng dụng an toàn."""
    capture_window_state(win, persist=True)
    if hasattr(win, "tray") and hasattr(win.tray, "tray_icon"):
        win.tray.tray_icon.hide()
    win.monitor_timer.stop()
    win.auto_quota_timer.stop()
    from launcher_quota_runner import stop_spinner_animation
    from launcher_proxy import stop_all_launched_apps, stop_proxy
    stop_spinner_animation(win)
    if event:
        event.accept()
    else:
        stop_all_launched_apps()
        stop_proxy()
        QApplication.quit()
