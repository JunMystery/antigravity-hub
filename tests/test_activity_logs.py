# -*- coding: utf-8 -*-
"""
Unit tests for ActivityLogsPanel, 20-item rolling cap, format_compact_details, and CompactStatusBar.
"""

import sys
import unittest
sys.path.insert(0, "launcher")

from PyQt6.QtWidgets import QApplication, QHeaderView
from PyQt6.QtCore import Qt

from launcher_activity_widget import ActivityLogsPanel, format_compact_details
from launcher_widget import BadgeLabel, MetricCard, CompactStatusBar

app = QApplication.instance() or QApplication(["-platform", "offscreen"])

class TestActivityLogs(unittest.TestCase):
    """Kiểm tra chuyên sâu ActivityLogsPanel tinh gọn 1 bảng, giới hạn 20 dòng và định dạng compact."""

    def setUp(self):
        self.panel = ActivityLogsPanel()

    def test_activity_panel_structure(self):
        """Xác nhận panel có 1 bảng duy nhất, 2 cột (Time, Request Details) và các thuộc tính tương thích."""
        tbl = self.panel.table
        self.assertEqual(tbl.columnCount(), 2)
        hdr = tbl.horizontalHeader()
        self.assertEqual(hdr.sectionResizeMode(0), QHeaderView.ResizeMode.ResizeToContents)
        self.assertEqual(hdr.sectionResizeMode(1), QHeaderView.ResizeMode.Stretch)

        # Kiểm tra thuộc tính tương thích ngược
        self.assertIs(self.panel.table_feed, tbl)
        self.assertIs(self.panel.table_chat, tbl)
        self.assertIs(self.panel.table_subagent, tbl)

    def test_activity_log_20_rolling_cap(self):
        """Xác nhận giới hạn tối đa 20 dòng gần nhất cho bảng feed duy nhất."""
        logs = []
        for i in range(50):
            logs.append({
                "req": i + 1,
                "tag": "MAIN",
                "timestamp": f"10:00:{i:02d}",
                "details": f"POST v1internal:streamGenerateContent -> [ACC: user{i}@gmail.com]"
            })

        self.panel.update_logs(logs)

        # Bảng phải được giới hạn chặt chẽ ở 20 dòng
        self.assertEqual(self.panel.table.rowCount(), 20)

        # Dòng đầu tiên là log #31 (index 30), dòng cuối cùng là log #50 (index 49)
        first_detail = self.panel.table.item(0, 1).text()
        last_detail = self.panel.table.item(19, 1).text()
        self.assertEqual(first_detail, "POST streamGenerateContent → user30@gmail.com")
        self.assertEqual(last_detail, "POST streamGenerateContent → user49@gmail.com")

    def test_compact_details_formatter(self):
        """Xác nhận định dạng chi tiết log tinh gọn: [Endpoint/Action] → [Email], bỏ (N/M req)."""
        raw1 = "[MAIN] POST v1internal:streamGenerateContent (1/10 req) -> [ACC: business.junm@gmail.com]"
        self.assertEqual(format_compact_details(raw1), "POST streamGenerateContent → business.junm@gmail.com")

        raw2 = "[STICKY] [SUBAGENT] GET v1beta:models -> [ACC: darkzeuslk@gmail.com]"
        self.assertEqual(format_compact_details(raw2), "GET models → darkzeuslk@gmail.com")

        raw3 = "[AUTH-REFRESH] [OK] Đã tự động cấp mới Token từ Google cho: darkzeuslk@gmail.com"
        self.assertEqual(format_compact_details(raw3), "Refresh Token → darkzeuslk@gmail.com [OK]")

        raw4 = "[AUTH-PERSIST] [SAVE] Đã mã hóa và lưu Access Token mới cho: darkzeuslk@gmail.com"
        self.assertEqual(format_compact_details(raw4), "Lưu Token → darkzeuslk@gmail.com [OK]")

    def test_compact_status_bar(self):
        """Xác nhận CompactStatusBar hiển thị liền khối và format trạng thái chuẩn."""
        bar = CompactStatusBar()
        self.assertEqual(bar.height(), 68)
        bar.set_state("● STANDBY", "#89b4fa", "20130", "test@gmail.com", "4/10", "Lượt")
        self.assertEqual(bar.lbl_status.text(), "● STANDBY")
        self.assertEqual(bar.lbl_acc.text(), "test@gmail.com")
        self.assertEqual(bar.lbl_turn.text(), "4/10")

    def test_badge_label_color_map(self):
        """Xác nhận BadgeLabel có đủ color map cho general, main, subagent."""
        self.assertIn("general", BadgeLabel.COLOR_MAP)
        self.assertIn("main", BadgeLabel.COLOR_MAP)
        self.assertIn("subagent", BadgeLabel.COLOR_MAP)

        badge_gen = BadgeLabel("[GENERAL]", "general")
        self.assertEqual(badge_gen.text(), "[GENERAL]")

    def test_metric_card_fixed_height_and_styling(self):
        """Xác nhận MetricCard có chiều cao cố định 70px và nền nâng cao #24273a."""
        card = MetricCard("Active", "● STANDBY", "Port 20130")
        self.assertEqual(card.maximumHeight(), 70)
        self.assertEqual(card.minimumHeight(), 70)
        self.assertIn("#24273a", card.styleSheet())
        self.assertIn("#363a4f", card.styleSheet())

if __name__ == "__main__":
    unittest.main()
