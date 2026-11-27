# -*- coding: utf-8 -*-
"""
Module hiển thị các hộp thoại xác nhận hành vi (Prompt Dialogs) cho Antigravity Launcher:
- Hỏi ẩn launcher khi chạy ứng dụng (kèm checkbox ghi nhớ)
- Hỏi hành vi khi đóng cửa sổ [X] (kèm checkbox ghi nhớ)
- Hộp thoại Giới thiệu (About Dialog)
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QIcon

from launcher_i18n import tr
from launcher_paths import APP_ICON

def ask_hide_on_launch_prompt(parent=None):
    """
    Hiển thị hộp thoại hỏi có muốn ẩn Launcher khi chạy ứng dụng không.
    Trả về: (should_hide: bool, remember: bool)
    """
    q_parent = parent if isinstance(parent, QWidget) else None
    dlg = QDialog(q_parent)
    dlg.setWindowTitle(tr("dialog.hide_on_launch_title"))
    if APP_ICON and os.path.exists(APP_ICON):
        dlg.setWindowIcon(QIcon(APP_ICON))
    dlg.setModal(True)
    dlg.setMinimumWidth(380)

    layout = QVBoxLayout(dlg)
    layout.setSpacing(14)
    layout.setContentsMargins(18, 16, 18, 16)

    lbl = QLabel(tr("dialog.hide_on_launch_msg"))
    lbl.setWordWrap(True)
    layout.addWidget(lbl)

    chk_remember = QCheckBox(tr("dialog.prompt_remember"))
    layout.addWidget(chk_remember)

    btn_row = QHBoxLayout()
    btn_row.setSpacing(10)
    btn_row.addStretch(1)

    btn_keep = QPushButton(tr("dialog.btn_keep_window"))
    btn_hide = QPushButton(tr("dialog.btn_hide_tray"))
    btn_hide.setObjectName("btn_primary")

    btn_row.addWidget(btn_keep)
    btn_row.addWidget(btn_hide)
    layout.addLayout(btn_row)

    res = {"hide": False, "remember": False}

    def on_hide():
        res["hide"] = True
        res["remember"] = chk_remember.isChecked()
        dlg.accept()

    def on_keep():
        res["hide"] = False
        res["remember"] = chk_remember.isChecked()
        dlg.reject()

    btn_hide.clicked.connect(on_hide)
    btn_keep.clicked.connect(on_keep)

    dlg.exec()
    return res["hide"], res["remember"]

def ask_close_action_prompt(parent=None):
    """
    Hiển thị hộp thoại hỏi hành vi khi bấm nút [X] đóng cửa sổ.
    Trả về: (action: str, remember: bool) -> action: 'hide' | 'exit' | None
    """
    q_parent = parent if isinstance(parent, QWidget) else None
    dlg = QDialog(q_parent)
    dlg.setWindowTitle(tr("dialog.close_title"))
    if APP_ICON and os.path.exists(APP_ICON):
        dlg.setWindowIcon(QIcon(APP_ICON))
    dlg.setModal(True)
    dlg.setMinimumWidth(380)

    layout = QVBoxLayout(dlg)
    layout.setSpacing(14)
    layout.setContentsMargins(18, 16, 18, 16)

    lbl = QLabel(tr("dialog.close_msg"))
    lbl.setWordWrap(True)
    layout.addWidget(lbl)

    chk_remember = QCheckBox(tr("dialog.prompt_remember"))
    layout.addWidget(chk_remember)

    btn_row = QHBoxLayout()
    btn_row.setSpacing(10)

    btn_cancel = QPushButton(tr("btn.cancel"))
    btn_exit = QPushButton(tr("dialog.btn_exit_app"))
    btn_exit.setObjectName("btn_danger")
    btn_hide = QPushButton(tr("dialog.btn_hide_tray"))
    btn_hide.setObjectName("btn_primary")

    btn_row.addWidget(btn_cancel)
    btn_row.addStretch(1)
    btn_row.addWidget(btn_exit)
    btn_row.addWidget(btn_hide)
    layout.addLayout(btn_row)

    res = {"action": None, "remember": False}

    def on_hide():
        res["action"] = "hide"
        res["remember"] = chk_remember.isChecked()
        dlg.accept()

    def on_exit():
        res["action"] = "exit"
        res["remember"] = chk_remember.isChecked()
        dlg.accept()

    def on_cancel():
        res["action"] = None
        dlg.reject()

    btn_hide.clicked.connect(on_hide)
    btn_exit.clicked.connect(on_exit)
    btn_cancel.clicked.connect(on_cancel)

    dlg.exec()
    return res["action"], res["remember"]

def show_about_prompt(parent=None):
    """Hiển thị hộp thoại giới thiệu ứng dụng About."""
    try:
        from launcher import __version__
    except ImportError:
        __version__ = "0.2.3"
    q_parent = parent if isinstance(parent, QWidget) else None
    dlg = QMessageBox(q_parent)
    dlg.setWindowTitle(tr("dialog.about_title"))
    if APP_ICON and os.path.exists(APP_ICON):
        dlg.setWindowIcon(QIcon(APP_ICON))
    dlg.setText(tr("dialog.about_text", version=__version__))
    if APP_ICON and os.path.exists(APP_ICON):
        dlg.setIconPixmap(QPixmap(APP_ICON).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    dlg.setStandardButtons(QMessageBox.StandardButton.Ok)
    dlg.exec()
