# -*- coding: utf-8 -*-
"""
Module thanh điều hướng bên (Sidebar Navigation) cho Antigravity Launcher.
Phát tín hiệu view_changed(str) khi người dùng chọn Dashboard, Accounts hoặc Settings.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon

from launcher_paths import ASSET_PNG, ASSET_IDE_PNG, ASSET_LOCKUP_PNG
from launcher_i18n import tr, SUPPORTED_LANGUAGES, get_current_language
from launcher_widget import NavButton


def _make_launch_btn(obj_name: str, label: str, icon_path: str, tooltip: str, slot) -> QPushButton:
    btn = QPushButton(label)
    btn.setObjectName(obj_name)
    btn.setProperty("keep_short_label", True)
    btn.setFixedHeight(34)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip(tooltip)
    if icon_path and os.path.exists(icon_path):
        btn.setIcon(QIcon(icon_path))
        btn.setIconSize(QSize(18, 18))
    if slot:
        btn.clicked.connect(slot)
    return btn


class SidebarNav(QWidget):
    """Thanh điều hướng Sidebar cố định bên trái cửa sổ."""
    view_changed = pyqtSignal(str)

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
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header: Google Antigravity Lockup với viền sáng tách biệt nền tối
        self.logo_lockup = QLabel()
        self.logo_lockup.setObjectName("sidebar_logo_lockup")
        self.logo_lockup.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_lockup.setFixedHeight(40)
        self.logo_lockup.setStyleSheet(
            "QLabel#sidebar_logo_lockup { background-color: #1e1e2e; border: 1px solid #6c7086; "
            "border-radius: 8px; padding: 4px 6px; }"
        )
        if os.path.exists(ASSET_LOCKUP_PNG):
            pix = QPixmap(ASSET_LOCKUP_PNG).scaled(
                150, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.logo_lockup.setPixmap(pix)
        else:
            self.logo_lockup.setText("Antigravity Hub")
            self.logo_lockup.setStyleSheet(
                "QLabel#sidebar_logo_lockup { background-color: #1e1e2e; border: 1px solid #6c7086; "
                "border-radius: 8px; padding: 4px 6px; color: #cdd6f4; font-size: 13px; font-weight: bold; }"
            )
        layout.addWidget(self.logo_lockup)

        # Quick launch buttons (App & IDE) with compact labels under header
        launch_row = QHBoxLayout()
        launch_row.setContentsMargins(0, 2, 0, 2)
        launch_row.setSpacing(6)
        self.btn_launch_app = _make_launch_btn(
            "btn_launch_app", "App", ASSET_PNG, tr("btn.launch_app"),
            getattr(self.win, "on_launch_app_clicked", None)
        )
        self.btn_launch_ide = _make_launch_btn(
            "btn_launch_ide", "IDE", ASSET_IDE_PNG, tr("btn.launch_ide"),
            getattr(self.win, "on_launch_ide_clicked", None)
        )
        launch_row.addWidget(self.btn_launch_app, 1)
        launch_row.addWidget(self.btn_launch_ide, 1)
        layout.addLayout(launch_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #313244; border: none; border-top: 1px solid #313244; max-height: 1px;")
        layout.addWidget(sep)

        # Navigation buttons
        self.buttons = {}
        nav_items = [
            ("dashboard", tr("nav.dashboard")),
            ("accounts", tr("nav.accounts")),
            ("model_rules", tr("nav.model_rules")),
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

        layout.addSpacing(6)
        self.lbl_footer = QLabel("v0.2.2 • JunMystery")
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
        self.btn_launch_app.setToolTip(tr("btn.launch_app"))
        self.btn_launch_ide.setToolTip(tr("btn.launch_ide"))
        for vid in ("dashboard", "accounts", "model_rules", "logs", "settings"):
            if vid in self.buttons:
                self.buttons[vid].setText(tr(f"nav.{vid}"))
