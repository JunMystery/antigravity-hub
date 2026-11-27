# -*- coding: utf-8 -*-
"""
Module cung cấp OrderCellWidget cho cột STT trong bảng Antigravity Launcher.
Hiển thị số thứ tự nhập nhanh kèm cụm nút Micro-Stepper (▲/▼) xếp dọc trong cùng một ô.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLineEdit
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIntValidator

from launcher_i18n import tr


class OrderCellWidget(QWidget):
    """Widget ô số thứ tự tích hợp ô nhập nhanh và cụm 2 nút Lên/Xuống micro-stepper."""

    def __init__(self, pid: str, order_num: int, is_first: bool, is_last: bool, on_step_callback, on_edit_callback, parent=None):
        super().__init__(parent)
        self.pid = pid
        self.order_num = order_num
        self.on_step_callback = on_step_callback
        self.on_edit_callback = on_edit_callback

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Ô hiển thị / nhập số thứ tự
        self.edit_num = QLineEdit(str(order_num), self)
        self.edit_num.setObjectName("order_edit_num")
        self.edit_num.setFixedWidth(26)
        self.edit_num.setFixedHeight(22)
        self.edit_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit_num.setToolTip(tr("order.edit_tooltip"))
        self.edit_num.setValidator(QIntValidator(1, 9999, self))
        self.edit_num.editingFinished.connect(self._handle_editing_finished)
        layout.addWidget(self.edit_num)

        # 2. Cụm 2 nút micro-stepper xếp dọc
        stepper_box = QVBoxLayout()
        stepper_box.setContentsMargins(0, 0, 0, 0)
        stepper_box.setSpacing(1)
        stepper_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_up = QPushButton("▲", self)
        self.btn_up.setObjectName("order_step_btn")
        self.btn_up.setFixedSize(16, 11)
        self.btn_up.setToolTip(tr("order.move_up"))
        self.btn_up.setEnabled(not is_first)
        self.btn_up.clicked.connect(lambda: self.on_step_callback(self.pid, -1))
        stepper_box.addWidget(self.btn_up)

        self.btn_down = QPushButton("▼", self)
        self.btn_down.setObjectName("order_step_btn")
        self.btn_down.setFixedSize(16, 11)
        self.btn_down.setToolTip(tr("order.move_down"))
        self.btn_down.setEnabled(not is_last)
        self.btn_down.clicked.connect(lambda: self.on_step_callback(self.pid, 1))
        stepper_box.addWidget(self.btn_down)

        layout.addLayout(stepper_box)

    def _handle_editing_finished(self):
        text = self.edit_num.text().strip()
        try:
            val = max(1, int(text))
        except ValueError:
            self.edit_num.setText(str(self.order_num))
            return

        if val != self.order_num:
            self.on_edit_callback(self.pid, val)

    def sizeHint(self) -> QSize:
        return QSize(68, 24)
