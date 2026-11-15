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

if __name__ == "__main__":
    unittest.main()
