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
from launcher_order_widget import OrderCellWidget
from launcher_quota_fetcher import format_reset_time, parse_quota_summary
from launcher_quota_widget import QuotaCellWidget, QuotaProgressBar
from datetime import datetime, timezone, timedelta

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

    def test_order_cell_widget_dimensions_and_spacing(self):
        """Xác nhận ô nhập STT và nút micro-stepper không bị chồng lấn với số có 2 chữ số (VD: 10)."""
        widget = OrderCellWidget(
            pid="prof_10",
            order_num=10,
            is_first=False,
            is_last=False,
            on_step_callback=lambda p, d: None,
            on_edit_callback=lambda p, v: None
        )
        self.assertEqual(widget.edit_num.maximumWidth(), 26)
        self.assertGreaterEqual(widget.layout().spacing(), 6)
        self.assertGreaterEqual(widget.sizeHint().width(), 68)

        # Kiểm tra khoảng cách trực quan giữa ô nhập và nút bấm
        widget.adjustSize()
        edit_right = widget.edit_num.x() + widget.edit_num.width()
        btn_left = widget.btn_up.x()
        self.assertGreaterEqual(btn_left - edit_right, 4)

    def test_format_reset_time_logic(self):
        """Xác nhận logic format thời gian reset: < 24h, >= 24h, đã qua, và rỗng."""
        self.assertEqual(format_reset_time(""), "")
        self.assertEqual(format_reset_time(None), "")
        self.assertEqual(format_reset_time("invalid-date-string"), "")

        now = datetime.now(timezone.utc)
        # 1. Trong vòng 24h: 'Reset in HH:MM'
        target_2h = (now + timedelta(hours=2, minutes=30, seconds=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(format_reset_time(target_2h), "Reset in 02:30")

        # 2. Trên 24h: 'Reset in Xd Yh'
        target_3d = (now + timedelta(days=3, hours=5, minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(format_reset_time(target_3d), "Reset in 3d 5h")

        # 3. Đã qua thời gian reset: 'Resetting...'
        target_past = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(format_reset_time(target_past), "Resetting...")

    def test_quota_cell_widget_rendering(self):
        """Xác nhận QuotaCellWidget hiển thị progress bar gradient, text trắng và dòng reset."""
        w = QuotaCellWidget(val=75, text="75%", is_valid=True, reset_text="Reset in 03:45")
        self.assertFalse(w.bar.isHidden())
        self.assertEqual(w.bar.width(), 38)
        self.assertEqual(w.lbl_percent.text(), "75%")
        self.assertIn("#ffffff", w.lbl_percent.styleSheet().lower())
        self.assertEqual(w.lbl_reset.text(), "Reset in 03:45")
        self.assertFalse(w.lbl_reset.isHidden())
        self.assertEqual(w.sizeHint().width(), 105)

        # Kiểm tra chế độ spinner
        w.set_spinner("⠋", QColor("#89b4fa"))
        self.assertTrue(w.bar.isHidden())
        self.assertTrue(w.lbl_reset.isHidden())
        self.assertEqual(w.lbl_percent.text(), "⠋")

    def test_update_row_quota_display_with_quota_cell_widget(self):
        """Xác nhận update_row_quota_display cập nhật chuẩn xác QuotaCellWidget trong bảng."""
        table = QTableWidget(1, 6)
        item_order = QTableWidgetItem("1")
        item_order.setData(Qt.ItemDataRole.UserRole, "prof_456")
        table.setItem(0, 0, item_order)

        w5 = QuotaCellWidget(val=0, text="--", is_valid=False)
        ww = QuotaCellWidget(val=0, text="--", is_valid=False)
        table.setCellWidget(0, 3, w5)
        table.setCellWidget(0, 4, ww)

        class DummyWin:
            def __init__(self, t):
                self.treeview = t
                self.refreshing_profile_ids = {"prof_456"}

        win = DummyWin(table)
        update_row_quota_display(
            win, "prof_456",
            85, "85%", True,
            42, "42%", True,
            q5_reset="Reset in 04:12",
            qw_reset="Reset in 5d 2h"
        )

        self.assertEqual(w5.lbl_percent.text(), "85%")
        self.assertEqual(w5.lbl_reset.text(), "Reset in 04:12")
        self.assertFalse(w5.bar.isHidden())
        self.assertEqual(w5.bar.val, 85)

        self.assertEqual(ww.lbl_percent.text(), "42%")
        self.assertEqual(ww.lbl_reset.text(), "Reset in 5d 2h")
        self.assertFalse(ww.bar.isHidden())
        self.assertEqual(ww.bar.val, 42)

    def test_parse_quota_summary_separates_gemini_and_argon_weekly(self):
        """Xác nhận Gemini Weekly không bị Argon Weekly ghi đè và Argon Weekly được tách riêng."""
        now = datetime.now(timezone.utc)
        reset_5h = (now + timedelta(hours=4, minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        reset_wk = (now + timedelta(days=5, hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
        reset_ag = (now + timedelta(days=6, hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "groups": [
                {
                    "displayName": "Gemini Models",
                    "buckets": [
                        {"bucketId": "gemini-weekly", "window": "weekly", "remainingFraction": 0.60, "resetTime": reset_wk},
                        {"bucketId": "gemini-5h", "window": "5h", "remainingFraction": 0.83, "resetTime": reset_5h},
                    ],
                },
                {
                    "displayName": "Claude and GPT models",
                    "buckets": [
                        {"bucketId": "3p-weekly", "window": "weekly", "remainingFraction": 0.90, "resetTime": reset_wk},
                    ],
                },
                {
                    "displayName": "Gemini 4 Argon",
                    "buckets": [
                        {"bucketId": "gemini-argon-wtu-weekly", "window": "weekly", "remainingFraction": 0.94, "resetTime": reset_ag},
                    ],
                },
            ]
        }

        q5_v, q5_t, q5_ok, q5_r, qw_v, qw_t, qw_ok, qw_r, qa_v, qa_t, qa_ok, qa_r = parse_quota_summary(payload)
        self.assertEqual((q5_v, q5_t, q5_ok), (83, "83%", True))
        self.assertEqual((qw_v, qw_t, qw_ok), (60, "60%", True))
        self.assertEqual((qa_v, qa_t, qa_ok), (94, "94%", True))
        self.assertEqual(qa_r, format_reset_time(reset_ag))

        # Tài khoản không có nhóm Argon riêng -> Argon trả về '--', False
        no_argon = {"groups": [payload["groups"][0]]}
        _, _, _, _, qw_v2, _, _, _, qa_v2, qa_t2, qa_ok2, qa_r2 = parse_quota_summary(no_argon)
        self.assertEqual(qw_v2, 60)
        self.assertEqual((qa_v2, qa_t2, qa_ok2, qa_r2), (0, "--", False, ""))

    def test_update_row_quota_display_7_columns_with_argon(self):
        """Xác nhận update_row_quota_display cập nhật đủ 3 cột Quota (5h, Weekly, Argon) và nút ở cột 6."""
        table = QTableWidget(1, 7)
        item_order = QTableWidgetItem("1")
        item_order.setData(Qt.ItemDataRole.UserRole, "prof_7col")
        table.setItem(0, 0, item_order)

        w5 = QuotaCellWidget()
        ww = QuotaCellWidget()
        wa = QuotaCellWidget()
        table.setCellWidget(0, 3, w5)
        table.setCellWidget(0, 4, ww)
        table.setCellWidget(0, 5, wa)

        btn_cell = QWidget()
        btn_layout = QHBoxLayout(btn_cell)
        btn = QPushButton("⠋")
        btn.setEnabled(False)
        btn_layout.addWidget(btn)
        table.setCellWidget(0, 6, btn_cell)

        class DummyWin:
            def __init__(self, t):
                self.treeview = t
                self.refreshing_profile_ids = {"prof_7col"}

        win = DummyWin(table)
        update_row_quota_display(
            win, "prof_7col",
            83, "83%", True,
            60, "60%", True,
            q5_reset="Reset in 04:30",
            qw_reset="Reset in 5d 18h",
            qa_val=94, qa_text="94%", qa_valid=True, qa_reset="Reset in 6d 1h"
        )

        self.assertEqual(w5.lbl_percent.text(), "83%")
        self.assertEqual(ww.lbl_percent.text(), "60%")
        self.assertEqual(wa.lbl_percent.text(), "94%")
        self.assertEqual(wa.lbl_reset.text(), "Reset in 6d 1h")
        self.assertFalse(wa.bar.isHidden())
        self.assertEqual(btn.text(), "⟳")
        self.assertTrue(btn.isEnabled())

if __name__ == "__main__":
    unittest.main()
