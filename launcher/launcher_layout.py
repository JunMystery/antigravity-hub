# -*- coding: utf-8 -*-
"""
Module xây dựng cấu trúc giao diện (Layout) và QSS cho Antigravity Launcher Window (PyQt6).
Hỗ trợ đầy đủ đa nền tảng Windows và Linux.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QIcon

from launcher_storage import APP_ICON
from launcher_i18n import tr, SUPPORTED_LANGUAGES, get_current_language
from launcher_monitor import build_monitor_frame
from launcher_theme import apply_launcher_style, LAUNCHER_QSS

# apply_launcher_style được nhập và quản lý từ launcher_theme (re-export)

def build_launcher_layout(win):
    """Xây dựng các thành phần widget chính cho Launcher Window."""
    central = QWidget(win)
    win.setCentralWidget(central)
    root_layout = QVBoxLayout(central)
    root_layout.setContentsMargins(16, 14, 16, 14)
    root_layout.setSpacing(10)

    # Header Box
    header = QHBoxLayout()
    header.setSpacing(10)

    win.icon_lbl = QLabel()
    if os.path.exists(APP_ICON):
        pixmap = QPixmap(APP_ICON).scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        win.icon_lbl.setPixmap(pixmap)
    header.addWidget(win.icon_lbl, 0)

    title_box = QVBoxLayout()
    title_box.setSpacing(2)
    win.title_lbl = QLabel(f"<b><span style='font-size:16px;'>{tr('app.title')}</span></b>")
    win.sub_lbl = QLabel(tr("app.subtitle"))
    title_box.addWidget(win.title_lbl)
    title_box.addWidget(win.sub_lbl)
    header.addLayout(title_box, 1)

    win.combo_lang = QComboBox()
    for code, name in SUPPORTED_LANGUAGES:
        win.combo_lang.addItem(name, code)
    idx = win.combo_lang.findData(get_current_language())
    if idx >= 0:
        win.combo_lang.setCurrentIndex(idx)
    win.combo_lang.currentIndexChanged.connect(win.on_language_changed)
    header.addWidget(win.combo_lang, 0, Qt.AlignmentFlag.AlignVCenter)

    # Settings icon button
    win.btn_settings = QPushButton("⚙")
    win.btn_settings.setObjectName("btn_settings")
    win.btn_settings.setFixedSize(30, 28)
    win.btn_settings.setToolTip(tr("settings.title"))
    win.btn_settings.clicked.connect(win.on_settings_clicked)
    header.addWidget(win.btn_settings, 0, Qt.AlignmentFlag.AlignVCenter)
    root_layout.addLayout(header)

    # Action Bar (Add, Delete on Left, Auto & Refresh Quota on Right)
    act_bar = QHBoxLayout()
    act_bar.setSpacing(8)
    win.btn_add = QPushButton(tr("btn.add").replace("_", "&"))
    win.btn_add.clicked.connect(win.on_add_account)
    act_bar.addWidget(win.btn_add)

    win.btn_del = QPushButton(tr("btn.delete").replace("_", "&"))
    win.btn_del.clicked.connect(win.on_delete_account)
    act_bar.addWidget(win.btn_del)

    act_bar.addStretch(1)

    win.btn_auto = QPushButton()
    win.btn_auto.setFixedHeight(28)
    win.btn_auto.clicked.connect(win.on_toggle_auto_quota)
    act_bar.addWidget(win.btn_auto)

    win.btn_refresh_all = QPushButton("⟳")
    win.btn_refresh_all.setObjectName("btn_refresh_all")
    win.btn_refresh_all.setToolTip(tr("tooltip.refresh_all"))
    win.btn_refresh_all.setFixedSize(36, 28)
    win.btn_refresh_all.setStyleSheet("padding: 0px; font-size: 13px;")
    win.btn_refresh_all.clicked.connect(win.on_refresh_all_quota)
    act_bar.addWidget(win.btn_refresh_all)

    root_layout.addLayout(act_bar)

    # Table View placeholder (will be attached by setup_treeview)
    win.table_container = QVBoxLayout()
    root_layout.addLayout(win.table_container, 1)

    # Info summary label
    win.lbl_info = QLabel()
    root_layout.addWidget(win.lbl_info)

    # Live Monitor Frame
    win.monitor_frame = build_monitor_frame(win)
    root_layout.addWidget(win.monitor_frame)

    # Options Bar
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    root_layout.addWidget(sep)

    opt_bar = QHBoxLayout()
    win.rr_info = QLabel(tr("opt.mode"))
    opt_bar.addWidget(win.rr_info)
    opt_bar.addStretch(1)

    win.spin_lbl = QLabel(tr("opt.req_per_acc"))
    opt_bar.addWidget(win.spin_lbl)

    cur_reqs = win.data.get("settings", {}).get("requests_per_account", 1)
    win.spin_reqs = QSpinBox()
    win.spin_reqs.setRange(1, 500)
    win.spin_reqs.setValue(cur_reqs)
    win.spin_reqs.valueChanged.connect(win.on_spin_changed)
    opt_bar.addWidget(win.spin_reqs)
    root_layout.addLayout(opt_bar)

    # Launch Buttons (App and IDE)
    launch_box = QHBoxLayout()
    launch_box.setSpacing(10)

    win.btn_launch_app = QPushButton("🚀 " + tr("btn.launch_app"))
    win.btn_launch_app.setObjectName("btn_launch_app")
    win.btn_launch_app.setFixedHeight(42)
    win.btn_launch_app.clicked.connect(win.on_launch_app_clicked)
    launch_box.addWidget(win.btn_launch_app, 1)
    win.btn_launch = win.btn_launch_app  # Legacy compatibility alias

    win.btn_launch_ide = QPushButton("💻 " + tr("btn.launch_ide"))
    win.btn_launch_ide.setObjectName("btn_launch_ide")
    win.btn_launch_ide.setFixedHeight(42)
    win.btn_launch_ide.clicked.connect(win.on_launch_ide_clicked)
    launch_box.addWidget(win.btn_launch_ide, 1)

    root_layout.addLayout(launch_box)

def retranslate_layout(win):
    """Cập nhật toàn bộ nhãn tĩnh trên layout khi đổi ngôn ngữ."""
    win.setWindowTitle(tr("app.title"))
    win.title_lbl.setText(f"<b><span style='font-size:16px;'>{tr('app.title')}</span></b>")
    win.sub_lbl.setText(tr("app.subtitle"))
    win.btn_add.setText(tr("btn.add").replace("_", "&"))
    win.btn_del.setText(tr("btn.delete").replace("_", "&"))
    if hasattr(win, "btn_refresh_all"):
        win.btn_refresh_all.setToolTip(tr("tooltip.refresh_all"))
    if hasattr(win, "btn_settings"):
        win.btn_settings.setToolTip(tr("settings.title"))
    if hasattr(win, "monitor_frame") and win.monitor_frame:
        win.monitor_frame.setTitle(tr("monitor.box_title"))
    if hasattr(win, "btn_proxy_next") and win.btn_proxy_next:
        win.btn_proxy_next.setText(tr("monitor.btn_next"))
        win.btn_proxy_next.setToolTip(tr("monitor.btn_next_tooltip"))
    win.rr_info.setText(tr("opt.mode"))
    win.spin_lbl.setText(tr("opt.req_per_acc"))
    if hasattr(win, "btn_launch_app"):
        win.btn_launch_app.setText("🚀 " + tr("btn.launch_app"))
    if hasattr(win, "btn_launch_ide"):
        win.btn_launch_ide.setText("💻 " + tr("btn.launch_ide"))
    if hasattr(win, "update_live_monitor"):
        win.update_live_monitor()
