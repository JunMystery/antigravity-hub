# -*- coding: utf-8 -*-
"""
Custom QStyledItemDelegate for Token In/Out/Cached values.
Renders 'In' in Orange (#fab387), '/' in Gray (#6c7086), 'Out' in Green (#a6e3a1),
and optional '(+Cached)' in Yellow (#f9e2af), with '/' anchored as the horizontal center.
"""

import re
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PyQt6.QtCore import Qt, QModelIndex, QRect, QSize
from PyQt6.QtGui import QPainter, QColor

COLOR_IN = QColor("#f97316")      # Vibrant Orange for In (Sent)
COLOR_SLASH = QColor("#6c7086")   # Overlay Gray for '/'
COLOR_OUT = QColor("#22c55e")     # Vivid Green for Out (Received)
COLOR_CACHED = QColor("#f59e0b")  # Vibrant Amber/Gold for Cached
COLOR_MUTED = QColor("#585b70")   # Dim Gray for empty / --


def _format_single_token(val: str) -> str:
    """Chuyển đổi số nguyên hoặc số kèm hậu tố k/K/m/M/b/B sang chuỗi số nguyên có dấu phẩy."""
    v = (val or "").strip()
    if not v or v in ("--", "0"):
        return v
    if re.fullmatch(r"[0-9,]+", v):
        try:
            return f"{int(v.replace(',', '')):,}"
        except Exception:
            return v
    m_unit = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([kKmMgGbBtT]?)", v)
    if m_unit:
        num_str, unit = m_unit.groups()
        try:
            num = float(num_str)
            mult = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}.get(unit.upper(), 1)
            return f"{int(round(num * mult)):,}"
        except Exception:
            return v
    return v


def format_number_with_commas(val_str: str) -> str:
    """Định dạng chuỗi số token sang dạng số nguyên có dấu phẩy (000,000), hỗ trợ cả log cũ có hậu tố K."""
    s = (val_str or "").strip()
    if s.startswith("(+") and s.endswith(")"):
        inner = s[2:-1].strip()
        return f"(+{_format_single_token(inner)})"
    return _format_single_token(s)


def parse_token_display_text(raw_text: str):
    """
    Parses token string into (in_text, out_text, cached_text) with comma grouping.
    Example inputs:
      '122854 / 1542 (+156602)' -> ('122,854', '1,542', '(+156,602)')
      '184.2k / 91' -> ('184.2k', '91', '')
      '-- / --' -> ('--', '--', '')
    """
    cleaned = (raw_text or "").strip()
    if not cleaned or "/" not in cleaned:
        return format_number_with_commas(cleaned), "", ""

    parts = cleaned.split("/", 1)
    in_text = parts[0].strip()
    rest = parts[1].strip()

    cached_m = re.search(r"(\(\+[^)]+\))", rest)
    if cached_m:
        cached_text = cached_m.group(1).strip()
        out_text = rest.replace(cached_text, "").strip()
    else:
        cached_text = ""
        out_text = rest

    return format_number_with_commas(in_text), format_number_with_commas(out_text), format_number_with_commas(cached_text)


class TokenInOutDelegate(QStyledItemDelegate):
    """Delegate for drawing colored In / Out / Cached tokens anchored at center '/'."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()

        # Draw default background / selection
        self.initStyleOption(option, index)
        widget = option.widget
        style = widget.style() if widget else None
        if style:
            style.drawPrimitive(style.PrimitiveElement.PE_PanelItemViewItem, option, painter, widget)
        elif option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        raw_text = index.data(Qt.ItemDataRole.DisplayRole)
        in_text, out_text, cached_text = parse_token_display_text(raw_text)

        rect = option.rect
        fm = option.fontMetrics

        if not in_text and not out_text:
            painter.restore()
            return

        if "/" not in (raw_text or ""):
            painter.setPen(COLOR_MUTED)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, (raw_text or "").strip() or "--")
            painter.restore()
            return

        if in_text in ("--", "") and out_text in ("--", ""):
            painter.setPen(COLOR_MUTED)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, in_text or "--")
            painter.restore()
            return

        # Neo cố định dấu '/' tại tâm ngang của ô để đồng bộ giữa dòng có và không có cached
        slash_str = "/"
        slash_w = max(fm.horizontalAdvance(slash_str), 8)
        spacing = 5
        pad_x = 4

        center_x = rect.center().x()
        slash_x = center_x - slash_w // 2

        painter.setClipRect(rect)

        # 1. Draw '/' separator at center_x
        slash_rect = QRect(slash_x, rect.y(), slash_w, rect.height())
        painter.setPen(COLOR_SLASH)
        painter.drawText(slash_rect, Qt.AlignmentFlag.AlignCenter, slash_str)

        # 2. Draw 'In' right-aligned before slash
        in_left = rect.x() + pad_x
        in_avail_w = max(0, slash_x - spacing - in_left)
        if in_avail_w > 0:
            in_draw = fm.elidedText(in_text, Qt.TextElideMode.ElideLeft, in_avail_w) if fm.horizontalAdvance(in_text) > in_avail_w else in_text
            in_rect = QRect(in_left, rect.y(), in_avail_w, rect.height())
            painter.setPen(COLOR_IN)
            painter.drawText(in_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, in_draw)

        # 3. Draw 'Out' left-aligned after slash
        out_x = slash_x + slash_w + spacing
        right_limit = rect.right() - pad_x + 1
        out_avail_w = max(0, right_limit - out_x)
        out_w = fm.horizontalAdvance(out_text)
        if out_avail_w > 0:
            out_draw = fm.elidedText(out_text, Qt.TextElideMode.ElideRight, out_avail_w) if out_w > out_avail_w else out_text
            out_rect = QRect(out_x, rect.y(), min(out_w, out_avail_w), rect.height())
            painter.setPen(COLOR_OUT)
            painter.drawText(out_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, out_draw)

            # 4. Draw 'Cached' (if any) after out
            if cached_text and out_w < out_avail_w:
                cached_x = out_x + out_w + 4
                cached_avail_w = max(0, right_limit - cached_x)
                if cached_avail_w > 0:
                    cached_w = fm.horizontalAdvance(cached_text)
                    cached_draw = fm.elidedText(cached_text, Qt.TextElideMode.ElideRight, cached_avail_w) if cached_w > cached_avail_w else cached_text
                    cached_rect = QRect(cached_x, rect.y(), min(cached_w, cached_avail_w), rect.height())
                    painter.setPen(COLOR_CACHED)
                    painter.drawText(cached_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, cached_draw)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        raw_text = index.data(Qt.ItemDataRole.DisplayRole)
        in_text, out_text, cached_text = parse_token_display_text(raw_text)
        fm = option.fontMetrics
        in_w = fm.horizontalAdvance(in_text)
        out_w = fm.horizontalAdvance(out_text)
        cached_w = fm.horizontalAdvance(cached_text) if cached_text else 0
        right_w = out_w + (cached_w + 4 if cached_text else 0)
        w = 2 * max(in_w, right_w) + 36
        if cached_text:
            return QSize(max(w, 240), 28)
        return QSize(max(w, 160), 28)
