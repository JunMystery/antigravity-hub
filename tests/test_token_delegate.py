# -*- coding: utf-8 -*-
"""
Unit tests for TokenInOutDelegate and token string parsing.
"""

import sys
import unittest
sys.path.insert(0, "launcher")

from PyQt6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

from launcher_token_delegate import (
    parse_token_display_text,
    TokenInOutDelegate,
    COLOR_IN,
    COLOR_OUT,
    COLOR_CACHED,
    COLOR_SLASH,
    COLOR_MUTED
)

app = QApplication.instance() or QApplication(["-platform", "offscreen"])

class TestTokenInOutDelegate(unittest.TestCase):
    """Kiểm tra logic phân tích cú pháp token và Delegate vẽ màu In/Out/Cached."""

    def test_parse_token_display_text(self):
        # 1. Định dạng số kèm hậu tố k tự động chuyển sang số đầy đủ có dấu phẩy
        in_t, out_t, c_t = parse_token_display_text("184.2k / 91")
        self.assertEqual(in_t, "184,200")
        self.assertEqual(out_t, "91")
        self.assertEqual(c_t, "")

        # 2. Định dạng có Cached (+...) với hậu tố k
        in_t, out_t, c_t = parse_token_display_text("184.2k / 91 (+120k)")
        self.assertEqual(in_t, "184,200")
        self.assertEqual(out_t, "91")
        self.assertEqual(c_t, "(+120,000)")

        # 3. Định dạng log cũ có 3 chữ số thập phân và hậu tố K (như trong ảnh thực tế)
        in_t, out_t, c_t = parse_token_display_text("122.854K / 1.542K (+156.602K)")
        self.assertEqual(in_t, "122,854")
        self.assertEqual(out_t, "1,542")
        self.assertEqual(c_t, "(+156,602)")

        # 4. Định dạng số nguyên thuần tự động bổ sung dấu phẩy (000,000)
        in_t, out_t, c_t = parse_token_display_text("122854 / 1542 (+156602)")
        self.assertEqual(in_t, "122,854")
        self.assertEqual(out_t, "1,542")
        self.assertEqual(c_t, "(+156,602)")

        # 5. Định dạng triệu và tỉ có dấu phẩy
        in_t, out_t, c_t = parse_token_display_text("1000000 / 1000000000")
        self.assertEqual(in_t, "1,000,000")
        self.assertEqual(out_t, "1,000,000,000")
        self.assertEqual(c_t, "")

        # 6. Định dạng đã có sẵn dấu phẩy giữ nguyên chuẩn
        in_t, out_t, c_t = parse_token_display_text("122,854 / 1,542 (+156,602)")
        self.assertEqual(in_t, "122,854")
        self.assertEqual(out_t, "1,542")
        self.assertEqual(c_t, "(+156,602)")

        # 7. Định dạng rỗng hoặc phân cách -- / --
        in_t, out_t, c_t = parse_token_display_text("-- / --")
        self.assertEqual(in_t, "--")
        self.assertEqual(out_t, "--")
        self.assertEqual(c_t, "")

        # 8. Định dạng đơn lẻ không có slash
        in_t, out_t, c_t = parse_token_display_text("--")
        self.assertEqual(in_t, "--")
        self.assertEqual(out_t, "")
        self.assertEqual(c_t, "")

        # 9. Rỗng hoàn toàn
        in_t, out_t, c_t = parse_token_display_text("")
        self.assertEqual(in_t, "")
        self.assertEqual(out_t, "")
        self.assertEqual(c_t, "")

    def test_palette_color_definitions(self):
        """Xác nhận bảng màu chuẩn Catppuccin Peach, Green, Yellow, Gray."""
        self.assertEqual(COLOR_IN.name().lower(), "#f97316")
        self.assertEqual(COLOR_OUT.name().lower(), "#22c55e")
        self.assertEqual(COLOR_CACHED.name().lower(), "#f59e0b")
        self.assertEqual(COLOR_SLASH.name().lower(), "#6c7086")
        self.assertEqual(COLOR_MUTED.name().lower(), "#585b70")

    def test_delegate_attachment_and_rendering(self):
        """Xác nhận Delegate gắn vào QTableWidget và thực hiện paint mà không phát sinh ngoại lệ."""
        table = QTableWidget(2, 2)
        delegate = TokenInOutDelegate(table)
        table.setItemDelegateForColumn(1, delegate)
        self.assertIs(table.itemDelegateForColumn(1), delegate)

        table.setItem(0, 1, QTableWidgetItem("120k / 450 (+80k)"))
        table.setItem(1, 1, QTableWidgetItem("-- / --"))

        # Trigger layout and rendering event
        table.resize(400, 200)
        table.show()
        app.processEvents()

        # Kiểm tra index data vẫn nguyên vẹn để phục vụ copy/export
        self.assertEqual(table.item(0, 1).text(), "120k / 450 (+80k)")
        self.assertEqual(table.item(1, 1).text(), "-- / --")

    def test_delegate_size_hint(self):
        """Xác nhận sizeHint trả về độ rộng tối thiểu 240px khi có cache và 160px khi không cache."""
        from PyQt6.QtWidgets import QStyleOptionViewItem
        table = QTableWidget(2, 2)
        delegate = TokenInOutDelegate(table)
        table.setItem(0, 0, QTableWidgetItem("122854 / 1542 (+156602)"))
        table.setItem(1, 0, QTableWidgetItem("122854 / 123456"))

        opt = QStyleOptionViewItem()
        opt.fontMetrics = table.fontMetrics()

        idx_cached = table.model().index(0, 0)
        hint_cached = delegate.sizeHint(opt, idx_cached)
        self.assertGreaterEqual(hint_cached.width(), 240)

        idx_simple = table.model().index(1, 0)
        hint_simple = delegate.sizeHint(opt, idx_simple)
        self.assertGreaterEqual(hint_simple.width(), 160)

if __name__ == "__main__":
    unittest.main()
