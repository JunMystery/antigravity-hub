# -*- coding: utf-8 -*-
"""
Module cung cấp các widget giao diện dùng chung (Reusable UI Components)
cho Antigravity Launcher: MetricCard, BadgeLabel, SettingRow, NavButton.
"""

from PyQt6.QtWidgets import (
    QFrame, QLabel, QWidget, QPushButton, QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import Qt

class CompactStatusBar(QFrame):
    """Thanh tóm tắt trạng thái liền khối (Seamless Unified Status Bar) 3 phân vùng hiện đại."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("compact_status_bar")
        self.setFixedHeight(68)
        self.setStyleSheet(
            "QFrame#compact_status_bar { background-color: #24273a; border: 1px solid #363a4f; "
            "border-radius: 8px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(14)

        # Cột 1: Trạng thái Micro-Proxy (cố định độ rộng tối thiểu để chống giật layout)
        col_status = QVBoxLayout()
        col_status.setSpacing(2)
        self.lbl_status_title = QLabel("Trạng thái")
        self.lbl_status_title.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: 500;")
        self.lbl_status = QLabel("● STANDBY")
        self.lbl_status.setMinimumWidth(112)
        self.lbl_status.setStyleSheet("color: #89b4fa; font-size: 15px; font-weight: bold;")
        self.lbl_status_sub = QLabel("Port 20130")
        self.lbl_status_sub.setMinimumWidth(112)
        self.lbl_status_sub.setStyleSheet("color: #6c7086; font-size: 10px;")
        self._last_status_color = "#89b4fa"
        col_status.addWidget(self.lbl_status_title)
        col_status.addWidget(self.lbl_status)
        col_status.addWidget(self.lbl_status_sub)
        layout.addLayout(col_status)

        # Phân cách đứng 1
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.VLine)
        div1.setStyleSheet("color: #313244; border: none; border-left: 1px solid #313244;")
        layout.addWidget(div1)

        # Cột 2: Tài khoản đang hoạt động (dãn rộng mượt mà theo độ dài email)
        col_acc = QVBoxLayout()
        col_acc.setSpacing(2)
        self.lbl_acc_title = QLabel("Tài khoản")
        self.lbl_acc_title.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: 500;")
        self.lbl_acc = QLabel("--")
        self.lbl_acc.setStyleSheet("color: #cdd6f4; font-size: 15px; font-weight: bold;")
        self.lbl_acc_sub = QLabel("Active Account")
        self.lbl_acc_sub.setStyleSheet("color: #6c7086; font-size: 10px;")
        col_acc.addWidget(self.lbl_acc_title)
        col_acc.addWidget(self.lbl_acc)
        col_acc.addWidget(self.lbl_acc_sub)
        layout.addLayout(col_acc, 1)

        # Phân cách đứng 2
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.VLine)
        div2.setStyleSheet("color: #313244; border: none; border-left: 1px solid #313244;")
        layout.addWidget(div2)

        # Cột 3: Lượt quay vòng hiện tại (cố định độ rộng tối thiểu để chống giật layout)
        col_turn = QVBoxLayout()
        col_turn.setSpacing(2)
        self.lbl_turn_title = QLabel("Lượt")
        self.lbl_turn_title.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: 500;")
        self.lbl_turn = QLabel("0/1")
        self.lbl_turn.setMinimumWidth(82)
        self.lbl_turn.setStyleSheet("color: #b4befe; font-size: 15px; font-weight: bold;")
        self.lbl_turn_sub = QLabel("Current Turn")
        self.lbl_turn_sub.setMinimumWidth(82)
        self.lbl_turn_sub.setStyleSheet("color: #6c7086; font-size: 10px;")
        col_turn.addWidget(self.lbl_turn_title)
        col_turn.addWidget(self.lbl_turn)
        col_turn.addWidget(self.lbl_turn_sub)
        layout.addLayout(col_turn)

    def set_state(self, status_text: str, status_color: str, port_text: str, acc_email: str, turn_text: str, turn_label: str = None, status_label: str = None, acc_label: str = None, turn_sub: str = None):
        if status_label and self.lbl_status_title.text() != status_label:
            self.lbl_status_title.setText(status_label)
        if acc_label and self.lbl_acc_title.text() != acc_label:
            self.lbl_acc_title.setText(acc_label)
        if turn_label and self.lbl_turn_title.text() != turn_label:
            self.lbl_turn_title.setText(turn_label)
        if turn_sub is not None and self.lbl_turn_sub.text() != turn_sub:
            self.lbl_turn_sub.setText(turn_sub)
        port_sub = f"Port {port_text}" if port_text else "Offline"
        if self.lbl_status.text() != status_text:
            self.lbl_status.setText(status_text)
        if status_color != getattr(self, "_last_status_color", None):
            self.lbl_status.setStyleSheet(f"color: {status_color}; font-size: 15px; font-weight: bold;")
            self._last_status_color = status_color
        if self.lbl_status_sub.text() != port_sub:
            self.lbl_status_sub.setText(port_sub)
        next_acc = acc_email or "--"
        if self.lbl_acc.text() != next_acc:
            self.lbl_acc.setText(next_acc)
        if self.lbl_turn.text() != turn_text:
            self.lbl_turn.setText(turn_text)

class MetricCard(QFrame):
    """Thẻ hiển thị chỉ số tổng quan với tiêu đề, giá trị chính và mô tả phụ."""

    def __init__(self, title: str, value: str, subtext: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("metric_card")
        self.setFixedHeight(70)
        self.setStyleSheet(
            "QFrame#metric_card { background-color: #24273a; border: 1px solid #363a4f; "
            "border-radius: 8px; padding: 4px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: 500;")
        layout.addWidget(self.lbl_title)

        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet("color: #cdd6f4; font-size: 17px; font-weight: bold;")
        layout.addWidget(self.lbl_value)

        self.lbl_sub = QLabel(subtext)
        self.lbl_sub.setStyleSheet("color: #6c7086; font-size: 10px;")
        if not subtext:
            self.lbl_sub.hide()
        layout.addWidget(self.lbl_sub)

    def set_value(self, value: str):
        self.lbl_value.setText(value)

    def set_status(self, color: str):
        self.lbl_value.setStyleSheet(f"color: {color}; font-size: 17px; font-weight: bold;")

    def set_subtext(self, subtext: str):
        self.lbl_sub.setText(subtext)
        self.lbl_sub.setVisible(bool(subtext))


class BadgeLabel(QLabel):
    """Nhãn dạng Badge với màu sắc phân biệt loại request hoặc trạng thái."""

    COLOR_MAP = {
        "main": ("#89b4fa", "rgba(137, 180, 250, 0.18)", "#89b4fa"),
        "subagent": ("#cba6f7", "rgba(203, 166, 247, 0.18)", "#cba6f7"),
        "general": ("#a6adc8", "rgba(166, 173, 200, 0.18)", "#45475a"),
        "status": ("#a6e3a1", "rgba(166, 227, 161, 0.18)", "#a6e3a1"),
        "active": ("#a6e3a1", "rgba(166, 227, 161, 0.18)", "#a6e3a1"),
        "error": ("#f38ba8", "rgba(243, 139, 168, 0.18)", "#f38ba8"),
        "standby": ("#89b4fa", "rgba(137, 180, 250, 0.18)", "#89b4fa"),
        "paused": ("#f9e2af", "rgba(249, 226, 175, 0.18)", "#f9e2af"),
    }

    def __init__(self, text: str, badge_type: str = "main", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_badge(text, badge_type)

    def set_badge(self, text: str, badge_type: str = "main"):
        self.setText(text)
        fg, bg, border = self.COLOR_MAP.get(badge_type.lower(), ("#cdd6f4", "#313244", "#45475a"))
        self.setStyleSheet(
            f"color: {fg}; background-color: {bg}; border: 1px solid {border}; "
            "border-radius: 4px; padding: 2px 7px; font-size: 10px; font-weight: bold;"
        )


class SettingRow(QWidget):
    """Một hàng cài đặt gồm nhãn + mô tả bên trái và widget điều khiển bên phải."""

    def __init__(self, label_text: str, widget: QWidget, desc: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        lbl_box = QVBoxLayout()
        lbl_box.setSpacing(2)
        self.lbl_main = QLabel(label_text)
        self.lbl_main.setStyleSheet("color: #cdd6f4; font-size: 12px; font-weight: 500;")
        lbl_box.addWidget(self.lbl_main)

        if desc:
            self.lbl_desc = QLabel(desc)
            self.lbl_desc.setStyleSheet("color: #6c7086; font-size: 11px;")
            lbl_box.addWidget(self.lbl_desc)

        layout.addLayout(lbl_box, 1)
        layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)


class NavButton(QPushButton):
    """Nút điều hướng trên Sidebar với trạng thái Active/Inactive và kiểu dáng hiện đại."""

    def __init__(self, icon_text: str, label: str, view_id: str, parent=None):
        display_text = f"{icon_text}  {label}".strip() if icon_text else label
        super().__init__(display_text, parent)
        self.view_id = view_id
        self.icon_text = icon_text
        self.label_text = label
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_active(False)

    def update_label(self, label: str, icon_text: str = None):
        if icon_text is not None:
            self.icon_text = icon_text
        self.label_text = label
        self.setText(f"{self.icon_text}  {self.label_text}".strip() if self.icon_text else self.label_text)

    def set_active(self, active: bool):
        if active:
            self.setStyleSheet(
                "QPushButton { background-color: #313244; color: #89b4fa; font-weight: bold; "
                "border: none; border-left: 3px solid #89b4fa; border-radius: 6px; text-align: left; padding-left: 12px; font-size: 13px; } "
                "QPushButton:hover { background-color: #363a4f; }"
            )
        else:
            self.setStyleSheet(
                "QPushButton { background-color: transparent; color: #a6adc8; font-weight: 500; "
                "border: none; border-radius: 6px; text-align: left; padding-left: 15px; font-size: 13px; } "
                "QPushButton:hover { background-color: #24273a; color: #cdd6f4; }"
            )
