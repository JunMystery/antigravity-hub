# -*- coding: utf-8 -*-
"""
Module thanh điều hướng bên (Sidebar Navigation) cho Antigravity Launcher.
Phát tín hiệu view_changed(str) khi người dùng chọn các trang và hỗ trợ chuyển Theme/Ngôn ngữ.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon

from launcher_paths import (
    ASSET_PNG, ASSET_IDE_PNG, ASSET_LOCKUP_DARK_PNG, ASSET_LOCKUP_LIGHT_PNG
)
from launcher_i18n import tr, SUPPORTED_LANGUAGES, get_current_language
from launcher_theme import THEME_MODES, get_active_theme, get_theme_mode
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header: Google Antigravity Lockup không viền, tự đổi file Dark/Light theo theme
        self.logo_lockup = QLabel()
        self.logo_lockup.setObjectName("sidebar_logo_lockup")
        self.logo_lockup.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_lockup.setFixedHeight(38)
        self.logo_lockup.setStyleSheet(
            "QLabel#sidebar_logo_lockup { background: transparent; border: none; padding: 2px 4px; }"
        )
        layout.addWidget(self.logo_lockup)

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
        sep.setObjectName("sidebar_sep")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        self.buttons = {}
        for vid in ("dashboard", "accounts", "model_rules", "logs", "settings"):
            btn = NavButton("", tr(f"nav.{vid}"), vid, self)
            btn.clicked.connect(lambda _, v=vid: self._on_btn_clicked(v))
            layout.addWidget(btn)
            self.buttons[vid] = btn

        layout.addStretch(1)

        self.lbl_theme = QLabel(tr("theme.label"))
        self.lbl_theme.setObjectName("sidebar_caption")
        layout.addWidget(self.lbl_theme)

        self.combo_theme = QComboBox()
        self._populate_theme_options()
        on_theme = getattr(self.win, "on_theme_changed", None)
        if callable(on_theme):
            self.combo_theme.currentIndexChanged.connect(on_theme)
        layout.addWidget(self.combo_theme)

        lbl_lang = QLabel("Language / Ngôn ngữ")
        lbl_lang.setObjectName("sidebar_caption")
        layout.addWidget(lbl_lang)

        self.combo_lang = QComboBox()
        for code, name in SUPPORTED_LANGUAGES:
            self.combo_lang.addItem(name, code)
        idx = self.combo_lang.findData(get_current_language())
        if idx >= 0:
            self.combo_lang.setCurrentIndex(idx)
        on_lang = getattr(self.win, "on_language_changed", None)
        if callable(on_lang):
            self.combo_lang.currentIndexChanged.connect(on_lang)
        layout.addWidget(self.combo_lang)

        layout.addSpacing(4)
        self.lbl_footer = QLabel("v0.2.3 • JunMystery")
        self.lbl_footer.setObjectName("sidebar_footer")
        self.lbl_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_footer)

        self.update_theme()
        self.set_active_view("dashboard")

    def _populate_theme_options(self):
        cur_mode = get_theme_mode()
        self.combo_theme.blockSignals(True)
        try:
            self.combo_theme.clear()
            for mode in THEME_MODES:
                self.combo_theme.addItem(tr(f"theme.{mode}"), mode)
            idx = self.combo_theme.findData(cur_mode)
            if idx >= 0:
                self.combo_theme.setCurrentIndex(idx)
        finally:
            self.combo_theme.blockSignals(False)

    def update_theme(self):
        """Nạp logo lockup Dark/Light tương ứng và đồng bộ trạng thái combo Theme."""
        asset_path = ASSET_LOCKUP_LIGHT_PNG if get_active_theme() == "light" else ASSET_LOCKUP_DARK_PNG
        if os.path.exists(asset_path):
            pix = QPixmap(asset_path).scaled(
                158, 30, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.logo_lockup.setText("")
            self.logo_lockup.setPixmap(pix)
        else:
            self.logo_lockup.setPixmap(QPixmap())
            self.logo_lockup.setText("Antigravity Hub")

        idx = self.combo_theme.findData(get_theme_mode())
        if idx >= 0 and self.combo_theme.currentIndex() != idx:
            self.combo_theme.blockSignals(True)
            self.combo_theme.setCurrentIndex(idx)
            self.combo_theme.blockSignals(False)

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
        self.lbl_theme.setText(tr("theme.label"))
        self._populate_theme_options()
        self.btn_launch_app.setToolTip(tr("btn.launch_app"))
        self.btn_launch_ide.setToolTip(tr("btn.launch_ide"))
        for vid in ("dashboard", "accounts", "model_rules", "logs", "settings"):
            if vid in self.buttons:
                self.buttons[vid].setText(tr(f"nav.{vid}"))
