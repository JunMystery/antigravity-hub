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

def apply_launcher_style(app):
    """Áp dụng kiểu giao diện hiện đại đồng nhất qua QSS."""
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1e1e2e;
            color: #cdd6f4;
        }
        QWidget {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 13px;
            color: #cdd6f4;
        }
        QPushButton {
            background-color: #313244;
            color: #cdd6f4;
            border: 1px solid #45475a;
            border-radius: 4px;
            padding: 5px 12px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #45475a;
        }
        QPushButton:disabled {
            background-color: #181825;
            color: #6c7086;
            border-color: #313244;
        }
        QPushButton#btn_launch {
            background-color: #2980b9;
            color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            padding: 10px;
            border-radius: 6px;
            border: none;
        }
        QPushButton#btn_launch:hover {
            background-color: #3498db;
        }
        QPushButton#btn_launch:disabled {
            background-color: #313244;
            color: #6c7086;
        }
        QTableWidget {
            background-color: #181825;
            color: #cdd6f4;
            gridline-color: #313244;
            border: 1px solid #313244;
            border-radius: 6px;
            selection-background-color: #45475a;
        }
        QHeaderView::section {
            background-color: #313244;
            color: #cdd6f4;
            padding: 4px;
            border: 1px solid #45475a;
            font-weight: bold;
        }
        QComboBox, QSpinBox {
            background-color: #313244;
            color: #cdd6f4;
            border: 1px solid #45475a;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QGroupBox {
            border: 1px solid #45475a;
            border-radius: 6px;
            margin-top: 8px;
            padding-top: 10px;
            font-weight: bold;
        }
    """)

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
    root_layout.addLayout(header)

    # Action Bar (Add, Delete)
    act_bar = QHBoxLayout()
    act_bar.setSpacing(8)
    win.btn_add = QPushButton(tr("btn.add").replace("_", "&"))
    win.btn_add.clicked.connect(win.on_add_account)
    act_bar.addWidget(win.btn_add)

    win.btn_del = QPushButton(tr("btn.delete").replace("_", "&"))
    win.btn_del.clicked.connect(win.on_delete_account)
    act_bar.addWidget(win.btn_del)
    act_bar.addStretch(1)
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

    # Big Launch Button
    win.btn_launch = QPushButton(tr("btn.launch"))
    win.btn_launch.setObjectName("btn_launch")
    win.btn_launch.setFixedHeight(44)
    win.btn_launch.clicked.connect(win.on_launch_clicked)
    root_layout.addWidget(win.btn_launch)

def retranslate_layout(win):
    """Cập nhật toàn bộ nhãn tĩnh trên layout khi đổi ngôn ngữ."""
    win.setWindowTitle(tr("app.title"))
    win.title_lbl.setText(f"<b><span style='font-size:16px;'>{tr('app.title')}</span></b>")
    win.sub_lbl.setText(tr("app.subtitle"))
    win.btn_add.setText(tr("btn.add").replace("_", "&"))
    win.btn_del.setText(tr("btn.delete").replace("_", "&"))
    win.rr_info.setText(tr("opt.mode"))
    win.spin_lbl.setText(tr("opt.req_per_acc"))
    win.btn_launch.setText(tr("btn.launch"))
