# -*- coding: utf-8 -*-
"""
Kiểm thử toàn diện tính năng Theme Light/Dark/System, Header Lockup Dark/Light,
và sửa lỗi + sửa nhanh Priority trong Model Rules (Rules, Editor, Target Accounts Popup).
"""

import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER_DIR = os.path.join(ROOT_DIR, "launcher")
if LAUNCHER_DIR not in sys.path:
    sys.path.insert(0, LAUNCHER_DIR)

from PyQt6.QtWidgets import QApplication, QPushButton, QCheckBox
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPalette, QColor

import launcher_storage
import launcher_log_manager
import launcher_view_settings
import launcher_window
import launcher_theme
from launcher_window import LauncherWindow

app = QApplication.instance() or QApplication(["-platform", "offscreen"])


class TestThemeAndModelRulesUI(unittest.TestCase):
    """Đảm bảo đồng bộ Theme và đầy đủ tương tác trong Model Rules."""

    @classmethod
    def setUpClass(cls):
        cls._tmp_dir = tempfile.mkdtemp()
        cfg_dir = os.path.join(cls._tmp_dir, "config")
        prof_base = os.path.join(cls._tmp_dir, "profiles_base")
        os.makedirs(cfg_dir, exist_ok=True)
        patch_specs = [
            (launcher_storage, "CONFIG_DIR", cfg_dir),
            (launcher_storage, "PROFILES_FILE", os.path.join(cfg_dir, "profiles.json")),
            (launcher_storage, "ACCOUNTS_FILE", os.path.join(cfg_dir, "accounts.json")),
            (launcher_storage, "PROFILES_BASE_DIR", prof_base),
            (launcher_log_manager, "CONFIG_DIR", cfg_dir),
            (launcher_view_settings, "CONFIG_DIR", cfg_dir),
            (launcher_window, "PROFILES_BASE_DIR", prof_base),
        ]
        cls._patches = [patch.object(m, k, v) for m, k, v in patch_specs] + [
            patch.object(launcher_window, fn) for fn in ("ensure_proxy_running", "prune_logs", "create_desktop_shortcut")
        ]
        for p in cls._patches:
            p.start()
        cls.win = LauncherWindow()
        cls.win.monitor_timer.stop()
        cls.win.auto_quota_timer.stop()

    @classmethod
    def tearDownClass(cls):
        launcher_theme.apply_launcher_style(app, "dark")
        if hasattr(cls, "win") and cls.win:
            cls.win.close()
        for p in reversed(getattr(cls, "_patches", [])):
            p.stop()
        shutil.rmtree(getattr(cls, "_tmp_dir", ""), ignore_errors=True)

    def tearDown(self):
        launcher_theme.apply_theme_to_window(self.win, "dark")

    def test_theme_switching_system_dark_light_and_borderless_lockup(self):
        from launcher_i18n import set_language
        from launcher_quota_widget import QuotaCellWidget

        sidebar = self.win.sidebar
        self.assertIn("border: none", sidebar.logo_lockup.styleSheet())
        self.assertIn("background: transparent", sidebar.logo_lockup.styleSheet())
        self.assertFalse(sidebar.logo_lockup.pixmap().isNull())
        self.assertEqual(launcher_theme.get_active_theme(), "dark")

        # Chuyển sang Light qua combo ở chân Sidebar
        idx_light = sidebar.combo_theme.findData("light")
        self.assertGreaterEqual(idx_light, 0)
        sidebar.combo_theme.setCurrentIndex(idx_light)
        self.assertEqual(self.win.data["settings"]["theme"], "light")
        self.assertEqual(launcher_theme.get_active_theme(), "light")
        self.assertIn("#eff1f5", app.styleSheet())
        self.assertIn("#4c4f69", app.styleSheet())
        self.assertFalse(sidebar.logo_lockup.pixmap().isNull())

        # Kiểm tra ActivityLogsPanel & LogsView dùng màu chữ Light (không còn chữ trắng)
        act_panel = self.win.view_dashboard.activity_panel
        act_panel.update_logs([{"raw": "[ROUND-ROBIN #1] [MAIN] POST [MODEL: gemini-2.5] /v1 -> [ACC: a@b.com]"}])
        self.assertEqual(act_panel.table.item(0, 0).foreground().color().name().lower(), "#4c4f69")

        logs_view = self.win.view_logs
        logs_view._entries = [{"time": "10:00:00", "action": "gemini-2.5", "acc": "a@b.com", "tokens": "100 / 20"}]
        logs_view.refresh_theme()
        self.assertEqual(logs_view.table.item(0, 1).foreground().color().name().lower(), "#4c4f69")

        q_cell = QuotaCellWidget(val=80, text="80%", is_valid=True, reset_text="Reset in 01:00")
        self.assertIn("#4c4f69", q_cell.lbl_percent.styleSheet().lower())

        # Chuyển sang System (theo hệ điều hành Dark -> Light)
        with patch.object(launcher_theme, "detect_system_theme", return_value="dark"):
            sidebar.combo_theme.setCurrentIndex(sidebar.combo_theme.findData("system"))
            self.assertEqual(launcher_theme.get_theme_mode(), "system")
            self.assertEqual(launcher_theme.get_active_theme(), "dark")

        with patch.object(launcher_theme, "detect_system_theme", return_value="light"):
            launcher_theme.apply_theme_to_window(self.win, "system")
            self.assertEqual(launcher_theme.get_active_theme(), "light")

        # Retranslate giữ nguyên theme đã chọn
        set_language("en")
        self.win.retranslate_ui()
        self.assertEqual(sidebar.lbl_theme.text(), "Theme")
        self.assertEqual(sidebar.combo_theme.currentData(), "system")
        set_language("vi")
        self.win.retranslate_ui()

    def test_model_rules_column_widths_and_row_right_click(self):
        from launcher_order_widget import OrderCellWidget
        from launcher_toggle_switch import ToggleSwitch

        fake_accs = [
            {"id": "a1", "email": "one@test.com", "enabled": True, "account": {}},
            {"id": "a2", "email": "two@test.com", "enabled": False, "account": {}},
        ]
        rules = [
            {"id": "r1", "name": "Rule 1", "patterns": ["claude"], "match_type": "contains", "strategy": "priority", "accounts": fake_accs, "enabled": True},
            {"id": "r2", "name": "Rule 2", "patterns": ["gemini"], "match_type": "contains", "strategy": "priority", "accounts": fake_accs, "enabled": True},
        ]
        self.win.data["settings"]["model_rules"] = [dict(r) for r in rules]

        with patch("launcher_view_model_rules.collect_available_accounts", return_value=fake_accs), \
             patch("launcher_view_model_rules.discover_models_from_logs", return_value=[]):
            mv = self.win.view_model_rules
            mv.refresh_view()

            # Không che mép phải 2 cột Priority & On
            self.assertGreaterEqual(mv.tbl_rules.columnWidth(0), 72)
            self.assertGreaterEqual(mv.tbl_rules.columnWidth(1), 56)
            ord_w = mv.tbl_rules.cellWidget(0, 0)
            self.assertIsInstance(ord_w, OrderCellWidget)
            self.assertLessEqual(ord_w.sizeHint().width(), mv.tbl_rules.columnWidth(0))
            sw = mv.tbl_rules.cellWidget(0, 1).findChild(ToggleSwitch)
            self.assertIsNotNone(sw)
            self.assertLessEqual(sw.width() + 8, mv.tbl_rules.columnWidth(1))

            # Chuột phải trên mọi cột cellWidget (0, 1, 2, 4) và cột text (3) đều gọi đúng row
            captured = []
            with patch.object(mv, "_open_rule_menu_at", side_effect=lambda r, gpos: captured.append(r)):
                for col in (0, 1, 2, 4):
                    w = mv.tbl_rules.cellWidget(1, col)
                    w.customContextMenuRequested.emit(QPoint(4, 4))
                ord_w1 = mv.tbl_rules.cellWidget(1, 0)
                ord_w1.edit_num.customContextMenuRequested.emit(QPoint(2, 2))
                pat_btn = mv.tbl_rules.cellWidget(1, 2).findChild(QPushButton)
                pat_btn.customContextMenuRequested.emit(QPoint(2, 2))
                col3_rect = mv.tbl_rules.visualRect(mv.tbl_rules.model().index(1, 3))
                mv.tbl_rules.viewport().customContextMenuRequested.emit(col3_rect.center())

            self.assertEqual(captured, [1, 1, 1, 1, 1, 1, 1])

    def test_model_rules_quick_priority_ordering_in_all_three_places(self):
        from launcher_order_widget import OrderCellWidget
        from launcher_rule_account_picker import RuleAccountPicker
        from launcher_item_list_dialog import RuleAccountsPriorityDialog

        accs = [
            {"id": "a1", "email": "alpha@test.com", "enabled": True, "account": {}},
            {"id": "a2", "email": "beta@test.com", "enabled": True, "account": {}},
            {"id": "a3", "email": "gamma@test.com", "enabled": False, "account": {}},
        ]
        rules = [
            {"id": "r1", "name": "R1", "patterns": ["m1"], "match_type": "contains", "strategy": "priority", "accounts": list(accs), "enabled": True},
            {"id": "r2", "name": "R2", "patterns": ["m2"], "match_type": "contains", "strategy": "priority", "accounts": list(accs), "enabled": True},
            {"id": "r3", "name": "R3", "patterns": ["m3"], "match_type": "contains", "strategy": "priority", "accounts": list(accs), "enabled": True},
        ]
        self.win.data["settings"]["model_rules"] = rules

        # 1. Sửa nhanh thứ tự Rules bằng nhập số + ▲/▼
        with patch("launcher_view_model_rules.collect_available_accounts", return_value=accs), \
             patch("launcher_view_model_rules.discover_models_from_logs", return_value=[]), \
             patch("launcher_view_model_rules.save_data") as mock_save, \
             patch("launcher_view_model_rules.send_proxy_cmd") as mock_cmd:
            mv = self.win.view_model_rules
            mv.refresh_view()
            ord_last = mv.tbl_rules.cellWidget(2, 0)
            self.assertIsInstance(ord_last, OrderCellWidget)
            ord_last.edit_num.setText("1")
            ord_last.edit_num.editingFinished.emit()
            self.assertEqual([r["id"] for r in self.win.data["settings"]["model_rules"]], ["r3", "r1", "r2"])
            mv.tbl_rules.cellWidget(0, 0).btn_down.click()
            self.assertEqual([r["id"] for r in self.win.data["settings"]["model_rules"]], ["r1", "r3", "r2"])
            self.assertEqual(mock_save.call_count, 2)
            self.assertEqual(mock_cmd.call_count, 2)

        # 2. Sửa nhanh thứ tự Accounts trong ModelRuleEditorDialog (RuleAccountPicker)
        rule_edit = dict(rules[0])
        picker = RuleAccountPicker(accs, rule_edit)
        self.assertEqual(picker.table_accounts.columnCount(), 3)
        picker.table_accounts.cellWidget(2, 0).edit_num.setText("1")
        picker.table_accounts.cellWidget(2, 0).edit_num.editingFinished.emit()
        self.assertEqual([a["email"] for a in picker.get_selected_accounts()], ["gamma@test.com", "alpha@test.com", "beta@test.com"])
        picker.table_accounts.cellWidget(1, 0).btn_up.click()
        self.assertEqual([a["email"] for a in picker.get_selected_accounts()], ["alpha@test.com", "gamma@test.com", "beta@test.com"])
        chk0 = picker.table_accounts.cellWidget(0, 1).findChild(QCheckBox)
        chk0.setChecked(False)
        self.assertEqual([a["email"] for a in picker.get_selected_accounts()], ["gamma@test.com", "beta@test.com"])

        # 3. Sửa nhanh thứ tự Accounts ngay trong popup Target Accounts (tự lưu callback)
        reordered_calls = []
        popup_rule = {
            "id": "r_pop",
            "patterns": ["claude"],
            "strategy": "priority",
            "accounts": [{"id": "a1", "email": "alpha@test.com"}, {"id": "a2", "email": "beta@test.com"}, {"id": "a3", "email": "gamma@test.com"}],
        }
        dlg = RuleAccountsPriorityDialog(
            "Target Accounts", popup_rule, accs, subtitle="3 accounts", on_reordered=lambda: reordered_calls.append(True)
        )
        dlg.tbl_accounts.cellWidget(2, 0).edit_num.setText("1")
        dlg.tbl_accounts.cellWidget(2, 0).edit_num.editingFinished.emit()
        self.assertEqual([a["email"] for a in popup_rule["accounts"]], ["gamma@test.com", "alpha@test.com", "beta@test.com"])
        self.assertEqual(popup_rule["account_email"], "gamma@test.com")
        dlg.tbl_accounts.cellWidget(0, 0).btn_down.click()
        self.assertEqual([a["email"] for a in popup_rule["accounts"]], ["alpha@test.com", "gamma@test.com", "beta@test.com"])
        self.assertEqual(len(reordered_calls), 2)
        dlg.close()

    def test_gui_theme_audit_coverage_across_all_surfaces(self):
        from launcher_treeview_updater import get_quota_color
        from launcher_widget import MetricCard, BadgeLabel
        from launcher_quota_widget import QuotaCellWidget

        # 1. QPalette Window & PlaceholderText thay đổi giữa Dark và Light
        launcher_theme.apply_theme_to_window(self.win, "dark")
        self.assertEqual(app.palette().color(QPalette.ColorRole.Window).name().lower(), "#1e1e2e")
        self.assertEqual(app.palette().color(QPalette.ColorRole.PlaceholderText).name().lower(), "#6c7086")
        self.assertEqual(get_quota_color(10, True), "#f38ba8")
        self.assertEqual(get_quota_color(35, True), "#f9e2af")
        self.assertEqual(get_quota_color(75, True), "#a6e3a1")

        # 2. Nút Auto Quota không dùng inline màu cứng
        self.assertEqual(self.win.btn_auto.objectName(), "btn_auto")
        self.assertIn(self.win.btn_auto.property("auto_state"), ("on", "off"))
        self.assertEqual(self.win.btn_auto.styleSheet(), "")

        # 3. Chuẩn bị semantic status labels & custom widgets ở Dark trước khi chuyển sang Light
        launcher_theme.set_semantic_text(self.win.lbl_info, "Scanning...", "accent", bold=True)
        self.win.view_settings._set_status_msg(self.win.view_settings.lbl_log_status, "Cleared", True)
        launcher_theme.set_semantic_text(self.win.view_settings.grp_backup.lbl_status, "Backup OK", "green")
        m_card = MetricCard("Test", "10", parent=self.win)
        badge = BadgeLabel("ACTIVE", "active", parent=self.win)
        q_norm = QuotaCellWidget(val=80, text="80%", is_valid=True, parent=self.win)
        q_spin = QuotaCellWidget(val=0, text="--", is_valid=False, parent=self.win)
        q_spin.set_spinner("⠋", QColor("#89b4fa"))

        launcher_theme.apply_theme_to_window(self.win, "light")
        self.assertEqual(app.palette().color(QPalette.ColorRole.Window).name().lower(), "#eff1f5")
        self.assertEqual(app.palette().color(QPalette.ColorRole.PlaceholderText).name().lower(), "#8c8fa1")
        self.assertEqual(get_quota_color(10, True), "#d20f39")
        self.assertEqual(get_quota_color(35, True), "#df8e1d")
        self.assertEqual(get_quota_color(75, True), "#40a02b")

        self.assertIn("#1e66f5", self.win.lbl_info.text().lower())
        self.assertIn("#40a02b", self.win.view_settings.lbl_log_status.text().lower())
        self.assertIn("#40a02b", self.win.view_settings.grp_backup.lbl_status.text().lower())
        self.assertIn("#ffffff", m_card.styleSheet().lower())
        self.assertIn("#40a02b", badge.styleSheet().lower())
        self.assertIn("#4c4f69", q_norm.lbl_percent.styleSheet().lower())
        self.assertIn("#1e66f5", q_spin.lbl_percent.styleSheet().lower())

        # 4. Ghi đè bằng plain setText không bị semantic helper ghi đè ngược khi đổi theme
        self.win.lbl_info.setText("plain")
        launcher_theme.apply_theme_to_window(self.win, "dark")
        self.assertEqual(self.win.lbl_info.text(), "plain")
        m_card.deleteLater()
        badge.deleteLater()
        q_norm.deleteLater()
        q_spin.deleteLater()

        # 5. Quét tĩnh đảm bảo không còn mã hex hardcoded lạc hậu trong các module GUI
        forbidden_hexes = ("#27ae60", "#c0392b", "#2980b9", "#1e1e2e", "#181825", "#cdd6f4")
        for fname in os.listdir(LAUNCHER_DIR):
            if not fname.endswith(".py") or fname == "launcher_theme_qss.py":
                continue
            fpath = os.path.join(LAUNCHER_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read().lower()
            for hex_code in forbidden_hexes:
                self.assertNotIn(hex_code, content, f"Found hardcoded {hex_code} in {fname}")


if __name__ == "__main__":
    unittest.main()
