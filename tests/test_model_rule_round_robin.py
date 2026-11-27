# -*- coding: utf-8 -*-
import os
import sys
import json
import tempfile
import subprocess
import unittest
from unittest.mock import patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROXY_DIR = os.path.join(ROOT_DIR, "proxy")
LAUNCHER_DIR = os.path.join(ROOT_DIR, "launcher")
if LAUNCHER_DIR not in sys.path:
    sys.path.insert(0, LAUNCHER_DIR)


def run_node(script_body: str):
    env = os.environ.copy()
    env["PROXY_DIR"] = PROXY_DIR.replace("\\", "/")
    res = subprocess.run(["node", "-e", script_body], cwd=ROOT_DIR, env=env, capture_output=True, text=True, check=True)
    lines = [ln.strip() for ln in res.stdout.strip().splitlines() if ln.strip()]
    return json.loads(lines[-1])


class TestModelRuleRoundRobin(unittest.TestCase):
    def test_rule_rr_inherits_global_and_overrides_per_rule_threshold(self):
        code = r"""
        const path = require("node:path");
        const { AccountRotator } = require(path.join(process.env.PROXY_DIR, "account_rotator"));
        const { sanitizeModelRules } = require(path.join(process.env.PROXY_DIR, "rotator_state_loader"));
        const r = new AccountRotator({});
        r.requestsPerAccount = 3;
        r.allAccounts = [
          { id: "a1", email: "a1@test.com", enabled: true, accessToken: "t1" },
          { id: "a2", email: "a2@test.com", enabled: true, accessToken: "t2" },
          { id: "b1", email: "b1@test.com", enabled: true, accessToken: "t3" },
          { id: "b2", email: "b2@test.com", enabled: true, accessToken: "t4" }
        ];
        r.accounts = [r.allAccounts[0], r.allAccounts[1], r.allAccounts[2], r.allAccounts[3]];
        r.modelRules = sanitizeModelRules([
          { id: "r_inherit", patterns: ["claude"], strategy: "round_robin", requests_per_account: 0, accounts: [{ email: "a1@test.com" }, { email: "a2@test.com" }] },
          { id: "r_custom", patterns: ["gemini"], strategy: "round_robin", requests_per_account: 2, accounts: [{ email: "b1@test.com" }, { email: "b2@test.com" }] }
        ]);
        const bodyA = Buffer.from(JSON.stringify({ model: "claude-sonnet" }));
        const bodyB = Buffer.from(JSON.stringify({ model: "gemini-pro" }));
        const bodyG = Buffer.from(JSON.stringify({ model: "gpt-4o" }));
        const picksA = [1, 2, 3, 4, 5, 6].map(() => r.allocateAccountForRequest("/v1:chat", "", {}, bodyA));
        const g1 = r.allocateAccountForRequest("/v1:chat", "", {}, bodyG);
        const picksB = [1, 2, 3, 4].map(() => r.allocateAccountForRequest("/v1:chat", "", {}, bodyB));
        const g2 = r.allocateAccountForRequest("/v1:chat", "", {}, bodyG);
        const midA = r.allocateAccountForRequest("/v1:chat", "", {}, bodyA);
        r.requestsPerAccount = 1;
        const loweredA = r.allocateAccountForRequest("/v1:chat", "", {}, bodyA);
        r.allAccounts[2].enabled = false;
        r.accounts = [r.allAccounts[0], r.allAccounts[1], r.allAccounts[3]];
        const bDeactive = [1, 2].map(() => r.allocateAccountForRequest("/v1:chat", "", {}, bodyB).account.email);
        console.log(JSON.stringify({
          aEmails: picksA.map((p) => p.account.email),
          aServed: picksA.map((p) => p.servedCount),
          aMax: picksA.map((p) => p.requestsPerAccount),
          bEmails: picksB.map((p) => p.account.email),
          bServed: picksB.map((p) => p.servedCount),
          bMax: picksB.map((p) => p.requestsPerAccount),
          gServed: [g1.servedCount, g2.servedCount],
          gIdx: r.accountIndex,
          midA: [midA.account.email, midA.servedCount],
          loweredA: [loweredA.account.email, loweredA.servedCount, loweredA.requestsPerAccount],
          bDeactive
        }));
        """
        out = run_node(code)
        self.assertEqual(out["aEmails"], ["a1@test.com"] * 3 + ["a2@test.com"] * 3)
        self.assertEqual(out["aServed"], [1, 2, 3, 1, 2, 3])
        self.assertEqual(out["aMax"], [3] * 6)
        self.assertEqual(out["bEmails"], ["b1@test.com", "b1@test.com", "b2@test.com", "b2@test.com"])
        self.assertEqual(out["bServed"], [1, 2, 1, 2])
        self.assertEqual(out["bMax"], [2] * 4)
        self.assertEqual(out["gServed"], [1, 2])
        self.assertEqual(out["gIdx"], 0)
        self.assertEqual(out["midA"], ["a1@test.com", 1])
        self.assertEqual(out["loweredA"], ["a2@test.com", 1, 1])
        self.assertEqual(out["bDeactive"], ["b2@test.com", "b2@test.com"])

    def test_model_rule_precedence_over_pause_pin_and_fallback_to_pinned(self):
        code = r"""
        const path = require("node:path");
        const { AccountRotator } = require(path.join(process.env.PROXY_DIR, "account_rotator"));
        const { sanitizeModelRules } = require(path.join(process.env.PROXY_DIR, "rotator_state_loader"));
        const { buildRequestContext } = require(path.join(process.env.PROXY_DIR, "model_rule_engine"));
        const r = new AccountRotator({});
        r.allAccounts = [
          { id: "p1", email: "pin@test.com", enabled: true, accessToken: "t0" },
          { id: "g1", email: "g1@test.com", enabled: true, accessToken: "t1" },
          { id: "g2", email: "g2@test.com", enabled: true, accessToken: "t2" }
        ];
        r.accounts = [r.allAccounts[0], r.allAccounts[1], r.allAccounts[2]];
        r.rotationPaused = true;
        r.pinnedAccountKey = { id: "p1", email: "pin@test.com" };
        r.modelRules = sanitizeModelRules([
          { id: "r_rr", patterns: ["claude"], strategy: "round_robin", accounts: [{ email: "g1@test.com" }, { email: "g2@test.com" }] },
          { id: "r_fb", patterns: ["flex"], strategy: "priority", fallback_to_global: true, accounts: [{ email: "g1@test.com" }] }
        ]);
        const m1 = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "claude-opus" })));
        const m2 = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "claude-opus" })));
        const un = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "gemini-flash" })));
        r.allAccounts[1].unhealthyUntil = Date.now() + 60000;
        const fbAlloc = r.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "flex-1" })));
        console.log(JSON.stringify({
          m1: m1.account.email, m2: m2.account.email,
          unAcc: un.account.email, unLock: un.lockReason,
          fbAcc: fbAlloc.account.email, fbLock: fbAlloc.lockReason
        }));
        """
        out = run_node(code)
        self.assertEqual([out["m1"], out["m2"]], ["g1@test.com", "g2@test.com"])
        self.assertEqual(out["unAcc"], "pin@test.com")
        self.assertEqual(out["unLock"], "pinned")
        self.assertEqual(out["fbAcc"], "pin@test.com")
        self.assertEqual(out["fbLock"], "pinned")

    def test_rule_states_persist_and_restore_across_restart(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            acc_file = os.path.join(tmp_dir, "accounts.json")
            prof_file = os.path.join(tmp_dir, "profiles.json")
            state_file = os.path.join(tmp_dir, "rotator_state.json")
            with open(acc_file, "w", encoding="utf-8") as f:
                json.dump({"accounts": [
                    {"id": "a1", "email": "a1@test.com", "accessToken": "t1"},
                    {"id": "a2", "email": "a2@test.com", "accessToken": "t2"}
                ]}, f)
            with open(prof_file, "w", encoding="utf-8") as f:
                json.dump({
                    "profiles": [{"id": "a1", "email": "a1@test.com", "enabled": True, "order": 1}, {"id": "a2", "email": "a2@test.com", "enabled": True, "order": 2}],
                    "settings": {"requests_per_account": 1, "model_rules": [
                        {"id": "keep_rule", "patterns": ["claude"], "strategy": "round_robin", "requests_per_account": 3, "accounts": [{"id": "a1", "email": "a1@test.com"}, {"id": "a2", "email": "a2@test.com"}], "enabled": True},
                        {"id": "old_rule", "patterns": ["gpt"], "strategy": "round_robin", "requests_per_account": 2, "accounts": [{"id": "a1", "email": "a1@test.com"}], "enabled": True}
                    ]}
                }, f)

            script_part1 = r"""
            const path = require("node:path");
            const { AccountRotator } = require(path.join(process.env.PROXY_DIR, "account_rotator"));
            const cfg = { ACCOUNTS_FILE: %s, PROFILES_FILE: %s, ROTATOR_STATE_FILE: %s };
            const r1 = new AccountRotator(cfg);
            r1.loadState();
            const first = r1.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "claude-sonnet" })));
            r1.allocateAccountForRequest("/v1:chat", "", {}, Buffer.from(JSON.stringify({ model: "gpt-4o" })));
            r1.modelRules = r1.modelRules.filter((x) => x.id !== "old_rule");
            r1.saveRotatorState();
            console.log(JSON.stringify({ first: first.account.email, served: first.servedCount }));
            """ % (json.dumps(acc_file), json.dumps(prof_file), json.dumps(state_file))
            out1 = run_node(script_part1)
            self.assertEqual((out1["first"], out1["served"]), ("a1@test.com", 1))

            with open(state_file, "r", encoding="utf-8") as f:
                persisted = json.load(f)
            self.assertIn("keep_rule", persisted.get("rule_states", {}))
            self.assertNotIn("old_rule", persisted.get("rule_states", {}))

            script_part2 = r"""
            const path = require("node:path");
            const { AccountRotator } = require(path.join(process.env.PROXY_DIR, "account_rotator"));
            const { serializeRuleStates } = require(path.join(process.env.PROXY_DIR, "rotator_persistence"));
            const cfg = { ACCOUNTS_FILE: %s, PROFILES_FILE: %s, ROTATOR_STATE_FILE: %s };
            const r2 = new AccountRotator(cfg);
            r2.loadState();
            const body = Buffer.from(JSON.stringify({ model: "claude-sonnet" }));
            const next3 = [1, 2, 3].map(() => r2.allocateAccountForRequest("/v1:chat", "", {}, body));
            const cleared = serializeRuleStates(r2.ruleCursors, []);
            console.log(JSON.stringify({
              emails: next3.map((x) => x.account.email),
              served: next3.map((x) => x.servedCount),
              clearedKeys: Object.keys(cleared)
            }));
            """ % (json.dumps(acc_file), json.dumps(prof_file), json.dumps(state_file))
            out2 = run_node(script_part2)
            self.assertEqual(out2["emails"], ["a1@test.com", "a1@test.com", "a2@test.com"])
            self.assertEqual(out2["served"], [2, 3, 1])
            self.assertEqual(out2["clearedKeys"], [])

    def test_cyclic_failover_order_and_cursor_advance_in_rule_rr(self):
        code = r"""
        const path = require("node:path");
        const { AccountRotator } = require(path.join(process.env.PROXY_DIR, "account_rotator"));
        const { sanitizeModelRules } = require(path.join(process.env.PROXY_DIR, "rotator_state_loader"));
        const { buildRequestContext } = require(path.join(process.env.PROXY_DIR, "model_rule_engine"));
        const r = new AccountRotator({});
        r.allAccounts = [
          { id: "a1", email: "a1@test.com", enabled: true, accessToken: "t1" },
          { id: "a2", email: "a2@test.com", enabled: true, accessToken: "t2" },
          { id: "a3", email: "a3@test.com", enabled: true, accessToken: "t3" }
        ];
        r.accounts = [...r.allAccounts];
        r.modelRules = sanitizeModelRules([
          { id: "rr3", patterns: ["claude"], strategy: "round_robin", requests_per_account: 2, accounts: [{ email: "a1@test.com" }, { email: "a2@test.com" }, { email: "a3@test.com" }] }
        ]);
        const body = Buffer.from(JSON.stringify({ model: "claude-sonnet" }));
        r.allocateAccountForRequest("/v1:chat", "", {}, body);
        r.allocateAccountForRequest("/v1:chat", "", {}, body);
        const alloc = r.allocateAccountForRequest("/v1:chat", "", {}, body);
        const ctx = buildRequestContext(r, {}, () => {}, null, false, alloc);
        r.allAccounts[1].unhealthyUntil = Date.now() + 60000;
        const fail1 = ctx.nextAccount(null, true, false, alloc.account);
        r.allAccounts[2].unhealthyUntil = Date.now() + 60000;
        const fail2 = ctx.nextAccount(null, true, false, fail1);
        console.log(JSON.stringify({
          startAcc: alloc.account.email,
          fail1: fail1?.email || null,
          fail2: fail2?.email || null,
          cursorAfter: r.ruleCursors.get("rr3")
        }));
        """
        out = run_node(code)
        self.assertEqual(out["startAcc"], "a2@test.com")
        self.assertEqual(out["fail1"], "a3@test.com")
        self.assertEqual(out["fail2"], "a1@test.com")
        self.assertEqual(out["cursorAfter"]["lastAccountEmail"], "a1@test.com")
        self.assertEqual(out["cursorAfter"]["served"], 1)

    def test_ui_rule_editor_table_and_dashboard_turn_display(self):
        from PyQt6.QtWidgets import QApplication
        from launcher_model_rule_editor import ModelRuleEditorDialog
        from launcher_view_model_rules import ModelRulesView
        from launcher_view_dashboard import DashboardView

        _app = QApplication.instance() or QApplication(["-platform", "offscreen"])
        fake_accs = [
            {"id": "a1", "email": "u1@test.com", "enabled": True, "account": {}},
            {"id": "a2", "email": "u2@test.com", "enabled": False, "account": {}}
        ]
        scan_cache = {"u1@test.com": {"id": "a1", "email": "u1@test.com", "ok": True, "models": ["claude-sonnet-4"]}}

        class _FakeWin:
            data = {"settings": {"language": "vi", "model_rules": []}, "profiles": [
                {"id": "a1", "email": "u1@test.com", "enabled": True},
                {"id": "a2", "email": "u2@test.com", "enabled": False}
            ]}
            def on_launch_app_clicked(self): pass
            def on_launch_ide_clicked(self): pass
            def on_manual_next_account(self): pass
            def on_toggle_proxy_btn(self): pass
            def on_pin_account_selected(self, _): pass

        with patch("launcher_model_rule_editor.collect_available_accounts", return_value=fake_accs), \
             patch("launcher_view_model_rules.collect_available_accounts", return_value=fake_accs), \
             patch("launcher_view_model_rules.discover_models_from_logs", return_value=[]), \
             patch("launcher_view_model_rules.save_data"), \
             patch("launcher_view_model_rules.send_proxy_cmd"):
            dlg = ModelRuleEditorDialog(_FakeWin(), preset_models=["claude-sonnet-4"], preset_account=fake_accs[0], scanned_cache=scan_cache)
            self.assertTrue(dlg.row_rr_reqs.isHidden())
            dlg.combo_strategy.setCurrentIndex(dlg.combo_strategy.findData("round_robin"))
            self.assertFalse(dlg.row_rr_reqs.isHidden())
            dlg.spin_req_per_account.setValue(4)
            dlg._on_save()
            saved = dlg.get_rule()
            self.assertEqual(saved["requests_per_account"], 4)

            dlg_reopen = ModelRuleEditorDialog(_FakeWin(), rule=saved, scanned_cache=scan_cache)
            self.assertFalse(dlg_reopen.row_rr_reqs.isHidden())
            self.assertEqual(dlg_reopen.spin_req_per_account.value(), 4)
            dlg_reopen.combo_strategy.setCurrentIndex(dlg_reopen.combo_strategy.findData("priority"))
            self.assertTrue(dlg_reopen.row_rr_reqs.isHidden())
            dlg_reopen._on_save()
            self.assertEqual(dlg_reopen.get_rule()["requests_per_account"], 0)

            view = ModelRulesView(_FakeWin())
            view.add_or_update_rule(saved)
            view.add_or_update_rule(dict(saved, id="r_global", requests_per_account=0))
            self.assertIn("4 req", view.tbl_rules.item(0, 3).text())
            self.assertIn("Tổng", view.tbl_rules.item(1, 3).text())

        with tempfile.TemporaryDirectory() as tmp_dir:
            status_file = os.path.join(tmp_dir, "live_status.json")
            dash = DashboardView(_FakeWin())
            with patch("launcher_view_dashboard.is_proxy_running", return_value=True), \
                 patch("launcher_view_dashboard.STATUS_FILE", status_file), \
                 patch("launcher_view_dashboard.collect_available_accounts", return_value=fake_accs):
                for payload, exp_turn in [
                    ({"status": "paused", "paused": True, "pinned": True, "pinned_email": "u2@test.com", "account_email": "u1@test.com", "model_routed": "VIP", "model_rule_strategy": "round_robin", "current_req": 2, "requests_per_account": 4}, "2/4"),
                    ({"status": "paused", "paused": True, "pinned": True, "pinned_email": "u2@test.com", "account_email": "u1@test.com", "model_routed": "VIP", "model_rule_strategy": "priority", "current_req": 1, "requests_per_account": 1}, "—"),
                    ({"status": "paused", "paused": True, "pinned": True, "pinned_email": "u2@test.com", "account_email": "u2@test.com", "model_routed": "", "current_req": 1, "requests_per_account": 5}, "∞")
                ]:
                    with open(status_file, "w", encoding="utf-8") as f:
                        json.dump(payload, f)
                    dash.update_dashboard()
                    self.assertEqual(dash.card_turn.lbl_value.text(), exp_turn)


if __name__ == "__main__":
    unittest.main()
