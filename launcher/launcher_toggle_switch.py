# -*- coding: utf-8 -*-
"""
Component Toggle Switch chuẩn iOS hiện đại cho PyQt6.
Dùng cho cột Active trên bảng tài khoản và bảng quy tắc Model.
"""

from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush

from launcher_theme import get_palette


class ToggleSwitch(QCheckBox):
    """Nút gạt Bật/Tắt (Toggle Switch) phong cách iOS hiện đại bo tròn."""

    def __init__(self, checked=True, parent=None):
        super().__init__(parent)
        self.setChecked(checked)
        self.setFixedSize(36, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText("")

    def paintEvent(self, event):
        """Vẽ rãnh bo tròn (track) và con trượt (thumb) theo trạng thái và Theme hiện hành."""
        p = get_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = 36.0, 20.0
        radius = h / 2.0
        is_on = self.isChecked()

        track_color = QColor(p["toggle_on_track"] if is_on else p["toggle_off_track"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        thumb_diameter = 16.0
        thumb_x = (w - thumb_diameter - 2.0) if is_on else 2.0
        thumb_y = 2.0
        thumb_color = QColor(p["toggle_on_thumb"] if is_on else p["toggle_off_thumb"])

        painter.setBrush(QBrush(thumb_color))
        painter.drawEllipse(QRectF(thumb_x, thumb_y, thumb_diameter, thumb_diameter))
        painter.end()

    def hitButton(self, pos):
        """Cho phép nhấp toàn bộ diện tích widget để kích hoạt."""
        return self.rect().contains(pos)
