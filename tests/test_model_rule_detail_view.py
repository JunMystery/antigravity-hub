# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER_DIR = os.path.join(ROOT_DIR, "launcher")
if LAUNCHER_DIR not in sys.path:
    sys.path.insert(0, LAUNCHER_DIR)

from PyQt6.QtWidgets import QApplication, QPushButton
from PyQt6.QtCore import Qt

app = QApplication.instance() or QApplication(["-platform", "offscreen"])


class TestModelRuleDetailViewAndSort(unittest.TestCase):
    def test_toggle_switch_compact_buttons_and_detail_dialog_search(self):
        from launcher_i18n import set_language
        from launcher_view_model_rules import ModelRulesView
        from launcher_toggle_switch import ToggleSwitch
        from launcher_item_list_dialog import ItemListDetailDialog
        from launcher_model_rule_formatter import build_rule_account_display_lines

        set_language("vi")
        fake_accs = [
            {"id": "a1", "email": "zoe@test.com", "enabled": False, "account": {}},
            {"id": "a2", "email": "amy@test.com", "enabled": True, "account": {}}
        ]

        class _FakeWin:
            data = {"settings": {"language": "vi", "model_rules": []}, "profiles": []}

        with patch("launcher_view_model_rules.collect_available_accounts", return_value=fake_accs), \
             patch("launcher_view_model_rules.discover_models_from_logs", return_value=["zeta-1", "alpha-2"]), \
             patch("launcher_view_model_rules.save_data"), \
             patch("launcher_view_model_rules.send_proxy_cmd"):
            view = ModelRulesView(_FakeWin())
            rule = {
                "id": "r1",
                "name": "VIP Pool",
                "patterns": ["zeta-model", "alpha-model", "beta-model"],
                "match_type": "contains",
                "strategy": "round_robin",
                "requests_per_account": 2,
                "fallback_to_global": True,
                "accounts": [{"id": "a1", "email": "zoe@test.com"}, {"id": "a2", "email": "amy@test.com"}],
                "enabled": True
            }
            view.add_or_update_rule(rule)

            sw_cell = view.tbl_rules.cellWidget(0, 1)
            sw = sw_cell.findChild(ToggleSwitch)
            self.assertIsNotNone(sw)
            self.assertTrue(sw.isChecked())
            sw.setChecked(False)
            self.assertFalse(_FakeWin.data["settings"]["model_rules"][0]["enabled"])

            self.assertEqual(view.tbl_rules.columnCount(), 5)
            pat_btn = view.tbl_rules.cellWidget(0, 2).findChild(QPushButton)
            acc_btn = view.tbl_rules.cellWidget(0, 4).findChild(QPushButton)
            self.assertEqual(pat_btn.text(), "VIP Pool (3 model)")
            self.assertIn("Chứa từ khóa", pat_btn.toolTip())
            self.assertEqual(view.tbl_rules.item(0, 3).text(), "RR (2 req)")
            self.assertEqual(acc_btn.text(), "2 tài khoản · Fallback")
            ctx_actions = view._build_rule_context_menu(0).actions()
            self.assertEqual(len(ctx_actions), 2)
            ctx_actions[1].trigger()
            self.assertEqual(len(_FakeWin.data["settings"]["model_rules"]), 0)
            view.add_or_update_rule(rule)

            lines = build_rule_account_display_lines(rule, fake_accs)
            self.assertEqual(lines, ["#1  zoe@test.com  [Deactive]", "#2  amy@test.com  [Hoạt động]"])

            view._on_scan_finished([
                {"id": "a1", "email": "zoe@test.com", "enabled": False, "models": ["zeta", "Alpha", "beta"]},
                {"id": "a2", "email": "amy@test.com", "enabled": True, "models": [], "error": "Timeout"}
            ])
            scan_btn = view.tbl_scan.cellWidget(0, 2).findChild(QPushButton)
            self.assertEqual(scan_btn.text(), "3 model")
            self.assertEqual(view.tbl_scan.item(1, 2).text(), "Timeout")
            self.assertEqual(view._collect_all_known_models(), ["Alpha", "alpha-2", "beta", "zeta", "zeta-1"])

            set_language("en")
            view.retranslate_ui()
            self.assertEqual(view.tbl_scan.cellWidget(0, 2).findChild(QPushButton).text(), "3 models")
            self.assertEqual(view.tbl_scan.item(1, 1).text(), "Active")
            set_language("vi")

            dlg = ItemListDetailDialog("Test", ["zeta", "Alpha", "beta"], subtitle="3 models")
            self.assertEqual(dlg.list_items.count(), 3)
            dlg.edit_search.setText("ALP")
            visible = [dlg.list_items.item(i).text() for i in range(dlg.list_items.count()) if not dlg.list_items.item(i).isHidden()]
            self.assertEqual(visible, ["Alpha"])
            dlg.close()

    def test_models_auto_sorted_az_and_stable_on_check(self):
        from launcher_model_discovery import discover_models_from_logs, _extract_model_ids_from_payload
        from launcher_model_selector import MultiModelSelector

        extracted = _extract_model_ids_from_payload({
            "models": {"zeta-pro": {}, "models/Alpha-1": {}, "claude-sonnet": {}}
        })
        self.assertEqual(extracted, ["Alpha-1", "claude-sonnet", "zeta-pro"])

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = os.path.join(tmp_dir, "proxy.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("[10:00:01] [MAIN] POST [MODEL: zeta-2] /v1\n")
                f.write("[10:00:02] [MAIN] POST [MODEL: alpha-1] /v1\n")
                f.write("[10:00:03] [MAIN] POST [MODEL: Beta-9] /v1\n")
            with patch("launcher_model_discovery.get_log_path", return_value=log_file):
                self.assertEqual(discover_models_from_logs(), ["alpha-1", "Beta-9", "zeta-2"])

        sel = MultiModelSelector(initial_patterns=["zeta-model"])
        acc = [{"id": "a1", "email": "u1@test.com"}]
        cache = {"u1@test.com": {"models": ["claude-opus", "Alpha-pro", "zeta-model"]}}
        sel.refresh_models(acc, cache)
        order_before = [sel.list_models.item(i).data(Qt.ItemDataRole.UserRole) for i in range(sel.list_models.count())]
        self.assertEqual(order_before, ["Alpha-pro", "claude-opus", "zeta-model"])
        sel.list_models.item(0).setCheckState(Qt.CheckState.Checked)
        order_after = [sel.list_models.item(i).data(Qt.ItemDataRole.UserRole) for i in range(sel.list_models.count())]
        self.assertEqual(order_after, order_before)


if __name__ == "__main__":
    unittest.main()
