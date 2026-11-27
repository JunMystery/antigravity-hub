# -*- coding: utf-8 -*-
"""
View Cài đặt (Settings View) cho Antigravity Launcher.
Quản lý cấu hình đường dẫn ứng dụng/IDE, tạo shortcut desktop,
và quản lý nhật ký: cấu hình lưu trữ (7/30/90 ngày) cùng nút Xóa Log.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QGroupBox, QMessageBox, QComboBox, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices

from launcher_i18n import tr
from launcher_theme import set_semantic_text, refresh_semantic_label
from launcher_storage import (
    find_app_binary, find_ide_binary, save_data, get_app_binary, get_ide_binary,
    CONFIG_DIR
)
from launcher_shortcut import create_desktop_shortcut
from launcher_log_manager import (
    get_retention_days, set_retention_days, clear_log, prune_logs
)
from launcher_widget import SettingRow
from launcher_tray import TraySettingsGroup
from launcher_backup import BackupSettingsGroup


class SettingsView(QWidget):
    """View cấu hình hệ thống, đường dẫn thực thi và nhật ký."""

    def __init__(self, win, parent=None):
        super().__init__(parent)
        self.win = win
        self.setObjectName("settings_view")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_content.setObjectName("settings_scroll_content")
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(16, 14, 16, 10)
        layout.setSpacing(12)

        # 1. Nhóm đường dẫn thực thi
        self.grp_paths = QGroupBox(tr("settings.paths_group"))
        grp_paths_layout = QVBoxLayout(self.grp_paths)
        grp_paths_layout.setContentsMargins(12, 14, 12, 12)
        grp_paths_layout.setSpacing(8)

        self.lbl_app, self.txt_app, self.btn_browse_app, self.btn_detect_app = self._build_path_row(
            grp_paths_layout, "settings.app_path", get_app_binary(self.win.data), self._browse_app, self._detect_app
        )

        self.lbl_ide, self.txt_ide, self.btn_browse_ide, self.btn_detect_ide = self._build_path_row(
            grp_paths_layout, "settings.ide_path", get_ide_binary(self.win.data), self._browse_ide, self._detect_ide
        )
        layout.addWidget(self.grp_paths)

        # 2. Nhóm quản lý nhật ký (Log Management & Retention)
        self.grp_logs = QGroupBox(tr("settings.logs_group"))
        grp_logs_layout = QVBoxLayout(self.grp_logs)
        grp_logs_layout.setSpacing(10)

        self.combo_retention = QComboBox()
        self._populate_retention_options()
        self.combo_retention.currentIndexChanged.connect(self._on_retention_changed)

        self.row_retention = SettingRow(tr("settings.retention_label"), self.combo_retention, tr("settings.retention_desc"))
        grp_logs_layout.addWidget(self.row_retention)

        row_clear = QHBoxLayout()
        self.btn_clear_log = QPushButton(tr("btn.clear_log"))
        self.btn_clear_log.setObjectName("btn_danger")
        self.btn_clear_log.clicked.connect(self._on_clear_log)
        row_clear.addWidget(self.btn_clear_log)

        self.lbl_log_status = QLabel()
        row_clear.addWidget(self.lbl_log_status, 1)
        grp_logs_layout.addLayout(row_clear)
        layout.addWidget(self.grp_logs)

        # 3. Nhóm Cửa sổ & Khay hệ thống
        self.grp_tray = TraySettingsGroup(self.win, self)
        layout.addWidget(self.grp_tray)

        # 4. Nhóm Sao lưu & Phục hồi
        self.grp_backup = BackupSettingsGroup(self.win, self)
        layout.addWidget(self.grp_backup)

        # 5. Desktop Shortcut & Thư mục Dữ liệu (Data Directory)
        row_sc = QHBoxLayout()
        row_sc.setSpacing(8)
        self.btn_shortcut = QPushButton(tr("settings.create_shortcut"))
        self.btn_shortcut.clicked.connect(self._create_shortcut)
        row_sc.addWidget(self.btn_shortcut)

        self.btn_install_cert = QPushButton(tr("settings.install_cert"))
        self.btn_install_cert.clicked.connect(self._install_cert)
        row_sc.addWidget(self.btn_install_cert)

        self.btn_open_data = QPushButton(tr("settings.open_data_dir"))
        self.btn_open_data.clicked.connect(self._open_data_dir)
        row_sc.addWidget(self.btn_open_data)

        self.lbl_sc_status = QLabel()
        row_sc.addWidget(self.lbl_sc_status, 1)
        layout.addLayout(row_sc)

        layout.addStretch(1)
        self.scroll_area.setWidget(scroll_content)
        outer_layout.addWidget(self.scroll_area, 1)

        # 6. Nút Lưu Cài đặt (ghim cố định ở chân view)
        footer = QHBoxLayout()
        footer.setContentsMargins(16, 8, 16, 14)
        self.btn_save = QPushButton(tr("btn.save"))
        self.btn_save.setObjectName("btn_primary")
        self.btn_save.setFixedHeight(32)
        self.btn_save.clicked.connect(self._save_settings)
        footer.addWidget(self.btn_save)
        outer_layout.addLayout(footer)

    def _set_status_msg(self, label, text: str, ok: bool):
        set_semantic_text(label, text, "green" if ok else "red")

    def refresh_theme(self):
        """Đồng bộ màu các nhãn trạng thái trên SettingsView theo Theme."""
        refresh_semantic_label(self.lbl_log_status)
        refresh_semantic_label(self.lbl_sc_status)
        if hasattr(self, "grp_backup") and hasattr(self.grp_backup, "refresh_theme"):
            self.grp_backup.refresh_theme()

    def _build_path_row(self, parent_layout, label_key, initial_val, on_browse, on_detect):
        lbl = QLabel(f"<b>{tr(label_key)}:</b>")
        parent_layout.addWidget(lbl)
        row = QHBoxLayout()
        row.setSpacing(8)
        txt, btn_b, btn_d = QLineEdit(initial_val), QPushButton(tr("settings.browse")), QPushButton(tr("settings.detect"))
        btn_b.clicked.connect(on_browse)
        btn_d.clicked.connect(on_detect)
        for w in (txt, btn_b, btn_d):
            w.setMinimumHeight(32)
            w.setSizePolicy(w.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Fixed)
        row.addWidget(txt, 1)
        row.addWidget(btn_b)
        row.addWidget(btn_d)
        parent_layout.addLayout(row)
        return lbl, txt, btn_b, btn_d

    def _browse_app(self):
        f, _ = QFileDialog.getOpenFileName(self, tr("settings.browse_app_title"), self.txt_app.text().strip())
        if f:
            self.txt_app.setText(f)

    def _browse_ide(self):
        f, _ = QFileDialog.getOpenFileName(self, tr("settings.browse_ide_title"), self.txt_ide.text().strip())
        if f:
            self.txt_ide.setText(f)

    def _detect_app(self):
        p = find_app_binary()
        if p and os.path.exists(p):
            self.txt_app.setText(p)
        else:
            QMessageBox.information(self, tr("settings.detect"), tr("settings.not_found_app"))

    def _detect_ide(self):
        p = find_ide_binary()
        if p and os.path.exists(p):
            self.txt_ide.setText(p)
        else:
            QMessageBox.information(self, tr("settings.detect"), tr("settings.not_found_ide"))

    def _create_shortcut(self):
        ok = create_desktop_shortcut()
        self._set_status_msg(self.lbl_sc_status, tr("settings.shortcut_success" if ok else "settings.shortcut_failed"), ok)

    def _install_cert(self):
        try:
            from launcher_cert import install_root_ca, is_root_ca_installed
            ok = install_root_ca() or is_root_ca_installed()
            self._set_status_msg(self.lbl_sc_status, tr("settings.cert_success" if ok else "settings.cert_failed"), bool(ok))
        except Exception as e:
            self._set_status_msg(self.lbl_sc_status, str(e), False)

    def _populate_retention_options(self):
        """Nạp danh sách các mốc thời gian lưu trữ theo ngôn ngữ hiện hành."""
        cur_days = None
        if hasattr(self, "win") and hasattr(self.win, "data") and isinstance(self.win.data, dict):
            cur_days = self.win.data.get("settings", {}).get("log_retention_days")
        if not cur_days:
            cur_days = get_retention_days()
        self.combo_retention.blockSignals(True)
        self.combo_retention.clear()
        self.combo_retention.addItem(tr("settings.retention_7d"), 7)
        self.combo_retention.addItem(tr("settings.retention_30d"), 30)
        self.combo_retention.addItem(tr("settings.retention_90d"), 90)
        idx = self.combo_retention.findData(cur_days)
        if idx >= 0:
            self.combo_retention.setCurrentIndex(idx)
        self.combo_retention.blockSignals(False)

    def _open_data_dir(self):
        """Mở thư mục cấu hình và dữ liệu của launcher trên trình duyệt tệp tin hệ thống."""
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(CONFIG_DIR))
        except Exception as e:
            self._set_status_msg(self.lbl_sc_status, tr("settings.open_data_failed", error=str(e)), False)

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "grp_tray"):
            self.grp_tray.populate()

    def retranslate_ui(self):
        """Cập nhật giao diện khi đổi ngôn ngữ động."""
        if hasattr(self, "grp_paths"):
            self.grp_paths.setTitle(tr("settings.paths_group"))
        if hasattr(self, "lbl_app"):
            self.lbl_app.setText(f"<b>{tr('settings.app_path')}:</b>")
        if hasattr(self, "lbl_ide"):
            self.lbl_ide.setText(f"<b>{tr('settings.ide_path')}:</b>")
        if hasattr(self, "btn_browse_app"):
            self.btn_browse_app.setText(tr("settings.browse"))
        if hasattr(self, "btn_detect_app"):
            self.btn_detect_app.setText(tr("settings.detect"))
        if hasattr(self, "btn_browse_ide"):
            self.btn_browse_ide.setText(tr("settings.browse"))
        if hasattr(self, "btn_detect_ide"):
            self.btn_detect_ide.setText(tr("settings.detect"))
        if hasattr(self, "grp_logs"):
            self.grp_logs.setTitle(tr("settings.logs_group"))
        if hasattr(self, "combo_retention"):
            self._populate_retention_options()
        if hasattr(self, "row_retention"):
            self.row_retention.lbl_main.setText(tr("settings.retention_label"))
            if hasattr(self.row_retention, "lbl_desc"):
                self.row_retention.lbl_desc.setText(tr("settings.retention_desc"))
        if hasattr(self, "btn_clear_log"):
            self.btn_clear_log.setText(tr("btn.clear_log"))
        if hasattr(self, "btn_shortcut"):
            self.btn_shortcut.setText(tr("settings.create_shortcut"))
        if hasattr(self, "btn_install_cert"):
            self.btn_install_cert.setText(tr("settings.install_cert"))
        if hasattr(self, "btn_open_data"):
            self.btn_open_data.setText(tr("settings.open_data_dir"))
        if hasattr(self, "grp_tray"):
            self.grp_tray.retranslate_ui()
        if hasattr(self, "grp_backup"):
            self.grp_backup.retranslate_ui()
        if hasattr(self, "btn_save"):
            self.btn_save.setText(tr("btn.save"))

    def _on_retention_changed(self, idx):
        days = self.combo_retention.itemData(idx)
        if days:
            set_retention_days(days)
            if hasattr(self, "win") and hasattr(self.win, "data") and isinstance(self.win.data, dict):
                self.win.data.setdefault("settings", {})["log_retention_days"] = int(days)
                save_data(self.win.data)
            pruned = prune_logs(days)
            self._set_status_msg(self.lbl_log_status, tr("settings.retention_updated", days=days, pruned=pruned), True)

    def _on_clear_log(self):
        ok = clear_log()
        if ok:
            self._set_status_msg(self.lbl_log_status, tr("settings.log_cleared"), True)
            if hasattr(self.win, "view_dashboard") and hasattr(self.win.view_dashboard, "table_feed"):
                self.win.view_dashboard.table_feed.setRowCount(0)
        else:
            self._set_status_msg(self.lbl_log_status, tr("settings.log_clear_failed"), False)

    def _save_settings(self):
        self.win.data.setdefault("settings", {})
        self.win.data["settings"]["app_binary"] = self.txt_app.text().strip()
        self.win.data["settings"]["ide_binary"] = self.txt_ide.text().strip()
        days = self.combo_retention.currentData()
        if days:
            self.win.data["settings"]["log_retention_days"] = int(days)
            set_retention_days(days)
        if hasattr(self, "grp_tray"):
            self.grp_tray.save()
        save_data(self.win.data)
        QMessageBox.information(self, tr("settings.title"), tr("settings.saved_msg"))
