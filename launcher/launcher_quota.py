# -*- coding: utf-8 -*-
"""
Module quản lý và hiển thị đồ họa Quota cho Antigravity Launcher (PyQt6).
Cung cấp bộ tạo Pill QPixmap bo tròn với màu gradient chuyển sắc theo % Quota.
"""

from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush, QFont, QPen
from PyQt6.QtCore import Qt, QRectF

from launcher_theme import get_active_theme, get_palette

_PIXMAP_CACHE = {}

def get_quota_pill_pixmap(val, is_valid) -> QPixmap:
    """
    Tạo hoặc lấy từ cache đối tượng QPixmap hiển thị thanh Quota pill.
    Hỗ trợ chuyển sắc mượt từ Đỏ -> Vàng -> Xanh lá theo Theme hiện hành.
    """
    theme = get_active_theme()
    key = (theme, val if is_valid else -1, is_valid)
    if key in _PIXMAP_CACHE:
        return _PIXMAP_CACHE[key]

    p = get_palette(theme)
    w_box = 112
    h_box = 22
    radius = h_box / 2.0

    pixmap = QPixmap(w_box, h_box)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 1. Rãnh nền (Background track) bo tròn theo theme
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(*p["quota_track"])))
    painter.drawRoundedRect(QRectF(1, 1, w_box - 2, h_box - 2), radius - 1, radius - 1)

    # 2. Thanh Fill Bar với màu chuyển sắc
    if is_valid and val > 0:
        fill_w = max(h_box - 2, (w_box - 2) * (min(100, val) / 100.0))
        frac = val / 100.0
        c_red, c_yel, c_grn = QColor(p["red"]), QColor(p["yellow"]), QColor(p["green"])
        if frac >= 0.5:
            t = (frac - 0.5) * 2.0
            c0, c1 = c_yel, c_grn
        else:
            t = frac * 2.0
            c0, c1 = c_red, c_yel
        r = int(c0.red() * (1.0 - t) + c1.red() * t)
        g = int(c0.green() * (1.0 - t) + c1.green() * t)
        b = int(c0.blue() * (1.0 - t) + c1.blue() * t)

        painter.setBrush(QBrush(QColor(r, g, b)))
        painter.drawRoundedRect(QRectF(1, 1, fill_w, h_box - 2), radius - 1, radius - 1)

    # 3. Chữ %
    font = QFont("Sans", 9)
    font.setBold(True)
    painter.setFont(font)
    txt = f"{val}%" if is_valid else "--"

    if theme == "dark":
        painter.setPen(QPen(QColor(0, 0, 0, 180)))
        painter.drawText(QRectF(1.5, 1.5, w_box, h_box), Qt.AlignmentFlag.AlignCenter, txt)

    painter.setPen(QPen(QColor(p["quota_text"])))
    painter.drawText(QRectF(1, 1, w_box, h_box), Qt.AlignmentFlag.AlignCenter, txt)

    painter.end()

    _PIXMAP_CACHE[key] = pixmap
    return pixmap
