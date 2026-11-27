# -*- coding: utf-8 -*-
"""
Module cung cấp các widget giao diện dùng chung (Reusable UI Components)
cho Antigravity Launcher: CompactStatusBar, MetricCard, BadgeLabel, SettingRow, NavButton.
"""

from PyQt6.QtWidgets import (
    QFrame, QLabel, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QSizePolicy
)
from PyQt6.QtCore import Qt

from launcher_theme import get_palette, repolish_widget


class CompactStatusBar(QFrame):
    """Thanh tóm tắt trạng thái liền khối (Seamless Unified Status Bar) 3 phân vùng hiện đại."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_state = None
        self.setObjectName("compact_status_bar")
        self.setFixedHeight(60)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 4, 14, 4)
        layout.setSpacing(12)

        col_status = QVBoxLayout()
        col_status.setSpacing(1)
        self.lbl_status_title = QLabel("Trạng thái")
        self.lbl_status_title.setObjectName("status_title")
        self.lbl_status = QLabel("● STANDBY")
        self.lbl_status_sub = QLabel("Port 20130")
        self.lbl_status_sub.setObjectName("status_sub")
        col_status.addWidget(self.lbl_status_title)
        col_status.addWidget(self.lbl_status)
        col_status.addWidget(self.lbl_status_sub)
        layout.addLayout(col_status)

        div1 = QFrame()
        div1.setObjectName("status_divider")
        div1.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(div1)

        col_acc = QVBoxLayout()
        col_acc.setSpacing(1)
        self.lbl_acc_title = QLabel("Tài khoản")
        self.lbl_acc_title.setObjectName("status_title")
        self.lbl_acc = QLabel("--")
        self.lbl_acc.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_acc_sub = QLabel("Round Robin")
        self.lbl_acc_sub.setObjectName("status_sub")
        col_acc.addWidget(self.lbl_acc_title)
        col_acc.addWidget(self.lbl_acc)
        col_acc.addWidget(self.lbl_acc_sub)
        layout.addLayout(col_acc, 1)

        div2 = QFrame()
        div2.setObjectName("status_divider")
        div2.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(div2)

        col_turn = QVBoxLayout()
        col_turn.setSpacing(1)
        self.lbl_turn_title = QLabel("Lượt")
        self.lbl_turn_title.setObjectName("status_title")
        self.lbl_turn = QLabel("0/1")
        self.lbl_turn_sub = QLabel("Current Turn")
        self.lbl_turn_sub.setObjectName("status_sub")
        col_turn.addWidget(self.lbl_turn_title)
        col_turn.addWidget(self.lbl_turn)
        col_turn.addWidget(self.lbl_turn_sub)
        layout.addLayout(col_turn)

        self.refresh_theme()

    def refresh_theme(self):
        p = get_palette()
        self._last_state = None
        self.lbl_status.setStyleSheet(f"color: {p['accent']}; font-size: 15px; font-weight: bold;")
        self.lbl_acc.setStyleSheet(f"color: {p['green']}; font-size: 15px; font-weight: bold;")
        self.lbl_turn.setStyleSheet(f"color: {p['accent_turn']}; font-size: 15px; font-weight: bold;")
        repolish_widget(self)

    def set_state(self, status_text: str, status_color: str, port_text: str, acc_email: str, turn_text: str,
                  turn_label: str = None, status_label: str = None, acc_label: str = None,
                  acc_sub: str = None, turn_sub: str = None, acc_color: str = None):
        state_key = (
            status_text, status_color, port_text, acc_email, turn_text,
            turn_label, status_label, acc_label, acc_sub, turn_sub, acc_color
        )
        if state_key == self._last_state:
            return
        self._last_state = state_key
        if status_label:
            self.lbl_status_title.setText(status_label)
        if acc_label:
            self.lbl_acc_title.setText(acc_label)
        if turn_label:
            self.lbl_turn_title.setText(turn_label)
        port_sub = f"Port {port_text}" if port_text else "Offline"
        self.lbl_status.setText(status_text)
        self.lbl_status.setStyleSheet(f"color: {status_color}; font-size: 15px; font-weight: bold;")
        self.lbl_status_sub.setText(port_sub)
        self.lbl_acc.setText(acc_email or "--")
        self.lbl_acc.setToolTip(acc_email or "")
        self.lbl_acc.setStyleSheet(f"color: {acc_color or get_palette()['green']}; font-size: 15px; font-weight: bold;")
        if acc_sub is not None:
            self.lbl_acc_sub.setText(acc_sub)
        if turn_sub is not None:
            self.lbl_turn_sub.setText(turn_sub)
        self.lbl_turn.setText(turn_text)


class MetricCard(QFrame):
    """Thẻ hiển thị chỉ số tổng quan với tiêu đề, giá trị chính và mô tả phụ."""

    def __init__(self, title: str, value: str, subtext: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("metric_card")
        self.setFixedHeight(70)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("metric_title")
        layout.addWidget(self.lbl_title)

        self.lbl_value = QLabel(value)
        layout.addWidget(self.lbl_value)

        self.lbl_sub = QLabel(subtext)
        self.lbl_sub.setObjectName("metric_sub")
        if not subtext:
            self.lbl_sub.hide()
        layout.addWidget(self.lbl_sub)
        self.refresh_theme()

    def refresh_theme(self):
        p = get_palette()
        self.setStyleSheet(
            f"QFrame#metric_card {{ background-color: {p['bg_card']}; border: 1px solid {p['border_card']}; "
            "border-radius: 8px; padding: 4px; }"
        )
        self.lbl_value.setStyleSheet(f"color: {p['text']}; font-size: 17px; font-weight: bold;")

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
        self._badge_type = badge_type
        self.set_badge(text, badge_type)

    def _palette_badge(self, badge_type: str):
        p = get_palette()
        key_map = {
            "main": p["accent"], "standby": p["accent"],
            "subagent": p["accent_ide"],
            "general": p["text_sub"],
            "status": p["green"], "active": p["green"],
            "error": p["red"], "paused": p["yellow"],
        }
        fg = key_map.get(badge_type.lower())
        if not fg:
            return p["text"], p["bg_surface"], p["border_strong"]
        border = p["border_strong"] if badge_type.lower() == "general" else fg
        return fg, p["bg_surface"], border if badge_type.lower() == "general" else fg

    def refresh_theme(self):
        """Đồng bộ lại màu badge theo Theme hiện hành."""
        self.set_badge(self.text(), self._badge_type)

    def set_badge(self, text: str, badge_type: str = "main"):
        self._badge_type = badge_type
        self.setText(text)
        fg, bg, border = self._palette_badge(badge_type)
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
        self.lbl_main.setObjectName("setting_title")
        lbl_box.addWidget(self.lbl_main)

        if desc:
            self.lbl_desc = QLabel(desc)
            self.lbl_desc.setObjectName("setting_desc")
            lbl_box.addWidget(self.lbl_desc)

        layout.addLayout(lbl_box, 1)
        layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)


class NavButton(QPushButton):
    """Nút điều hướng trên Sidebar với trạng thái Active/Inactive đồng bộ QSS."""

    def __init__(self, icon_text: str, label: str, view_id: str, parent=None):
        display_text = f"{icon_text}  {label}".strip() if icon_text else label
        super().__init__(display_text, parent)
        self.view_id = view_id
        self.icon_text = icon_text
        self.label_text = label
        self.setProperty("nav_btn", True)
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_active(False)

    def update_label(self, label: str, icon_text: str = None):
        if icon_text is not None:
            self.icon_text = icon_text
        self.label_text = label
        self.setText(f"{self.icon_text}  {self.label_text}".strip() if self.icon_text else self.label_text)

    def set_active(self, active: bool):
        self.setProperty("active", bool(active))
        repolish_widget(self)
