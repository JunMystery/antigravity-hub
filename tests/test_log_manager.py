# -*- coding: utf-8 -*-
"""
Unit tests for Log Manager: truncation, retention, pruning, and tag parsing.
"""

import os
import sys
import time
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "launcher")

import launcher_log_manager as lm

class TestLogManager(unittest.TestCase):
    """Kiểm tra toàn bộ chức năng quản lý log và lưu trữ."""

    def test_get_log_path(self):
        """Xác nhận đường dẫn proxy.log hợp lệ."""
        p = lm.get_log_path()
        self.assertTrue(p.endswith("proxy.log"))

    def test_clear_log(self):
        """Xác nhận clear_log làm rỗng file nhật ký."""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("line 1\nline 2\n")
            temp_path = tf.name

        try:
            with patch.object(lm, "LOG_FILE", temp_path):
                self.assertGreater(os.path.getsize(temp_path), 0)
                ok = lm.clear_log()
                self.assertTrue(ok)
                self.assertEqual(os.path.getsize(temp_path), 0)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_retention_days_get_and_set(self):
        """Xác nhận đọc/ghi cấu hình retention days."""
        mock_data = {"settings": {}}
        with patch("launcher_log_manager.load_data", return_value=mock_data), \
             patch("launcher_log_manager.save_data") as mock_save:
            lm.set_retention_days(7)
            self.assertEqual(mock_data["settings"]["log_retention_days"], 7)
            mock_save.assert_called_once_with(mock_data)

            self.assertEqual(lm.get_retention_days(), 7)

    def test_prune_logs(self):
        """Xác nhận prune_logs xóa file cũ quá hạn và giữ file mới."""
        with tempfile.TemporaryDirectory() as tmpdir:
            now = time.time()
            old_file = os.path.join(tmpdir, "proxy-old.log")
            new_file = os.path.join(tmpdir, "proxy-new.log")

            with open(old_file, "w") as f: f.write("old log")
            with open(new_file, "w") as f: f.write("new log")

            # Đặt mtime cho old_file là 40 ngày trước
            old_mtime = now - (40 * 86400)
            os.utime(old_file, (old_mtime, old_mtime))
            # new_file giữ nguyên mtime hiện tại
            os.utime(new_file, (now, now))

            with patch.object(lm, "LOGS_DIR", tmpdir):
                pruned = lm.prune_logs(retention_days=30)
                self.assertEqual(pruned, 1)
                self.assertFalse(os.path.exists(old_file))
                self.assertTrue(os.path.exists(new_file))

    def test_parse_log_lines(self):
        """Xác nhận bóc tách chính xác [MAIN] vs [SUBAGENT] từ các dòng log."""
        lines = [
            "[ROUND-ROBIN #1] [MAIN] GET /v1/models -> [ACC: user1@gmail.com] (1/1 req)",
            "[ROUND-ROBIN #2] [SUBAGENT] [STICKY] POST /v1/chat -> [ACC: user2@gmail.com] (1/1 req)",
            "Non-round-robin proxy listening on port 20130"
        ]
        parsed = lm.parse_log_lines(lines)
        self.assertEqual(len(parsed), 3)

        # Item 0: MAIN
        self.assertEqual(parsed[0]["req"], 1)
        self.assertEqual(parsed[0]["tag"], "MAIN")
        self.assertIn("GET /v1/models", parsed[0]["details"])

        # Item 1: SUBAGENT
        self.assertEqual(parsed[1]["req"], 2)
        self.assertEqual(parsed[1]["tag"], "SUBAGENT")
        self.assertIn("[STICKY]", parsed[1]["details"])

        # Item 2: GENERAL
        self.assertIsNone(parsed[2]["req"])
        self.assertEqual(parsed[2]["tag"], "GENERAL")

    def test_read_tail_lines_large_file(self):
        """Xác nhận read_tail_lines đọc đúng N dòng cuối mà không cần nạp toàn bộ tệp."""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
            for i in range(3000):
                tf.write(f"[12:00:00] [NOISE #{i}] sample proxy log payload line {i:04d}\n")
            temp_path = tf.name
        try:
            tail = lm.read_tail_lines(temp_path, max_lines=100)
            self.assertEqual(len(tail), 100)
            self.assertIn("2900", tail[0])
            self.assertIn("2999", tail[-1])
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_logs_view_indexes_full_100_records_with_noise(self):
        """Xác nhận LogsView lập chỉ mục đủ 100 bản ghi gần nhất ngay cả khi log xen kẽ nhiều dòng nhiễu."""
        from PyQt6.QtWidgets import QApplication
        import launcher_view_logs
        _app = QApplication.instance() or QApplication(["-platform", "offscreen"])

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
            for i in range(1, 121):
                for n in range(5):
                    tf.write(f"[12:00:00] [NOISE] background line {i}-{n}\n")
                tf.write(f"[12:00:01] [ROUND-ROBIN #{i}] [MAIN] POST [MODEL: gemini-2.5-flash] /v1 -> [ACC: u{i}@test.com] (1/1 req)\n")
                tf.write(f"[12:00:02] [TOKENS] [u{i}@test.com] Sent: {100 + i} | Recv: {20 + i} | Cached: {i}\n")
            temp_path = tf.name
        try:
            with patch.object(launcher_view_logs, "get_log_path", return_value=temp_path):
                view = launcher_view_logs.LogsView()
                self.assertEqual(view.table.rowCount(), 100)
                self.assertEqual(view.table.item(0, 2).text(), "u21@test.com")
                self.assertEqual(view.table.item(99, 2).text(), "u120@test.com")
                self.assertIn("220 / 140", view.table.item(99, 3).text())
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_compact_status_bar_skips_redundant_style_reapply(self):
        """Xác nhận CompactStatusBar bỏ qua cập nhật lặp lại khi trạng thái không đổi."""
        from PyQt6.QtWidgets import QApplication
        from launcher_widget import CompactStatusBar
        _app = QApplication.instance() or QApplication(["-platform", "offscreen"])

        bar = CompactStatusBar()
        with patch.object(bar.lbl_status, "setStyleSheet", wraps=bar.lbl_status.setStyleSheet) as spy:
            bar.set_state("● STANDBY", "#89b4fa", "20130", "u1@test.com", "1/5")
            bar.set_state("● STANDBY", "#89b4fa", "20130", "u1@test.com", "1/5")
            self.assertEqual(spy.call_count, 1)

    def test_monitor_tick_skips_when_hidden(self):
        """Xác nhận _on_monitor_tick bỏ qua poll Dashboard khi cửa sổ đang ẩn."""
        import launcher_window
        calls = []

        class _Dummy:
            stack = type("S", (), {"currentWidget": lambda self: "dash"})()
            view_dashboard = "dash"
            def isHidden(self): return True
            def isMinimized(self): return False
            def update_live_monitor(self): calls.append(1)

        launcher_window.LauncherWindow._on_monitor_tick(_Dummy())
        self.assertEqual(calls, [])

if __name__ == "__main__":
    unittest.main()
