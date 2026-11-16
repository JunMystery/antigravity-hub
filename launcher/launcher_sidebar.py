# -*- coding: utf-8 -*-
"""
Module thanh điều hướng bên (Sidebar Navigation) cho Antigravity Launcher.
Phát tín hiệu view_changed(str) khi người dùng chọn Dashboard, Accounts hoặc Settings.
"""

import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap

from launcher_storage import APP_ICON
from launcher_i18n import tr, SUPPORTED_LANGUAGES, get_current_language
from launcher_widget import NavButton

class SidebarNav(QWidget):
    """Thanh điều hướng Sidebar cố định bên trái cửa sổ."""
    view_changed = pyqtSignal(str)

    NAV_ICONS = {
        "dashboard": "⊞",
        "accounts": "👤",
        "logs": "≡",
        "settings": "⚙"
    }

    def __init__(self, win, parent=None):
        super().__init__(parent)
        self.win = win
        self.setFixedWidth(190)
        self.setObjectName("sidebar_nav")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.setStyleSheet(
            "QWidget#sidebar_nav { background-color: #181825; border-right: 1px solid #313244; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(8)

        # Header: Logo + App title
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        self.icon_lbl = QLabel()
        if os.path.exists(APP_ICON):
            pix = QPixmap(APP_ICON).scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.icon_lbl.setPixmap(pix)
        hdr.addWidget(self.icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.title_lbl = QLabel("Antigravity")
        self.title_lbl.setStyleSheet("color: #cdd6f4; font-size: 14px; font-weight: bold;")
        self.sub_lbl = QLabel("Launcher")
        self.sub_lbl.setStyleSheet("color: #6c7086; font-size: 11px;")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.sub_lbl)
        hdr.addLayout(title_box, 1)
        layout.addLayout(hdr)

        layout.addSpacing(16)

        # Navigation buttons
        self.buttons = {}
        nav_items = [
            ("dashboard", tr("nav.dashboard")),
            ("accounts", tr("nav.accounts")),
            ("logs", tr("nav.logs")),
            ("settings", tr("nav.settings"))
        ]

        for vid, label in nav_items:
            btn = NavButton("", label, vid, self)
            btn.clicked.connect(lambda _, v=vid: self._on_btn_clicked(v))
            layout.addWidget(btn)
            self.buttons[vid] = btn

        layout.addStretch(1)

        # Language dropdown at footer
        lbl_lang = QLabel("Language / Ngôn ngữ")
        lbl_lang.setStyleSheet("color: #6c7086; font-size: 10px;")
        layout.addWidget(lbl_lang)

        self.combo_lang = QComboBox()
        for code, name in SUPPORTED_LANGUAGES:
            self.combo_lang.addItem(name, code)
        cur_lang = get_current_language()
        idx = self.combo_lang.findData(cur_lang)
        if idx >= 0:
            self.combo_lang.setCurrentIndex(idx)
        self.combo_lang.currentIndexChanged.connect(self.win.on_language_changed)
        layout.addWidget(self.combo_lang)

        layout.addSpacing(10)
        self.lbl_footer = QLabel("v0.1.1 • JunMystery")
        self.lbl_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_footer.setStyleSheet("color: #6c7086; font-size: 10px; font-weight: 500;")
        layout.addWidget(self.lbl_footer)

        self.set_active_view("dashboard")

    def _on_btn_clicked(self, view_id: str):
        self.set_active_view(view_id)
        self.view_changed.emit(view_id)

    def set_active_view(self, view_id: str):
        for vid, btn in self.buttons.items():
            btn.set_active(vid == view_id)

    def retranslate_ui(self):
        cur_lang = get_current_language()
        idx = self.combo_lang.findData(cur_lang)
        if idx >= 0 and self.combo_lang.currentIndex() != idx:
            self.combo_lang.blockSignals(True)
            self.combo_lang.setCurrentIndex(idx)
            self.combo_lang.blockSignals(False)
        for vid in ("dashboard", "accounts", "logs", "settings"):
            if vid in self.buttons:
                self.buttons[vid].setText(tr(f"nav.{vid}"))
