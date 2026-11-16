# -*- coding: utf-8 -*-
"""
Module widget hiển thị ô Quota (QuotaCellWidget) và thanh tiến trình Gradient mỏng (QuotaProgressBar).
Tích hợp Progress Bar fading từ xanh lá sang đỏ, chữ % màu trắng và dòng phụ thời gian reset.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QBrush
from PyQt6.QtCore import Qt, QRectF, QSize

class QuotaProgressBar(QWidget):
    """Thanh tiến trình mỏng nhỏ với dải gradient nội bộ từ đỏ (hết) sang xanh lá (đầy)."""

    def __init__(self, val: int = 0, is_valid: bool = False, parent=None):
        super().__init__(parent)
        self.val = max(0, min(100, val))
        self.is_valid = is_valid
        self.setFixedSize(38, 5)

    def set_value(self, val: int, is_valid: bool):
        self.val = max(0, min(100, val))
        self.is_valid = is_valid
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        radius = h / 2.0

        # 1. Rãnh nền (Background track) màu xám mờ bo tròn
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(49, 50, 68, 180)))
        painter.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        # 2. Thanh Fill với dải gradient: Đỏ (trái / cạn) -> Vàng -> Xanh lá (phải / đầy)
        if self.is_valid and self.val > 0:
            fill_w = max(radius * 2.0, w * (self.val / 100.0))
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, QColor("#f38ba8"))   # Đỏ (cạn / thấp)
            grad.setColorAt(0.45, QColor("#f9e2af"))  # Vàng cam (trung bình)
            grad.setColorAt(1.0, QColor("#a6e3a1"))   # Xanh lá (đầy)

            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(QRectF(0, 0, fill_w, h), radius, radius)

        painter.end()

class QuotaCellWidget(QWidget):
    """Widget hiển thị ô Quota 2 tầng: thanh gradient + % trắng ở trên, Reset in HH:MM ở dưới."""

    def __init__(self, val: int = 0, text: str = "--", is_valid: bool = False, reset_text: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Tầng trên: Progress Bar + Chữ % màu trắng
        top_box = QHBoxLayout()
        top_box.setContentsMargins(0, 0, 0, 0)
        top_box.setSpacing(6)
        top_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.bar = QuotaProgressBar(val, is_valid, self)
        top_box.addWidget(self.bar)

        self.lbl_percent = QLabel(text, self)
        self.lbl_percent.setStyleSheet("font-size: 11px; font-weight: bold; color: #ffffff;")
        self.lbl_percent.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        top_box.addWidget(self.lbl_percent)

        layout.addLayout(top_box)

        # Tầng dưới: Dòng phụ thời gian reset (Reset in HH:MM)
        self.lbl_reset = QLabel(reset_text, self)
        self.lbl_reset.setStyleSheet("font-size: 9px; color: #a6adc8;")
        self.lbl_reset.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_reset)

        self.bar.setVisible(is_valid)
        self.lbl_reset.setVisible(bool(reset_text and is_valid))

    def set_quota(self, val: int, text: str, is_valid: bool, reset_text: str = ""):
        self.bar.set_value(val, is_valid)
        self.lbl_percent.setText(text)
        self.lbl_percent.setStyleSheet("font-size: 11px; font-weight: bold; color: #ffffff;")
        self.bar.setVisible(is_valid)

        self.lbl_reset.setText(reset_text or "")
        self.lbl_reset.setVisible(bool(reset_text and is_valid))

    def set_spinner(self, char: str, color: QColor = None):
        self.bar.setVisible(False)
        self.lbl_percent.setText(char)
        color_str = color.name() if color else "#89b4fa"
        self.lbl_percent.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color_str};")
        self.lbl_reset.setVisible(False)

    def sizeHint(self) -> QSize:
        return QSize(105, 36)
