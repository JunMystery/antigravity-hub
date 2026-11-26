# -*- coding: utf-8 -*-
import os
import json
import subprocess
import unittest
from unittest.mock import patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROXY_DIR = os.path.join(ROOT_DIR, "proxy")


def run_node(script_body: str):
    env = os.environ.copy()
    env["PROXY_DIR"] = PROXY_DIR.replace("\\", "/")
    res = subprocess.run(["node", "-e", script_body], cwd=ROOT_DIR, env=env, capture_output=True, text=True, check=True)
    lines = [ln.strip() for ln in res.stdout.strip().splitlines() if ln.strip()]
    return json.loads(lines[-1])


class TestAdvancedModelRules(unittest.TestCase):
    def test_match_types_priority_and_invalid_regex_resilience(self):
        code = r"""
        const path = require("node:path");
        const { AccountRotator } = require(path.join(process.env.PROXY_DIR, "account_rotator"));
        const { sanitizeModelRules } = require(path.join(process.env.PROXY_DIR, "rotator_state_loader"));
        const r = new AccountRotator({});
        r.allAccounts = [
          { id: "a1", email: "vip1@test.com", enabled: false, accessToken: "t1" },
          { id: "a2", email: "vip2@test.com", enabled: true, accessToken: "t2" },
          { id: "a3", email: "std@test.com", enabled: true, accessToken: "t3" }
        ];
        r.accounts = [r.allAccounts[1], r.allAccounts[2]];
        r.modelRules = sanitizeModelRules([
          { pattern: "[invalid-regex", match_type: "regex", accounts: [{ email: "std@test.com" }] },
          { pattern: "^gemini-2\\.5-(pro|flash)$", match_type: "regex", accounts: [{ email: "vip1@test.com" }] },
          { pattern: "claude-opus-4", match_type: "exact", accounts: [{ email: "vip2@test.com" }] },
          { pattern: "claude", match_type: "contains", accounts: [{ email: "std@test.com" }] }
        ]);
        const rx = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "gemini-2.5-pro" })));
        const ex = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "claude-opus-4" })));
        const ct = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "claude-sonnet-4" })));
        console.log(JSON.stringify({ rx: rx.account.email, ex: ex.account.email, ct: ct.account.email }));
        """
        out = run_node(code)
        self.assertEqual(out["rx"], "vip1@test.com")
        self.assertEqual(out["ex"], "vip2@test.com")
        self.assertEqual(out["ct"], "std@test.com")

    def test_intra_rule_failover_and_fallback_scope(self):
        code = r"""
        const path = require("node:path");
        const { pickNextRuleAccount, allocateForModelRule } = require(path.join(process.env.PROXY_DIR, "model_rule_engine"));
        const { sanitizeModelRules } = require(path.join(process.env.PROXY_DIR, "rotator_state_loader"));
        const pool = [
          { id: "a1", email: "u1@test.com", enabled: false },
          { id: "a2", email: "u2@test.com", enabled: true },
          { id: "a3", email: "u3@test.com", enabled: true }
        ];
        const rules = sanitizeModelRules([
          { pattern: "opus", strategy: "priority", fallback_to_global: false, accounts: [{ email: "u1@test.com" }, { email: "u2@test.com" }] },
          { pattern: "flex", strategy: "priority", fallback_to_global: true, accounts: [{ email: "u1@test.com" }] }
        ]);
        const strict = allocateForModelRule("claude-opus", rules, pool, new Map());
        const triedStrict = [strict.account];
        pool[0].unhealthyUntil = Date.now() + 60000;
        const step1 = pickNextRuleAccount(strict.rulePool, triedStrict, strict.fallbackToGlobal, () => pool[2]);
        pool[1].unhealthyUntil = Date.now() + 60000;
        const step2 = pickNextRuleAccount(strict.rulePool, triedStrict, strict.fallbackToGlobal, () => pool[2]);

        const flex = allocateForModelRule("flex-pro", rules, pool, new Map());
        let gIdx = 0;
        const globalPool = [pool[0], pool[1], pool[2]];
        const mockGlobalNext = (prevFailed) => {
          const cur = globalPool[gIdx % globalPool.length];
          if (!prevFailed || cur.email !== prevFailed.email) return cur;
          gIdx = (gIdx + 1) % globalPool.length;
          return globalPool[gIdx];
        };
        const flexSkipTried = pickNextRuleAccount([pool[0], pool[1]], [pool[0], pool[1]], true, mockGlobalNext);
        console.log(JSON.stringify({
          first: strict.account.email, step1: step1?.email || null, step2: step2?.email || null,
          flexAllocNull: flex === null, flexDirect: flexSkipTried?.email || null
        }));
        """
        out = run_node(code)
        self.assertEqual(out["first"], "u1@test.com")
        self.assertEqual(out["step1"], "u2@test.com")
        self.assertIsNone(out["step2"])
        self.assertTrue(out["flexAllocNull"])
        self.assertEqual(out["flexDirect"], "u3@test.com")

    def test_rule_group_round_robin_and_legacy_compat(self):
        code = r"""
        const path = require("node:path");
        const { AccountRotator } = require(path.join(process.env.PROXY_DIR, "account_rotator"));
        const { sanitizeModelRules } = require(path.join(process.env.PROXY_DIR, "rotator_state_loader"));
        const r = new AccountRotator({});
        r.allAccounts = [
          { id: "a1", email: "g1@test.com", enabled: false, accessToken: "t1" },
          { id: "a2", email: "g2@test.com", enabled: true, accessToken: "t2" }
        ];
        r.accounts = [r.allAccounts[1]];
        r.modelRules = sanitizeModelRules([
          { id: "rr1", pattern: "gemini", strategy: "round_robin", accounts: [{ email: "g1@test.com" }, { email: "g2@test.com" }] },
          { pattern: "legacy-m", account_id: "a1", account_email: "g1@test.com" }
        ]);
        const bodyG = Buffer.from(JSON.stringify({ model: "gemini-pro" }));
        const picks = [1, 2, 3].map(() => r.allocateAccountForRequest("/v1:chat", "", {}, bodyG).account.email);
        const leg = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "legacy-m-v1" })));
        console.log(JSON.stringify({ picks, leg: leg.account.email }));
        """
        out = run_node(code)
        self.assertEqual(out["picks"], ["g1@test.com", "g2@test.com", "g1@test.com"])
        self.assertEqual(out["leg"], "g1@test.com")

    def test_sidebar_and_model_rules_view_and_dashboard_cleanup(self):
        from PyQt6.QtWidgets import QApplication
        from launcher_sidebar import SidebarNav
        from launcher_view_dashboard import DashboardView
        from launcher_view_model_rules import ModelRulesView
        from launcher_model_discovery import simulate_model_route

        _app = QApplication.instance() or QApplication(["-platform", "offscreen"])

        class _FakeWin:
            data = {
                "settings": {"language": "vi", "model_rules": []},
                "profiles": [
                    {"id": "a1", "email": "u1@test.com", "enabled": True},
                    {"id": "a2", "email": "u2@test.com", "enabled": False}
                ]
            }
            def switch_view(self, _): pass
            def on_language_changed(self, _): pass
            def on_launch_app_clicked(self): pass
            def on_launch_ide_clicked(self): pass
            def on_manual_next_account(self): pass
            def on_toggle_proxy_btn(self): pass
            def on_pin_account_selected(self, _): pass

        win = _FakeWin()
        sidebar = SidebarNav(win)
        self.assertIn("model_rules", sidebar.buttons)
        dash = DashboardView(win)
        self.assertFalse(hasattr(dash, "btn_model_rules"))

        fake_accs = [
            {"id": "a1", "email": "u1@test.com", "enabled": True, "account": {}},
            {"id": "a2", "email": "u2@test.com", "enabled": False, "account": {}}
        ]
        with patch("launcher_view_model_rules.save_data"), \
             patch("launcher_view_model_rules.send_proxy_cmd"), \
             patch("launcher_view_model_rules.collect_available_accounts", return_value=fake_accs), \
             patch("launcher_view_model_rules.discover_models_from_logs", return_value=["claude-opus"]):
            view = ModelRulesView(win)
            view.add_or_update_rule({"id": "r1", "name": "R1", "pattern": "claude", "match_type": "contains", "strategy": "priority", "accounts": [{"email": "u2@test.com"}], "enabled": True})
            view.add_or_update_rule({"id": "r2", "name": "R2", "pattern": "claude-opus", "match_type": "exact", "strategy": "priority", "accounts": [{"email": "u1@test.com"}], "enabled": True})
            view.move_rule(1, -1)
            self.assertEqual(win.data["settings"]["model_rules"][0]["id"], "r2")
            self.assertEqual(view.tbl_rules.columnCount(), 5)
            menu_texts = [a.text() for a in view._build_rule_context_menu(0).actions()]
            self.assertTrue(menu_texts and all(not t.startswith("_") for t in menu_texts))
            res = simulate_model_route("claude-opus", win.data["settings"]["model_rules"], fake_accs)
            self.assertTrue(res["matched"])
            self.assertEqual(res["accounts"][0]["email"], "u1@test.com")
            view.delete_rule(0)
            self.assertEqual(len(win.data["settings"]["model_rules"]), 1)

    def test_multi_pattern_rule_matching_and_round_robin(self):
        code = r"""
        const path = require("node:path");
        const { AccountRotator } = require(path.join(process.env.PROXY_DIR, "account_rotator"));
        const { sanitizeModelRules } = require(path.join(process.env.PROXY_DIR, "rotator_state_loader"));
        const r = new AccountRotator({});
        r.allAccounts = [
          { id: "a1", email: "g1@test.com", enabled: true, accessToken: "t1" },
          { id: "a2", email: "g2@test.com", enabled: true, accessToken: "t2" },
          { id: "a3", email: "g3@test.com", enabled: true, accessToken: "t3" }
        ];
        r.accounts = [r.allAccounts[0], r.allAccounts[1], r.allAccounts[2]];
        r.modelRules = sanitizeModelRules([
          { id: "exact_multi", patterns: ["gpt-4o", "gpt-5", "GPT-4o", " "], match_type: "exact", accounts: [{ email: "g3@test.com" }] },
          { id: "rx_multi", patterns: ["[broken", "^deepseek-r1$"], match_type: "regex", accounts: [{ email: "g2@test.com" }] },
          { id: "rr_multi", patterns: ["claude-opus", "gemini-2.5"], match_type: "contains", strategy: "round_robin", accounts: [{ email: "g1@test.com" }, { email: "g2@test.com" }] }
        ]);
        const ex1 = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "GPT-4O" })));
        const ex2 = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "gpt-5" })));
        const exMiss = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "gpt-4o-mini" })));
        const rxOk = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "deepseek-r1" })));
        const rr1 = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "claude-opus-4" })));
        const rr2 = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "gemini-2.5-pro" })));
        const rr3 = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "claude-opus-4" })));
        console.log(JSON.stringify({
          sanitizedPats: r.modelRules[0].patterns,
          ex1: ex1.account.email,
          ex1Rule: ex1.matchedRule,
          ex2: ex2.account.email,
          exMissRule: exMiss.matchedRule || null,
          rxOk: rxOk.account.email,
          rrPicks: [rr1.account.email, rr2.account.email, rr3.account.email]
        }));
        """
        out = run_node(code)
        self.assertEqual(out["sanitizedPats"], ["gpt-4o", "gpt-5"])
        self.assertEqual(out["ex1"], "g3@test.com")
        self.assertEqual(out["ex1Rule"], "gpt-4o (+1)")
        self.assertEqual(out["ex2"], "g3@test.com")
        self.assertIsNone(out["exMissRule"])
        self.assertEqual(out["rxOk"], "g2@test.com")
        self.assertEqual(out["rrPicks"], ["g1@test.com", "g2@test.com", "g1@test.com"])

    def test_multi_model_editor_and_scan_presets(self):
        import time
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication, QTableWidget
        from launcher_model_rule_editor import ModelRuleEditorDialog
        from launcher_model_discovery import simulate_model_route
        from launcher_view_model_rules import ModelRulesView

        _app = QApplication.instance() or QApplication(["-platform", "offscreen"])
        fake_accs = [
            {"id": "a1", "email": "u1@test.com", "enabled": True, "account": {}},
            {"id": "a2", "email": "u2@test.com", "enabled": False, "account": {}}
        ]
        scan_cache = {
            "u1@test.com": {"id": "a1", "email": "u1@test.com", "ok": True, "models": ["claude-sonnet-4", "gpt-5"]},
            "u2@test.com": {"id": "a2", "email": "u2@test.com", "ok": True, "models": ["claude-opus-4", "claude-sonnet-4"]}
        }

        class _FakeWin:
            data = {"settings": {"language": "vi", "model_rules": []}, "profiles": []}

        with patch("launcher_model_rule_editor.collect_available_accounts", return_value=fake_accs), \
             patch("launcher_model_rule_editor.fetch_all_accounts_models", return_value=list(scan_cache.values())), \
             patch("launcher_view_model_rules.collect_available_accounts", return_value=fake_accs), \
             patch("launcher_view_model_rules.discover_models_from_logs", return_value=[]), \
             patch("launcher_view_model_rules.save_data"), \
             patch("launcher_view_model_rules.send_proxy_cmd"):
            dlg_empty = ModelRuleEditorDialog(_FakeWin(), scanned_cache=scan_cache)
            self.assertEqual(dlg_empty.model_selector.list_models.count(), 0)
            self.assertTrue(dlg_empty.model_selector.lbl_empty.isVisibleTo(dlg_empty))
            dlg_empty.close()

            dlg = ModelRuleEditorDialog(
                _FakeWin(),
                preset_models=["claude-opus-4", "claude-sonnet-4"],
                preset_account={"id": "a2", "email": "u2@test.com"},
                scanned_cache=scan_cache
            )
            self.assertEqual(dlg.model_selector.get_selected_patterns(), ["claude-opus-4"])
            dlg._select_accounts("all")
            texts = [dlg.model_selector.list_models.item(i).text() for i in range(dlg.model_selector.list_models.count())]
            tips = [dlg.model_selector.list_models.item(i).toolTip() for i in range(dlg.model_selector.list_models.count())]
            opus_idx = next(i for i, t in enumerate(texts) if t.startswith("claude-opus-4"))
            sonnet_idx = next(i for i, t in enumerate(texts) if t.startswith("claude-sonnet-4"))
            self.assertIn("1/2", texts[opus_idx])
            self.assertIn("u1@test.com", tips[opus_idx])
            self.assertEqual(texts[sonnet_idx], "claude-sonnet-4")

            dlg.model_selector.edit_search.setText("gpt-5")
            self.assertTrue(dlg.model_selector.list_models.item(opus_idx).isHidden())
            gpt_idx = next(i for i in range(dlg.model_selector.list_models.count()) if dlg.model_selector.list_models.item(i).data(Qt.ItemDataRole.UserRole) == "gpt-5")
            dlg.model_selector.list_models.item(gpt_idx).setCheckState(Qt.CheckState.Checked)

            dlg.query_selected_accounts()
            for _ in range(30):
                _app.processEvents()
                if not dlg._querying_emails:
                    break
                time.sleep(0.02)
            dlg.model_selector.edit_search.clear()
            self.assertEqual(dlg.model_selector.get_selected_patterns(), ["claude-opus-4", "gpt-5"])

            dlg._on_save()
            saved = dlg.get_rule()
            self.assertEqual(saved["patterns"], ["claude-opus-4", "gpt-5"])
            self.assertEqual(len(saved["accounts"]), 2)

            sim = simulate_model_route("gpt-5-turbo", [saved], fake_accs)
            self.assertTrue(sim["matched"])

            view = ModelRulesView(_FakeWin())
            self.assertEqual(view.tbl_rules.verticalHeader().defaultSectionSize(), 44)
            self.assertEqual(view.tbl_rules.editTriggers(), QTableWidget.EditTrigger.NoEditTriggers)
            view.add_or_update_rule(saved)
            from PyQt6.QtWidgets import QPushButton
            self.assertEqual(view.tbl_rules.cellWidget(0, 2).findChild(QPushButton).text(), "2 model")
            view.add_or_update_rule(dict(saved, name="VIP Pool"), edit_idx=0)
            self.assertEqual(view.tbl_rules.cellWidget(0, 2).findChild(QPushButton).text(), "VIP Pool (2 model)")


if __name__ == "__main__":
    unittest.main()
