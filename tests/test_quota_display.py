# -*- coding: utf-8 -*-
"""
Unit tests for Quota display, role mapping, and non-destructive refresh.
"""

import sys
import unittest
sys.path.insert(0, "launcher")

from PyQt6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QPushButton, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from launcher_treeview_updater import (
    get_quota_color, _set_row_spinner, update_row_quota_display
)

app = QApplication.instance() or QApplication(["-platform", "offscreen"])

class TestQuotaDisplay(unittest.TestCase):
    """Kiểm tra sửa lỗi UserRole và hiển thị Quota không ghi đè."""

    def test_user_role_constant_and_data_lookup(self):
        """Xác nhận Qt.ItemDataRole.UserRole có giá trị 256 và item.data(32) không khớp."""
        self.assertEqual(int(Qt.ItemDataRole.UserRole), 256)
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, "prof_alpha")
        self.assertEqual(item.data(Qt.ItemDataRole.UserRole), "prof_alpha")
        self.assertEqual(item.data(256), "prof_alpha")
        self.assertIsNone(item.data(32))

    def test_quota_color_thresholds(self):
        """Xác nhận bảng màu Catppuccin theo ngưỡng Quota."""
        self.assertEqual(get_quota_color(10.0, True), "#f38ba8")
        self.assertEqual(get_quota_color(90.0, False), "#f38ba8")
        self.assertEqual(get_quota_color(35.0, True), "#f9e2af")
        self.assertEqual(get_quota_color(75.0, True), "#a6e3a1")

    def test_non_destructive_refresh(self):
        """Xác nhận _set_row_spinner hiển thị spinner animation trên ô quota trong lúc fetch và cập nhật nút refresh."""
        table = QTableWidget(1, 6)
        item_q5 = QTableWidgetItem("85%")
        item_qw = QTableWidgetItem("92%")
        table.setItem(0, 3, item_q5)
        table.setItem(0, 4, item_qw)

        btn_cell = QWidget()
        btn_layout = QHBoxLayout(btn_cell)
        btn = QPushButton("⟳")
        btn_layout.addWidget(btn)
        table.setCellWidget(0, 5, btn_cell)

        _set_row_spinner(table, 0, "⠋", QColor("#89b4fa"))

        # Quota text hiển thị spinner animation để người dùng nhận biết đang fetch
        self.assertEqual(table.item(0, 3).text(), "⠋")
        self.assertEqual(table.item(0, 4).text(), "⠋")
        # Nút ở cột 5 phải hiển thị spinner và bị disable
        self.assertEqual(btn.text(), "⠋")
        self.assertFalse(btn.isEnabled())

    def test_update_row_quota_display(self):
        """Xác nhận update_row_quota_display tìm đúng dòng qua UserRole và cập nhật giá trị mới."""
        table = QTableWidget(1, 6)
        item_order = QTableWidgetItem("1")
        item_order.setData(Qt.ItemDataRole.UserRole, "prof_test_123")
        table.setItem(0, 0, item_order)

        table.setItem(0, 3, QTableWidgetItem("50%"))
        table.setItem(0, 4, QTableWidgetItem("60%"))

        btn_cell = QWidget()
        btn_layout = QHBoxLayout(btn_cell)
        btn = QPushButton("◐")
        btn.setEnabled(False)
        btn_layout.addWidget(btn)
        table.setCellWidget(0, 5, btn_cell)

        class DummyWin:
            def __init__(self, t):
                self.treeview = t
                self.refreshing_profile_ids = {"prof_test_123"}

        win = DummyWin(table)
        update_row_quota_display(win, "prof_test_123", 95.0, "95%", True, 88.0, "88%", True)

        self.assertEqual(table.item(0, 3).text(), "95%")
        self.assertEqual(table.item(0, 4).text(), "88%")
        self.assertEqual(btn.text(), "⟳")
        self.assertTrue(btn.isEnabled())
        self.assertNotIn("prof_test_123", win.refreshing_profile_ids)

if __name__ == "__main__":
    unittest.main()
