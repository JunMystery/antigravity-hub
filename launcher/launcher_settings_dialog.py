# -*- coding: utf-8 -*-
"""
Hộp thoại Cài đặt (Settings Dialog) cho Antigravity Launcher.
Quản lý cấu hình đường dẫn Antigravity App (2.0), Antigravity IDE và Desktop Shortcut.
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt

from launcher_i18n import tr
from launcher_storage import (
    find_app_binary, find_ide_binary, save_data, get_app_binary, get_ide_binary
)
from launcher_shortcut import create_desktop_shortcut

class LauncherSettingsDialog(QDialog):
    """Hộp thoại cấu hình đường dẫn và tiện ích hệ thống."""

    def __init__(self, win, parent=None):
        super().__init__(parent or win)
        self.win = win
        self.setWindowTitle(tr("settings.title"))
        self.resize(580, 300)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 16, 18, 16)

        # Nhóm cài đặt đường dẫn
        grp = QGroupBox(tr("settings.paths_group"))
        grp_layout = QVBoxLayout(grp)
        grp_layout.setSpacing(10)

        # 1. Antigravity App (Agentic 2.0)
        lbl_app = QLabel(f"<b>{tr('settings.app_path')}:</b>")
        grp_layout.addWidget(lbl_app)
        row_app = QHBoxLayout()
        row_app.setSpacing(8)
        self.txt_app = QLineEdit(get_app_binary(self.win.data))
        self.txt_app.setMinimumHeight(32)
        row_app.addWidget(self.txt_app, 1)

        btn_browse_app = QPushButton(tr("settings.browse"))
        btn_browse_app.setMinimumHeight(32)
        btn_browse_app.clicked.connect(self._browse_app)
        row_app.addWidget(btn_browse_app)

        btn_detect_app = QPushButton(tr("settings.detect"))
        btn_detect_app.setMinimumHeight(32)
        btn_detect_app.clicked.connect(self._detect_app)
        row_app.addWidget(btn_detect_app)
        grp_layout.addLayout(row_app)

        # 2. Antigravity IDE (Code Editor)
        lbl_ide = QLabel(f"<b>{tr('settings.ide_path')}:</b>")
        grp_layout.addWidget(lbl_ide)
        row_ide = QHBoxLayout()
        row_ide.setSpacing(8)
        self.txt_ide = QLineEdit(get_ide_binary(self.win.data))
        self.txt_ide.setMinimumHeight(32)
        row_ide.addWidget(self.txt_ide, 1)

        btn_browse_ide = QPushButton(tr("settings.browse"))
        btn_browse_ide.setMinimumHeight(32)
        btn_browse_ide.clicked.connect(self._browse_ide)
        row_ide.addWidget(btn_browse_ide)

        btn_detect_ide = QPushButton(tr("settings.detect"))
        btn_detect_ide.setMinimumHeight(32)
        btn_detect_ide.clicked.connect(self._detect_ide)
        row_ide.addWidget(btn_detect_ide)
        grp_layout.addLayout(row_ide)
        layout.addWidget(grp)

        # 3. Desktop Shortcut row
        row_sc = QHBoxLayout()
        btn_shortcut = QPushButton(tr("settings.create_shortcut"))
        btn_shortcut.clicked.connect(self._create_shortcut)
        row_sc.addWidget(btn_shortcut)
        self.lbl_sc_status = QLabel()
        row_sc.addWidget(self.lbl_sc_status, 1)
        layout.addLayout(row_sc)

        layout.addStretch(1)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch(1)

        btn_cancel = QPushButton(tr("btn.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton(tr("btn.save"))
        btn_save.setStyleSheet("background-color: #2980b9; color: #ffffff; font-weight: bold;")
        btn_save.clicked.connect(self._save_settings)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

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
        if ok:
            self.lbl_sc_status.setText(f"<span style='color:#a6e3a1;'>{tr('settings.shortcut_success')}</span>")
        else:
            self.lbl_sc_status.setText(f"<span style='color:#f38ba8;'>{tr('settings.shortcut_failed')}</span>")

    def _save_settings(self):
        self.win.data.setdefault("settings", {})
        self.win.data["settings"]["app_binary"] = self.txt_app.text().strip()
        self.win.data["settings"]["ide_binary"] = self.txt_ide.text().strip()
        save_data(self.win.data)
        self.accept()
