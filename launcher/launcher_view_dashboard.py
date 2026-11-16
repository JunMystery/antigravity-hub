# -*- coding: utf-8 -*-
"""
View Tổng quan (Dashboard View) cho Antigravity Launcher.
Hiển thị thanh tóm tắt trạng thái liền khối (CompactStatusBar), thanh tác vụ phân nhóm,
và luồng nhật ký hoạt động tinh gọn 1 bảng (ActivityLogsPanel).
"""

import os
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt

from launcher_storage import CONFIG_DIR
from launcher_i18n import tr
from launcher_proxy import is_proxy_running
from launcher_widget import CompactStatusBar
from launcher_activity_widget import ActivityLogsPanel
from launcher_token_widget import TokenMetricsBar

STATUS_FILE = os.path.join(CONFIG_DIR, "live_status.json")


class _CardAdapter:
    """Bộ chuyển đổi tương thích ngược cho các đoạn mã hoặc kiểm thử cũ."""
    def __init__(self, title_text: str = ""):
        self.lbl_title = QLabel(title_text)
        self.lbl_value = QLabel()

    def set_value(self, val: str):
        self.lbl_value.setText(val)

    def set_status(self, color: str):
        pass


class DashboardView(QWidget):
    """View hiển thị hoạt động trực tiếp của Proxy và luồng request."""

    def __init__(self, win, parent=None):
        super().__init__(parent)
        self.win = win
        self.active_filter = "ALL"

        self.setObjectName("dashboard_view")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # 1. Thanh tóm tắt trạng thái liền khối (Compact Inline Bar)
        self.status_bar = CompactStatusBar(self)
        self.status_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.status_bar)

        # Thuộc tính tương thích ngược
        self.card_status = _CardAdapter(tr("monitor.col_status"))
        self.card_acc = _CardAdapter(tr("monitor.col_acc"))
        self.card_turn = _CardAdapter(tr("monitor.col_turn"))
        self.card_total = _CardAdapter(tr("monitor.col_total"))

        # 2. Thanh tác vụ phân nhóm (Primary Launch vs Secondary Proxy Controls)
        act_box = QHBoxLayout()
        act_box.setSpacing(10)

        # Nhóm 1: Tác vụ khởi chạy chính
        launch_group = QHBoxLayout()
        launch_group.setSpacing(8)
        self.btn_launch_app = QPushButton(tr("btn.launch_app"))
        self.btn_launch_app.setObjectName("btn_launch_app")
        self.btn_launch_app.setFixedHeight(34)
        self.btn_launch_app.clicked.connect(self.win.on_launch_app_clicked)
        launch_group.addWidget(self.btn_launch_app, 1)

        self.btn_launch_ide = QPushButton(tr("btn.launch_ide"))
        self.btn_launch_ide.setObjectName("btn_launch_ide")
        self.btn_launch_ide.setFixedHeight(34)
        self.btn_launch_ide.clicked.connect(self.win.on_launch_ide_clicked)
        launch_group.addWidget(self.btn_launch_ide, 1)
        act_box.addLayout(launch_group, 3)

        # Đường phân cách đứng
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Plain)
        divider.setStyleSheet("color: #313244; border: none; border-left: 1px solid #313244;")
        act_box.addWidget(divider)

        # Nhóm 2: Điều khiển Proxy phụ trợ
        proxy_group = QHBoxLayout()
        proxy_group.setSpacing(8)
        self.btn_next = QPushButton(tr("monitor.btn_next"))
        self.btn_next.setObjectName("btn_proxy_next")
        self.btn_next.setFixedHeight(34)
        self.btn_next.clicked.connect(self.win.on_manual_next_account)
        proxy_group.addWidget(self.btn_next)

        self.btn_toggle_proxy = QPushButton(tr("btn.pause_rotation"))
        self.btn_toggle_proxy.setObjectName("btn_proxy_toggle")
        self.btn_toggle_proxy.setFixedHeight(34)
        self.btn_toggle_proxy.clicked.connect(self.win.on_toggle_proxy_btn)
        proxy_group.addWidget(self.btn_toggle_proxy)
        act_box.addLayout(proxy_group, 2)
        layout.addLayout(act_box)

        # 3. Thẻ thống kê Token (Token Metrics Bar)
        self.token_bar = TokenMetricsBar(self)
        self.token_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.token_bar)

        # 4. Phân vùng luồng hoạt động tinh gọn
        self.activity_panel = ActivityLogsPanel(self)
        self.activity_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.activity_panel, 1)

        # Thuộc tính tương thích ngược cho tests và launcher window
        self.table_feed = self.activity_panel.table_feed
        self.table_chat = self.activity_panel.table_chat
        self.table_subagent = self.activity_panel.table_subagent

    def _set_filter(self, f_type: str):
        """Hỗ trợ tương thích ngược cho việc lọc tag."""
        self.active_filter = f_type
        self.activity_panel._set_filter(f_type)

    def retranslate_ui(self):
        """Cập nhật giao diện khi thay đổi ngôn ngữ động."""
        self.btn_launch_app.setText(tr("btn.launch_app"))
        self.btn_launch_ide.setText(tr("btn.launch_ide"))
        self.btn_next.setText(tr("monitor.btn_next"))
        self.card_status.lbl_title.setText(tr("monitor.col_status"))
        self.card_acc.lbl_title.setText(tr("monitor.col_acc"))
        self.card_turn.lbl_title.setText(tr("monitor.col_turn"))
        self.card_total.lbl_title.setText(tr("monitor.col_total"))
        if hasattr(self, "token_bar"):
            self.token_bar.retranslate_ui()
        if hasattr(self, "activity_panel"):
            self.activity_panel.retranslate_ui()

    def update_dashboard(self):
        """Cập nhật dữ liệu từ live_status.json và proxy.log lên Dashboard."""
        status_lbl = tr("monitor.col_status") or "Trạng thái"
        acc_lbl = tr("monitor.col_acc") or "Tài khoản"
        turn_lbl = tr("monitor.col_turn") or "Lượt"

        if hasattr(self, "token_bar"):
            self.token_bar.refresh_metrics()

        if not is_proxy_running():
            self.status_bar.set_state("● STOPPED", "#f38ba8", "", tr("monitor.acc_unavailable"), "--", turn_label=turn_lbl, status_label=status_lbl, acc_label=acc_lbl)
            self.card_status.set_value("● STOPPED")
            self.card_acc.set_value(tr("monitor.acc_unavailable"))
            self.card_turn.set_value("--")
            self.card_total.set_value("--")
            self.btn_toggle_proxy.setText(tr("btn.start_proxy"))
            self.btn_next.setEnabled(False)
            self._read_recent_logs()
            return

        self.btn_next.setEnabled(True)
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                status = data.get("status", "standby")
                is_paused = bool(data.get("paused", False) or status == "paused")
                acc = data.get("account_email") or data.get("account_name") or "--"
                cur_req = data.get("current_req", 0)
                max_req = data.get("requests_per_account", 1)
                tot_req = data.get("total_requests", 0)

                turn_str = f"{cur_req}/{max_req}"
                if is_paused:
                    self.status_bar.set_state("● PAUSED", "#f9e2af", "20130", acc, turn_str, turn_label=turn_lbl, status_label=status_lbl, acc_label=acc_lbl)
                    self.card_status.set_value("● PAUSED")
                    self.btn_toggle_proxy.setText(tr("btn.resume_rotation"))
                else:
                    is_active = (status == "sending")
                    st_text = "● ACTIVE" if is_active else "● STANDBY"
                    st_color = "#a6e3a1" if is_active else "#89b4fa"
                    self.status_bar.set_state(st_text, st_color, "20130", acc, turn_str, turn_label=turn_lbl, status_label=status_lbl, acc_label=acc_lbl)
                    self.card_status.set_value(st_text)
                    self.btn_toggle_proxy.setText(tr("btn.pause_rotation"))

                self.card_acc.set_value(acc)
                self.card_turn.set_value(turn_str)
                self.card_total.set_value(str(tot_req))
            except Exception:
                pass
        self._read_recent_logs()

    def _read_recent_logs(self):
        self.activity_panel._read_recent_logs()
