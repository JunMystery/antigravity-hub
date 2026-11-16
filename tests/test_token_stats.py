# -*- coding: utf-8 -*-
"""
Kiểm thử toàn diện cho Hệ thống Token Stats & Full Log (test_token_stats.py).
Kiểm tra trích xuất usageMetadata, gom nhóm bucket theo giờ, các khung thời gian 24h/7D/30D/All,
bảo toàn dữ liệu token khi xóa proxy.log, và các widget UI.
"""

import os
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from launcher.launcher_token_storage import (
    load_token_metrics,
    format_token_count,
    format_full_number,
    get_aggregated_tokens,
    get_token_metrics_path
)
from launcher.launcher_log_manager import clear_log


class TestTokenStorageAndAggregation(unittest.TestCase):
    """Kiểm tra logic lưu trữ và tổng hợp Token Metrics."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.metrics_file = os.path.join(self.test_dir, "token_metrics.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_format_token_count(self):
        self.assertEqual(format_token_count(0), "0")
        self.assertEqual(format_token_count(450), "450")
        self.assertEqual(format_token_count(1000), "1K")
        self.assertEqual(format_token_count(1250), "1.25K")
        self.assertEqual(format_token_count(1234), "1.234K")
        self.assertEqual(format_token_count(25400), "25.4K")
        self.assertEqual(format_token_count(1500000), "1.5M")
        self.assertEqual(format_token_count(1000000000), "1B")
        self.assertEqual(format_token_count(2500000000000), "2.5T")
        self.assertEqual(format_token_count(1000000000000000), "1Q")
        self.assertEqual(format_token_count(1000000000000000000), "1Qi")

    def test_format_full_number(self):
        self.assertEqual(format_full_number(0), "0")
        self.assertEqual(format_full_number(450), "450")
        self.assertEqual(format_full_number(1250), "1,250")
        self.assertEqual(format_full_number(1000000), "1,000,000")
        self.assertEqual(format_full_number(123456789012345), "123,456,789,012,345")

    def test_load_empty_or_missing_metrics(self):
        data = load_token_metrics(self.metrics_file)
        self.assertIn("lifetime", data)
        self.assertIn("hourly", data)
        self.assertEqual(data["lifetime"]["sent"], 0)

    def test_aggregation_timeframes(self):
        now = datetime.now(timezone.utc)
        h1 = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:00:00Z")
        h2 = (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:00:00Z")
        h3 = (now - timedelta(days=15)).strftime("%Y-%m-%dT%H:00:00Z")
        h4 = (now - timedelta(days=45)).strftime("%Y-%m-%dT%H:00:00Z")

        sample_data = {
            "lifetime": {
                "sent": 10000, "received": 2000, "cached": 5000, "total": 12000, "requests": 4
            },
            "hourly": {
                h1: {"s": 1000, "r": 200, "c": 500, "t": 1200, "n": 1},
                h2: {"s": 2000, "r": 400, "c": 1000, "t": 2400, "n": 1},
                h3: {"s": 3000, "r": 600, "c": 1500, "t": 3600, "n": 1},
                h4: {"s": 4000, "r": 800, "c": 2000, "t": 4800, "n": 1},
            }
        }

        # 1. 24h -> Chỉ tính h1
        agg_24h = get_aggregated_tokens("24h", sample_data, now_dt=now)
        self.assertEqual(agg_24h["sent"], 1000)
        self.assertEqual(agg_24h["received"], 200)
        self.assertEqual(agg_24h["cached"], 500)
        self.assertEqual(agg_24h["total"], 1200)
        self.assertEqual(agg_24h["requests"], 1)
        self.assertAlmostEqual(agg_24h["cache_ratio"], 33.3, places=1)

        # 2. 7D -> Tính h1 + h2
        agg_7d = get_aggregated_tokens("7d", sample_data, now_dt=now)
        self.assertEqual(agg_7d["sent"], 3000)
        self.assertEqual(agg_7d["received"], 600)
        self.assertEqual(agg_7d["cached"], 1500)
        self.assertEqual(agg_7d["requests"], 2)

        # 3. 30D -> Tính h1 + h2 + h3 (bỏ qua h4)
        agg_30d = get_aggregated_tokens("30d", sample_data, now_dt=now)
        self.assertEqual(agg_30d["sent"], 6000)
        self.assertEqual(agg_30d["received"], 1200)
        self.assertEqual(agg_30d["cached"], 3000)
        self.assertEqual(agg_30d["requests"], 3)

        # 4. All time -> Lấy từ lifetime
        agg_all = get_aggregated_tokens("all", sample_data, now_dt=now)
        self.assertEqual(agg_all["sent"], 10000)
        self.assertEqual(agg_all["received"], 2000)
        self.assertEqual(agg_all["cached"], 5000)
        self.assertEqual(agg_all["total"], 12000)
        self.assertEqual(agg_all["requests"], 4)

    def test_token_stats_preserved_when_clear_log_called(self):
        """Đảm bảo xóa log không ảnh hưởng đến dữ liệu token_metrics.json."""
        log_file = os.path.join(self.test_dir, "proxy.log")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("Some dummy proxy log lines\n")

        token_file = os.path.join(self.test_dir, "token_metrics.json")
        token_payload = {
            "lifetime": {"sent": 5000, "received": 1000, "cached": 2000, "total": 6000, "requests": 2},
            "hourly": {}
        }
        with open(token_file, "w", encoding="utf-8") as f:
            json.dump(token_payload, f)

        # Mock LOG_FILE sang temp dir
        with patch("launcher.launcher_log_manager.LOG_FILE", log_file):
            self.assertTrue(clear_log())
            self.assertEqual(os.path.getsize(log_file), 0)

        # Kiểm tra token_metrics.json vẫn nguyên vẹn
        persisted = load_token_metrics(token_file)
        self.assertEqual(persisted["lifetime"]["sent"], 5000)
        self.assertEqual(persisted["lifetime"]["cached"], 2000)


class TestTokenWidgets(unittest.TestCase):
    """Kiểm tra khởi tạo và hành vi cơ bản của UI widgets."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        import sys
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_token_metrics_bar_creation_and_switch(self):
        from launcher.launcher_token_widget import TokenMetricsBar
        bar = TokenMetricsBar()
        self.assertEqual(bar.active_timeframe, "24h")
        self.assertEqual(bar.card_sent.height(), 48)
        self.assertEqual(bar.card_recv.height(), 48)
        self.assertEqual(bar.card_cached.height(), 48)

        # Kiểm tra kích thước cố định và nhãn in hoa 24H, 7D, 30D, ALL
        for btn in bar._buttons.values():
            self.assertEqual(btn.width(), 48)
            self.assertEqual(btn.height(), 22)
        self.assertEqual(bar._buttons["24h"].text(), "24H")
        self.assertEqual(bar._buttons["7d"].text(), "7D")
        self.assertEqual(bar._buttons["30d"].text(), "30D")
        self.assertEqual(bar._buttons["all"].text(), "ALL")

        bar.set_timeframe("7d")
        self.assertEqual(bar.active_timeframe, "7d")

        bar.set_timeframe("30d")
        self.assertEqual(bar.active_timeframe, "30d")

        bar.set_timeframe("all")
        self.assertEqual(bar.active_timeframe, "all")

    def test_node_extract_usage_metadata_cached(self):
        """Kiểm tra extractUsageMetadata trong proxy bắt được cached tokens cả camelCase và snake_case."""
        import subprocess
        node_script = """
        const { extractUsageMetadata } = require('./proxy/token_tracker');
        const text1 = 'data: {"usageMetadata":{"promptTokenCount":150000,"candidatesTokenCount":450,"cachedContentTokenCount":120000,"totalTokenCount":150450}}';
        const res1 = extractUsageMetadata(text1);
        if (!res1 || res1.cached !== 120000 || res1.received !== 450) process.exit(1);

        const text2 = '{"usage_metadata":{"prompt_token_count":100000,"candidates_token_count":300,"cached_content_token_count":80000,"total_token_count":100300}}';
        const res2 = extractUsageMetadata(text2);
        if (!res2 || res2.cached !== 80000 || res2.received !== 300) process.exit(2);

        process.exit(0);
        """
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        proc = subprocess.run(["node", "-e", node_script], cwd=repo_root)
        self.assertEqual(proc.returncode, 0)

    def test_full_log_dialog_creation(self):
        from launcher.launcher_full_log_dialog import FullLogDialog
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("2026-11-16 10:00:00 [MAIN] POST streamGenerateContent -> ok\n")
            tf.write("2026-11-16 10:01:00 [TOKENS] Sent: 1.2k | Recv: 300 | Cached: 800\n")
            temp_path = tf.name

        try:
            with patch("launcher.launcher_full_log_dialog.get_log_path", return_value=temp_path):
                dlg = FullLogDialog()
                self.assertIn("streamGenerateContent", dlg.log_viewer.toPlainText())

                # Test lọc tìm kiếm
                dlg._filter_logs("TOKENS")
                self.assertIn("Sent: 1.2k", dlg.log_viewer.toPlainText())
                self.assertNotIn("streamGenerateContent", dlg.log_viewer.toPlainText())
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_activity_logs_panel_50_limit(self):
        from launcher.launcher_activity_widget import ActivityLogsPanel, MAX_RECENT_LOGS
        self.assertEqual(MAX_RECENT_LOGS, 50)
        panel = ActivityLogsPanel()
        dummy_logs = [{"details": f"req {i}", "timestamp": "12:00:00"} for i in range(70)]
        panel.update_logs(dummy_logs)
        self.assertEqual(panel.table.rowCount(), 50)

    def test_dashboard_size_policies_for_scaling(self):
        from PyQt6.QtWidgets import QSizePolicy
        from launcher.launcher_token_widget import TokenMetricsBar
        bar = TokenMetricsBar()
        self.assertEqual(bar.sizePolicy().verticalPolicy(), QSizePolicy.Policy.Fixed)
        self.assertEqual(bar.card_sent.sizePolicy().verticalPolicy(), QSizePolicy.Policy.Fixed)
        self.assertEqual(bar.card_sent.height(), 48)

    def test_locked_minimum_sizes(self):
        from launcher.launcher_window import LauncherWindow
        from launcher.launcher_full_log_dialog import FullLogDialog
        win = LauncherWindow()
        self.assertEqual(win.minimumWidth(), 760)
        self.assertEqual(win.minimumHeight(), 480)

        dlg = FullLogDialog()
        self.assertEqual(dlg.minimumWidth(), 600)
        self.assertEqual(dlg.minimumHeight(), 400)

    def test_no_decorative_emojis(self):
        from launcher.launcher_token_widget import TokenMetricsBar
        from launcher.launcher_full_log_dialog import FullLogDialog
        from launcher.launcher_activity_widget import ActivityLogsPanel
        bar = TokenMetricsBar()
        self.assertNotIn("⚡", bar.lbl_bar_title.text())
        panel = ActivityLogsPanel()
        self.assertNotIn("📜", panel.lbl_panel_title.text())
        dlg = FullLogDialog()
        self.assertNotIn("📋", dlg.btn_copy.text())
        self.assertNotIn("🔍", dlg.txt_search.placeholderText())


if __name__ == "__main__":
    unittest.main()
