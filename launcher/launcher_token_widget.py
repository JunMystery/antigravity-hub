# -*- coding: utf-8 -*-
"""
Widget hiển thị thanh chỉ số Token (TokenMetricsBar).
Gồm 3 thẻ thống kê (Sent, Received, Cached) 48px hiển thị 15 chữ số kèm bộ chọn khung thời gian.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt

from launcher_i18n import tr
from launcher_theme import get_palette, repolish_widget
from launcher_token_storage import get_aggregated_tokens, format_full_number


class _MetricCard(QFrame):
    """Thẻ hiển thị một chỉ số Token duy nhất với chiều cao 48px và font số 13px."""

    def __init__(self, *args, **kwargs):
        super().__init__(kwargs.get("parent"))
        if len(args) >= 2 and str(args[1]).startswith("#"):
            title, color = args[0], args[1]
        elif len(args) >= 3 and str(args[2]).startswith("#"):
            title, color = args[1], args[2]
        else:
            title = args[0] if len(args) > 0 else kwargs.get("title", "")
            color = args[1] if len(args) > 1 else kwargs.get("color", "#89b4fa")

        self.setObjectName("token_metric_card")
        self.setFixedHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 2, 8, 2)
        lay.setSpacing(1)

        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("metric_title")
        lay.addWidget(self.lbl_title)

        self.lbl_val = QLabel("0")
        self.set_value_color(color)
        lay.addWidget(self.lbl_val)

        self.lbl_extra = QLabel("")
        self._last_val = "0"
        self._last_extra = ""

    def set_value_color(self, color: str):
        self.lbl_val.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")

    def set_data(self, val_str: str, extra_str: str = ""):
        if val_str != self._last_val:
            self._last_val = val_str
            self.lbl_val.setText(val_str)
        if extra_str != self._last_extra:
            self._last_extra = extra_str
            self.lbl_extra.setText(extra_str)


class TokenMetricsBar(QWidget):
    """Cụm 3 thẻ thống kê Token Metrics với bộ chọn khung thời gian."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_timeframe = "24h"
        self._buttons = {}
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(8)

        hdr_lay = QHBoxLayout()
        hdr_lay.setSpacing(6)
        self.lbl_bar_title = QLabel(tr("token.bar_title") or "Token Usage")
        self.lbl_bar_title.setObjectName("section_title")
        hdr_lay.addWidget(self.lbl_bar_title)
        hdr_lay.addStretch()

        for tf, label_key, def_label in [
            ("24h", "token.tf_24h", "24H"),
            ("7d", "token.tf_7d", "7D"),
            ("30d", "token.tf_30d", "30D"),
            ("all", "token.tf_all", "ALL")
        ]:
            btn = QPushButton(tr(label_key) or def_label)
            btn.setProperty("tf_btn", True)
            btn.setFixedSize(48, 22)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, t=tf: self.set_timeframe(t))
            self._buttons[tf] = btn
            hdr_lay.addWidget(btn)

        main_lay.addLayout(hdr_lay)

        cards_lay = QHBoxLayout()
        cards_lay.setSpacing(8)
        p = get_palette()
        self.card_sent = _MetricCard(tr("token.sent") or "Sent", p["tok_in"], parent=self)
        self.card_recv = _MetricCard(tr("token.received") or "Received", p["tok_out"], parent=self)
        self.card_cached = _MetricCard(tr("token.cached") or "Cached", p["tok_cached"], parent=self)

        cards_lay.addWidget(self.card_sent)
        cards_lay.addWidget(self.card_recv)
        cards_lay.addWidget(self.card_cached)

        main_lay.addLayout(cards_lay)
        self._update_button_styles()
        self.refresh_metrics()

    def refresh_theme(self):
        p = get_palette()
        self.card_sent.set_value_color(p["tok_in"])
        self.card_recv.set_value_color(p["tok_out"])
        self.card_cached.set_value_color(p["tok_cached"])
        self._update_button_styles()

    def set_timeframe(self, tf: str):
        self.active_timeframe = tf
        self._update_button_styles()
        self.refresh_metrics()

    def _update_button_styles(self):
        for tf, btn in self._buttons.items():
            btn.setProperty("active", tf == self.active_timeframe)
            repolish_widget(btn)

    def refresh_metrics(self):
        """Đọc và cập nhật số liệu token đầy đủ 15 chữ số có dấu phẩy lên các thẻ."""
        agg = get_aggregated_tokens(self.active_timeframe)
        self.card_sent.set_data(format_full_number(agg["sent"]))
        self.card_recv.set_data(format_full_number(agg["received"]))
        self.card_cached.set_data(format_full_number(agg["cached"]))

    def retranslate_ui(self):
        """Cập nhật nhãn khi đổi ngôn ngữ."""
        self.lbl_bar_title.setText(tr("token.bar_title") or "Token Usage")
        self._buttons["24h"].setText(tr("token.tf_24h") or "24H")
        self._buttons["7d"].setText(tr("token.tf_7d") or "7D")
        self._buttons["30d"].setText(tr("token.tf_30d") or "30D")
        self._buttons["all"].setText(tr("token.tf_all") or "ALL")
        self.card_sent.lbl_title.setText(tr("token.sent") or "Sent")
        self.card_recv.lbl_title.setText(tr("token.received") or "Received")
        self.card_cached.lbl_title.setText(tr("token.cached") or "Cached")
        self.refresh_metrics()
