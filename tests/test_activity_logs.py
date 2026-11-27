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
        """Xác nhận panel có 1 bảng duy nhất, 3 cột (Model, In / Out, When) và các thuộc tính tương thích."""
        tbl = self.panel.table
        self.assertEqual(tbl.columnCount(), 3)
        from launcher_token_delegate import TokenInOutDelegate
        self.assertIsInstance(tbl.itemDelegateForColumn(1), TokenInOutDelegate)
        hdr = tbl.horizontalHeader()
        self.assertEqual(hdr.sectionResizeMode(0), QHeaderView.ResizeMode.Stretch)
        self.assertEqual(hdr.sectionResizeMode(1), QHeaderView.ResizeMode.Interactive)
        self.assertEqual(tbl.columnWidth(1), 240)
        self.assertEqual(hdr.sectionResizeMode(2), QHeaderView.ResizeMode.ResizeToContents)

        # Kiểm tra thuộc tính tương thích ngược
        self.assertIs(self.panel.table_feed, tbl)
        self.assertIs(self.panel.table_chat, tbl)
        self.assertIs(self.panel.table_subagent, tbl)

    def test_activity_log_50_rolling_cap(self):
        """Xác nhận giới hạn tối đa 50 dòng gần nhất cho bảng Dashboard 3 cột."""
        logs = []
        for i in range(70):
            logs.append({
                "req": i + 1,
                "tag": "MAIN",
                "timestamp": f"10:00:{i:02d}",
                "details": f"POST v1internal:streamGenerateContent -> [ACC: user{i}@gmail.com]"
            })

        self.panel.update_logs(logs)

        # Bảng phải được giới hạn chặt chẽ ở 50 dòng
        self.assertEqual(self.panel.table.rowCount(), 50)

        # Dòng đầu tiên là log #21 (index 20), dòng cuối cùng là log #70 (index 69)
        first_model = self.panel.table.item(0, 0).text()
        first_when = self.panel.table.item(0, 2).text()
        last_model = self.panel.table.item(49, 0).text()
        last_when = self.panel.table.item(49, 2).text()
        self.assertEqual(first_model, "streamGenerateContent")
        self.assertEqual(first_when, "10:00:20")
        self.assertEqual(last_model, "streamGenerateContent")
        self.assertEqual(last_when, "10:00:69")

    def test_token_correlation_on_dashboard(self):
        """Xác nhận log [TOKENS] tự động cập nhật vào cột In / Out của request gần nhất."""
        logs = [
            {
                "req": 1,
                "tag": "MAIN",
                "timestamp": "12:00:01",
                "details": "POST v1internal:streamGenerateContent -> [ACC: test@gmail.com]"
            },
            {
                "req": None,
                "tag": "GENERAL",
                "timestamp": "12:00:03",
                "raw": "[TOKENS] [test@gmail.com] Sent: 1.8K | Recv: 420 | Cached: 1.2K"
            }
        ]
        self.panel.update_logs(logs)
        self.assertEqual(self.panel.table.rowCount(), 1)
        self.assertEqual(self.panel.table.item(0, 0).text(), "streamGenerateContent")
        self.assertEqual(self.panel.table.item(0, 1).text(), "1.8K / 420")
        self.assertEqual(self.panel.table.item(0, 2).text(), "12:00:01")

    def test_model_name_extraction_from_model_tag(self):
        """Xác nhận tên Model được trích xuất ưu tiên từ tag [MODEL: ...]."""
        logs = [
            {
                "req": 1,
                "tag": "MAIN",
                "timestamp": "12:00:01",
                "details": "POST [MODEL: gemini-2.5-pro] /v1internal:streamGenerateContent -> [ACC: test@gmail.com]"
            }
        ]
        self.panel.update_logs(logs)
        self.assertEqual(self.panel.table.rowCount(), 1)
        self.assertEqual(self.panel.table.item(0, 0).text(), "gemini-2.5-pro")

    def test_dashboard_filters_out_system_noise(self):
        """Xác nhận Dashboard chỉ hiển thị AI Log và loại bỏ 100% log hệ thống/abort/restore/refresh/save token."""
        logs = [
            {"raw": "[13:47:12] [CLIENT-ABORT] Client IDE da dong ket noi som."},
            {"raw": "[13:47:12] [UPSTREAM-ERR] Loi ket noi Google: socket hang up"},
            {"raw": "[13:47:23] [ROTATOR-RESTORE] [OK] Khoi phuc tai khoan: [user@gmail.com]"},
            {"raw": "[13:47:23] "},
            {"raw": "[15:10:23] [AUTH-REFRESH] [OK] Đã tự động cấp mới Token từ Google cho: user@gmail.com"},
            {"raw": "[15:10:23] [AUTH-PERSIST] [SAVE] Đã mã hóa và lưu Access Token mới cho [user@gmail.com] vào accounts.json"},
            {"details": "Refresh Token -> user@gmail.com", "timestamp": "15:10:24"},
            {"details": "Lưu Token -> user@gmail.com", "timestamp": "15:10:24"},
            {"raw": "[ROUND-ROBIN #1] [MAIN] POST [MODEL: gemini-3.8-flash] /v1internal:streamGenerateContent -> [ACC: user@gmail.com]"}
        ]
        self.panel.update_logs(logs)
        self.assertEqual(self.panel.table.rowCount(), 1)
        self.assertEqual(self.panel.table.item(0, 0).text(), "gemini-3.8-flash")

    def test_compact_details_formatter(self):
        """Xác nhận định dạng chi tiết log tinh gọn: [Endpoint/Action] → [Email], bỏ (N/M req)."""
        raw1 = "[MAIN] POST v1internal:streamGenerateContent (1/10 req) -> [ACC: main-user@example.com]"
        self.assertEqual(format_compact_details(raw1), "POST streamGenerateContent → main-user@example.com")

        raw2 = "[STICKY] [SUBAGENT] GET v1beta:models -> [ACC: sub-user@example.com]"
        self.assertEqual(format_compact_details(raw2), "GET models → sub-user@example.com")

        raw3 = "[AUTH-REFRESH] [OK] Đã tự động cấp mới Token từ Google cho: sub-user@example.com"
        self.assertEqual(format_compact_details(raw3), "Refresh Token → sub-user@example.com [OK]")

        raw4 = "[AUTH-PERSIST] [SAVE] Đã mã hóa và lưu Access Token mới cho: sub-user@example.com"
        self.assertEqual(format_compact_details(raw4), "Lưu Token → sub-user@example.com [OK]")

    def test_compact_status_bar(self):
        """Xác nhận CompactStatusBar hiển thị liền khối, làm nổi bật tài khoản và format trạng thái chuẩn."""
        bar = CompactStatusBar()
        self.assertEqual(bar.height(), 60)
        self.assertFalse(bar.lbl_acc.isHidden())
        bar.set_state("● STANDBY", "#89b4fa", "20130", "test@gmail.com", "4/10", "Lượt", acc_color="#f9e2af")
        self.assertEqual(bar.lbl_status.text(), "● STANDBY")
        self.assertEqual(bar.lbl_acc.text(), "test@gmail.com")
        self.assertIn("#f9e2af", bar.lbl_acc.styleSheet())
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
