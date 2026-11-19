# -*- coding: utf-8 -*-
"""
Headless PyQt6 unit tests cho tính năng Tắt/Bật Round Robin & Đổi tài khoản trên UI.
Cô lập hoàn toàn khỏi %APPDATA% của người dùng bằng TemporaryDirectory.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "launcher"))

from PyQt6.QtWidgets import QApplication

import launcher_i18n
import launcher_storage
import launcher_view_dashboard
import launcher_window

app = QApplication.instance() or QApplication(["-platform", "offscreen"])


class TestAccountModeAndSwitcher(unittest.TestCase):
    """Kiểm thử đồng bộ Round Robin toggle, chọn tài khoản Dashboard/Accounts, Launch và i18n."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.tmp_dir, "config")
        self.profiles_base = os.path.join(self.tmp_dir, "profiles")
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.profiles_base, exist_ok=True)

        self.profiles_file = os.path.join(self.config_dir, "profiles.json")
        self.accounts_file = os.path.join(self.config_dir, "accounts.json")
        self.status_file = os.path.join(self.config_dir, "live_status.json")

        self.seed_profiles = {
            "settings": {
                "use_proxy": True,
                "round_robin_enabled": True,
                "auto_rotation_enabled": True,
                "active_account_id": "acc1_test_com",
                "requests_per_account": 5,
                "language": "vi",
                "shortcut_created": True,
                "hide_on_launch": "never",
                "close_action": "exit"
            },
            "profiles": [
                {
                    "id": "acc1_test_com",
                    "name": "acc1@test.com",
                    "email": "acc1@test.com",
                    "order": 1,
                    "enabled": True,
                    "data_dir": os.path.join(self.profiles_base, "acc1_test_com")
                },
                {
                    "id": "acc2_test_com",
                    "name": "acc2@test.com",
                    "email": "acc2@test.com",
                    "order": 2,
                    "enabled": True,
                    "data_dir": os.path.join(self.profiles_base, "acc2_test_com")
                },
                {
                    "id": "acc3_test_com",
                    "name": "acc3@test.com",
                    "email": "acc3@test.com",
                    "order": 3,
                    "enabled": False,
                    "data_dir": os.path.join(self.profiles_base, "acc3_test_com")
                }
            ]
        }
        with open(self.profiles_file, "w", encoding="utf-8") as f:
            json.dump(self.seed_profiles, f)
        with open(self.accounts_file, "w", encoding="utf-8") as f:
            json.dump({"accounts": []}, f)
        with open(self.status_file, "w", encoding="utf-8") as f:
            json.dump({
                "status": "standby",
                "paused": False,
                "account_email": "acc1@test.com",
                "current_req": 0,
                "requests_per_account": 5,
                "total_requests": 0
            }, f)

        self.sent_cmds = []

        def fake_send_cmd(win, cmd, params=None):
            self.sent_cmds.append((cmd, params))
            if cmd == "pause":
                self._write_status(paused=True, status="paused")
            elif cmd == "resume":
                self._write_status(paused=False, status="standby")
            elif cmd == "toggle_pause":
                cur_paused = False
                if os.path.exists(self.status_file):
                    with open(self.status_file, "r", encoding="utf-8") as sf:
                        cur_paused = bool(json.load(sf).get("paused", False))
                self._write_status(paused=not cur_paused, status="standby" if cur_paused else "paused")
            elif cmd == "select" and isinstance(params, dict):
                self._write_status(account_email=params.get("target", "acc1@test.com"))
            return True

        self.patchers = [
            patch.object(launcher_storage, "CONFIG_DIR", self.config_dir),
            patch.object(launcher_storage, "PROFILES_FILE", self.profiles_file),
            patch.object(launcher_storage, "ACCOUNTS_FILE", self.accounts_file),
            patch.object(launcher_storage, "PROFILES_BASE_DIR", self.profiles_base),
            patch.object(launcher_window, "PROFILES_BASE_DIR", self.profiles_base),
            patch.object(launcher_window, "STATUS_FILE", self.status_file),
            patch.object(launcher_view_dashboard, "STATUS_FILE", self.status_file),
            patch.object(launcher_window, "ensure_proxy_running", return_value=None),
            patch.object(launcher_window, "is_proxy_running", return_value=True),
            patch.object(launcher_view_dashboard, "is_proxy_running", return_value=True),
            patch.object(launcher_window, "send_proxy_cmd", side_effect=fake_send_cmd),
            patch.object(launcher_window, "create_desktop_shortcut", return_value=True),
            patch.object(launcher_window, "prune_logs", return_value=0),
            patch.object(launcher_window, "handle_hide_on_launch", return_value=None),
            patch.object(launcher_window, "handle_close_event", side_effect=lambda win, ev: ev.accept()),
            patch.object(launcher_window.LauncherWindow, "on_refresh_all_quota", return_value=None),
        ]
        for p in self.patchers:
            p.start()

        launcher_i18n.set_language("vi")
        self.win = launcher_window.LauncherWindow()

    def _write_status(self, **updates):
        with open(self.status_file, "r", encoding="utf-8") as f:
            cur = json.load(f)
        cur.update(updates)
        with open(self.status_file, "w", encoding="utf-8") as f:
            json.dump(cur, f)

    def tearDown(self):
        try:
            self.win.monitor_timer.stop()
            self.win.auto_quota_timer.stop()
            if hasattr(self.win, "tray") and self.win.tray:
                self.win.tray.tray_icon.hide()
            self.win.close()
        except Exception:
            pass
        for p in reversed(self.patchers):
            p.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_toggle_round_robin_two_way_sync_and_independent_auto_quota(self):
        # 1. Tat xoay vong tu tab Tai khoan
        self._write_status(current_req=4, requests_per_account=3)
        self.win.toggle_round_robin.setChecked(False)
        app.processEvents()

        self.assertFalse(self.win.data["settings"]["auto_rotation_enabled"])
        self.assertFalse(self.win.spin_reqs.isEnabled())
        self.assertIn(("pause", None), self.sent_cmds)
        # Khi tat round robin, cot Luot chi hien so request (khong hien /3)
        self.assertEqual(self.win.view_dashboard.status_bar.lbl_turn.text(), "4")
        self.assertEqual(self.win.view_dashboard.card_turn.lbl_value.text(), "4")
        self.assertEqual(self.win.view_dashboard.status_bar.lbl_turn_sub.text(), "Requests")
        # Khi dang gui request (status="sending", paused=True) nut phai giu nguyen "Tiep tuc" va co dinh width
        self._write_status(status="sending", paused=True, current_req=5, requests_per_account=3)
        self.win.update_live_monitor()
        self.assertEqual(self.win.btn_toggle_proxy.text(), "Tiếp tục")
        self.assertEqual(self.win.view_dashboard.status_bar.lbl_status.text(), "● ACTIVE")
        self.assertEqual(self.win.view_dashboard.status_bar.lbl_turn.text(), "5")
        self.assertGreaterEqual(self.win.view_dashboard.status_bar.lbl_status.minimumWidth(), 112)
        self.assertGreaterEqual(self.win.view_dashboard.status_bar.lbl_turn.minimumWidth(), 82)
        self.assertGreaterEqual(self.win.btn_toggle_proxy.minimumWidth(), 96)
        # Auto Refresh Quota (round_robin_enabled) phai doc lap, van True
        self.assertTrue(self.win.data["settings"]["round_robin_enabled"])
        self.assertTrue(self.win.auto_refresh_enabled)

        # 2. Bam Tiep tuc tren Dashboard -> phai dong bo nguoc lai ToggleSwitch & spin_reqs & 4/3
        self.win.on_toggle_proxy_btn()
        app.processEvents()

        self.assertIn(("toggle_pause", None), self.sent_cmds)
        self.assertTrue(self.win.data["settings"]["auto_rotation_enabled"])
        self.assertTrue(self.win.toggle_round_robin.isChecked())
        self.assertTrue(self.win.spin_reqs.isEnabled())
        self.assertEqual(self.win.view_dashboard.status_bar.lbl_turn.text(), "5/3")
        self.assertEqual(self.win.view_dashboard.status_bar.lbl_turn_sub.text(), "Current Turn")

        # Kiem tra luu xuong dia
        with open(self.profiles_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertTrue(saved["settings"]["auto_rotation_enabled"])

    def test_dashboard_dropdown_and_accounts_button_switch_and_launch_profile(self):
        # Chon acc2 tu Dropdown tren Dashboard
        idx_acc2 = self.win.combo_active_account.findData("acc2_test_com")
        self.assertGreaterEqual(idx_acc2, 0)
        self.win.combo_active_account.setCurrentIndex(idx_acc2)
        app.processEvents()

        self.assertEqual(self.win.data["settings"]["active_account_id"], "acc2_test_com")
        self.assertIn(("select", {"target": "acc2@test.com"}), self.sent_cmds)

        # Refresh khong truyen select_id va chuyen sang tab Tai khoan phai auto-select dung dong acc2
        self.win._refresh_list()
        self.win.switch_view("accounts")
        selected_rows = self.win.treeview.selectionModel().selectedRows()
        self.assertEqual(len(selected_rows), 1)
        self.assertEqual(selected_rows[0].row(), 1)
        self.assertTrue(self.win.treeview.item(1, 2).text().startswith("● "))
        self.assertFalse(self.win.treeview.item(0, 2).text().startswith("● "))

        # Launch phai dung dung data_dir cua acc2_test_com
        with patch.object(launcher_window, "launch_profile", return_value=True) as mock_launch:
            self.win.on_launch_app_clicked()
            mock_launch.assert_called_once_with(
                os.path.join(self.profiles_base, "acc2_test_com"),
                target="app",
                use_proxy=True
            )

        # Edge case: Chon dong acc3 dang bi tat (enabled=False) qua nut "Chon dung"
        self.win.treeview.selectRow(2)
        self.sent_cmds.clear()
        self.win.on_use_selected_account()
        app.processEvents()

        acc3 = next(p for p in self.win.data["profiles"] if p["id"] == "acc3_test_com")
        self.assertTrue(acc3["enabled"])
        self.assertEqual(self.win.data["settings"]["active_account_id"], "acc3_test_com")
        self.assertIn(("reload", None), self.sent_cmds)
        self.assertIn(("select", {"target": "acc3@test.com"}), self.sent_cmds)

    def test_empty_profiles_and_table_contract_and_retranslation(self):
        # Bao toan bang 7 cot (bao gom Argon Weekly)
        self.assertEqual(self.win.treeview.columnCount(), 7)

        # Retranslation EN <-> VI
        launcher_i18n.set_language("en")
        self.win.retranslate_ui()
        self.assertEqual(self.win.btn_use_account.text(), "Use Account")
        self.assertEqual(self.win.view_dashboard.lbl_active_acc.text(), "Active Account:")

        launcher_i18n.set_language("vi")
        self.win.retranslate_ui()
        self.assertEqual(self.win.btn_use_account.text(), "Chọn dùng")
        self.assertEqual(self.win.view_dashboard.lbl_active_acc.text(), "Tài khoản dùng:")

        # Edge case: danh sach rong khong crash
        self.win.data["profiles"] = []
        self.win.data["settings"]["active_account_id"] = ""
        self.win._refresh_list()
        self.win.on_use_selected_account()
        self.assertFalse(self.win.combo_active_account.isEnabled())
        self.assertFalse(self.win.btn_use_account.isEnabled())


if __name__ == "__main__":
    unittest.main()
