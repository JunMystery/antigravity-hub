# -*- coding: utf-8 -*-
"""
Unit tests for Dashboard inline account pinning (including deactivated accounts),
strict pause lock, persistent pin state, model routing, and model discovery.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "launcher")

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_node(code: str) -> dict:
    res = subprocess.run(
        ["node", "-e", code],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    return json.loads(lines[-1])


class TestPinningAndModelRouting(unittest.TestCase):
    def _setup_files(self, tmp_dir, rules=None):
        acc_file = os.path.join(tmp_dir, "accounts.json")
        prof_file = os.path.join(tmp_dir, "profiles.json")
        state_file = os.path.join(tmp_dir, "rotator_state.json")
        with open(acc_file, "w", encoding="utf-8") as f:
            json.dump({
                "accounts": [
                    {"id": "a1", "email": "u1@test.com", "accessToken": "t1"},
                    {"id": "a2", "email": "u2@test.com", "accessToken": "t2"},
                    {"id": "a3", "email": "u3@test.com", "accessToken": "t3"}
                ]
            }, f)
        with open(prof_file, "w", encoding="utf-8") as f:
            json.dump({
                "settings": {"requests_per_account": 1, "model_rules": rules or []},
                "profiles": [
                    {"id": "a1", "email": "u1@test.com", "enabled": True, "order": 1},
                    {"id": "a2", "email": "u2@test.com", "enabled": True, "order": 2},
                    {"id": "a3", "email": "u3@test.com", "enabled": False, "order": 3}
                ]
            }, f)
        return acc_file, prof_file, state_file

    def test_pin_deactive_account_and_unpin_preserves_round_robin(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            acc_file, prof_file, state_file = self._setup_files(tmp_dir)
            code = f"""
            const {{ AccountRotator }} = require("./proxy/account_rotator");
            const cfg = {{ ACCOUNTS_FILE: {json.dumps(acc_file)}, PROFILES_FILE: {json.dumps(prof_file)}, ROTATOR_STATE_FILE: {json.dumps(state_file)} }};
            const r = new AccountRotator(cfg);
            r.loadState();
            r.handleCommand("pin_account", null, () => {{}}, {{ email: "u3@test.com" }});
            const pinnedCalls = [0, 1, 2].map(() => {{
              const a = r.allocateAccountForRequest("/v1internal:streamGenerateContent", "daily-cloudcode-pa.googleapis.com", {{}});
              return {{ email: a.account.email, locked: a.isLocked }};
            }});
            const failoverStay = r.nextAccount(null, true, false, r.getCurrentAccount()).email;
            r.handleCommand("unpin_account", null, () => {{}});
            const rrCalls = [0, 1, 2].map(() => r.allocateAccountForRequest("/v1internal:streamGenerateContent", "daily-cloudcode-pa.googleapis.com", {{}}).account.email);
            console.log(JSON.stringify({{ pinnedCalls, failoverStay, rrCalls }}));
            """
            out = run_node(code)
            self.assertEqual(out["pinnedCalls"], [
                {"email": "u3@test.com", "locked": True},
                {"email": "u3@test.com", "locked": True},
                {"email": "u3@test.com", "locked": True}
            ])
            self.assertEqual(out["failoverStay"], "u3@test.com")
            self.assertNotIn("u3@test.com", out["rrCalls"])

    def test_persisted_pin_and_model_rule_precedence(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            rules = [{"pattern": "claude-opus", "account_email": "u3@test.com", "account_id": "a3", "enabled": True}]
            acc_file, prof_file, state_file = self._setup_files(tmp_dir, rules=rules)
            with open(prof_file, "r", encoding="utf-8") as f:
                prof_data = json.load(f)
            prof_data["profiles"][2]["enabled"] = True
            with open(prof_file, "w", encoding="utf-8") as f:
                json.dump(prof_data, f)
            code = f"""
            const {{ AccountRotator }} = require("./proxy/account_rotator");
            const cfg = {{ ACCOUNTS_FILE: {json.dumps(acc_file)}, PROFILES_FILE: {json.dumps(prof_file)}, ROTATOR_STATE_FILE: {json.dumps(state_file)} }};
            const r1 = new AccountRotator(cfg);
            r1.loadState();
            r1.handleCommand("pin_account", null, () => {{}}, {{ email: "u2@test.com" }});

            const r2 = new AccountRotator(cfg);
            r2.loadState();
            const opusAlloc = r2.allocateAccountForRequest(
              "/v1internal:streamGenerateContent", "daily-cloudcode-pa.googleapis.com", {{}},
              Buffer.from(JSON.stringify({{ model: "claude-opus-4-6" }}))
            );
            const flashAlloc = r2.allocateAccountForRequest(
              "/v1internal:streamGenerateContent", "daily-cloudcode-pa.googleapis.com", {{}},
              Buffer.from(JSON.stringify({{ model: "gemini-2.5-flash" }}))
            );
            console.log(JSON.stringify({{
              restoredPaused: r2.rotationPaused,
              restoredEmail: r2.getCurrentAccount().email,
              opusEmail: opusAlloc.account.email,
              opusReason: opusAlloc.lockReason,
              flashEmail: flashAlloc.account.email,
              flashReason: flashAlloc.lockReason
            }}));
            """
            out = run_node(code)
            self.assertTrue(out["restoredPaused"])
            self.assertEqual(out["restoredEmail"], "u2@test.com")
            self.assertEqual(out["opusEmail"], "u3@test.com")
            self.assertEqual(out["opusReason"], "model_rule")
            self.assertEqual(out["flashEmail"], "u2@test.com")
            self.assertEqual(out["flashReason"], "pinned")

            # Deactive u3 o Accounts => Model Rule khong duoc chon hoac retry u3 nua
            prof_data["profiles"][2]["enabled"] = False
            with open(prof_file, "w", encoding="utf-8") as f:
                json.dump(prof_data, f)
            code_deactive = f"""
            const {{ AccountRotator }} = require("./proxy/account_rotator");
            const cfg = {{ ACCOUNTS_FILE: {json.dumps(acc_file)}, PROFILES_FILE: {json.dumps(prof_file)}, ROTATOR_STATE_FILE: {json.dumps(state_file)} }};
            const r3 = new AccountRotator(cfg);
            r3.loadState();
            const opusAfterOff = r3.allocateAccountForRequest(
              "/v1internal:streamGenerateContent", "daily-cloudcode-pa.googleapis.com", {{}},
              Buffer.from(JSON.stringify({{ model: "claude-opus-4-6" }}))
            );
            console.log(JSON.stringify({{
              opusAfterOffEmail: opusAfterOff.account.email,
              opusAfterOffReason: opusAfterOff.lockReason
            }}));
            """
            out_off = run_node(code_deactive)
            self.assertEqual(out_off["opusAfterOffEmail"], "u2@test.com")
            self.assertEqual(out_off["opusAfterOffReason"], "pinned")


class TestLauncherUiAndDiscovery(unittest.TestCase):
    def test_compact_status_bar_inline_selector(self):
        from PyQt6.QtWidgets import QApplication
        from launcher_view_dashboard import DashboardView

        _app = QApplication.instance() or QApplication(["-platform", "offscreen"])

        class _FakeWin:
            data = {"settings": {}, "profiles": []}
            def on_launch_app_clicked(self): pass
            def on_launch_ide_clicked(self): pass
            def on_manual_next_account(self): pass
            def on_toggle_proxy_btn(self): pass
            def on_pin_account_selected(self, key): selected.append(key)

        selected = []
        dash = DashboardView(_FakeWin())
        opts = [("AUTO", "Auto (Round Robin)"), ("a1@x.com", "a1@x.com"), ("a2@x.com", "a2@x.com [Deactive]")]
        dash.set_account_options(opts, "AUTO")
        self.assertEqual(selected, [])

        dash.combo_account.setCurrentIndex(2)
        self.assertEqual(selected, ["a2@x.com"])

    def test_discover_models_from_logs_and_payload(self):
        from launcher_model_discovery import discover_models_from_logs, _extract_model_ids_from_payload

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = os.path.join(tmp_dir, "proxy.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("[10:00:01] [ROUND-ROBIN #1] [MAIN] POST [MODEL: gemini-2.5-flash] /v1\n")
                f.write("[10:00:02] [ROUND-ROBIN #2] [MAIN] POST [MODEL: claude-opus-4-6] /v1\n")
            with patch("launcher_model_discovery.get_log_path", return_value=log_file):
                found = discover_models_from_logs()
            self.assertEqual(found, ["claude-opus-4-6", "gemini-2.5-flash"])

        extracted = _extract_model_ids_from_payload({
            "models": {"models/claude-sonnet-4-6": {}, "gemini-2.5-pro": {}},
            "groups": [{"displayName": "Gemini 2.5", "buckets": [{"modelId": "gemini-2.5-flash"}]}]
        })
        self.assertIn("claude-sonnet-4-6", extracted)
        self.assertIn("gemini-2.5-pro", extracted)
        self.assertIn("gemini-2.5-flash", extracted)

    def test_chat_handler_strict_lock_no_failover_on_429(self):
        code = """
        const https = require("node:https");
        const { EventEmitter } = require("node:events");
        const { executeGoogleChatRequest } = require("./proxy/chat_handler");

        let nextCalled = 0;
        https.request = (_opts, cb) => {
          const req = new EventEmitter();
          req.write = () => {};
          req.end = () => {
            const gRes = new EventEmitter();
            gRes.statusCode = 429;
            gRes.headers = { "content-type": "application/json" };
            gRes.complete = true;
            gRes.pipe = (dest) => { dest.end('{"error":"rate_limited"}'); };
            cb(gRes);
            gRes.emit("end");
          };
          return req;
        };

        const clientRes = new EventEmitter();
        clientRes.headersSent = false;
        clientRes.writableEnded = false;
        clientRes.destroyed = false;
        clientRes.closed = false;
        let sentStatus = null;
        let sentBody = "";
        clientRes.writeHead = (s) => { sentStatus = s; clientRes.headersSent = true; };
        clientRes.end = (chunk) => { if (chunk) sentBody += chunk; clientRes.writableEnded = true; };

        const ctx = {
          config: {},
          accounts: [{ id: "a1", email: "u1@test.com", accessToken: "t1" }, { id: "a2", email: "u2@test.com", accessToken: "t2" }],
          isAccountLocked: true,
          rotationPaused: true,
          requestsPerAccount: 1,
          currentAccRequestsServed: 1,
          requestCount: 1,
          nextAccount: () => { nextCalled++; return ctx.accounts[1]; },
          writeLiveStatus: () => {}
        };
        executeGoogleChatRequest(ctx.accounts[0], Buffer.from("{}"), "/v1internal:streamGenerateContent", "POST", {}, clientRes, ctx)
          .then(() => { console.log(JSON.stringify({ nextCalled, sentStatus, sentBody })); });
        """
        out = run_node(code)
        self.assertEqual(out["nextCalled"], 0)
        self.assertEqual(out["sentStatus"], 429)

    def test_dashboard_view_syncs_pinned_status(self):
        from PyQt6.QtWidgets import QApplication
        from launcher_view_dashboard import DashboardView

        _app = QApplication.instance() or QApplication(["-platform", "offscreen"])

        class _FakeWin:
            data = {
                "settings": {"model_rules": [{"pattern": "opus", "account_email": "u2@test.com", "enabled": True}]},
                "profiles": [
                    {"id": "a1", "email": "u1@test.com", "enabled": True},
                    {"id": "a2", "email": "u2@test.com", "enabled": False}
                ]
            }
            def on_launch_app_clicked(self): pass
            def on_launch_ide_clicked(self): pass
            def on_manual_next_account(self): pass
            def on_toggle_proxy_btn(self): pass
            def on_pin_account_selected(self, _): pass
            def on_open_model_rules(self): pass

        with tempfile.TemporaryDirectory() as tmp_dir:
            status_file = os.path.join(tmp_dir, "live_status.json")
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump({
                    "status": "paused", "paused": True, "pinned": True,
                    "pinned_email": "u2@test.com", "account_email": "u2@test.com",
                    "current_req": 3, "requests_per_account": 1, "total_requests": 10
                }, f)
            fake_accs = [
                {"id": "a1", "email": "u1@test.com", "enabled": True, "account": {}},
                {"id": "a2", "email": "u2@test.com", "enabled": False, "account": {}}
            ]
            dash = DashboardView(_FakeWin())
            with patch("launcher_view_dashboard.is_proxy_running", return_value=True), \
                 patch("launcher_view_dashboard.STATUS_FILE", status_file), \
                 patch("launcher_view_dashboard.collect_available_accounts", return_value=fake_accs):
                dash.update_dashboard()

            self.assertEqual(dash.combo_account.currentData(), "u2@test.com")
            self.assertEqual(dash.status_bar.lbl_acc.text(), "u2@test.com")
            self.assertEqual(dash.card_turn.lbl_value.text(), "∞")
            self.assertFalse(dash.btn_next.isEnabled())
            self.assertFalse(hasattr(dash, "btn_model_rules"))

    def test_on_account_toggled_reloads_running_proxy(self):
        import launcher_window

        class _DummyWin:
            data = {"profiles": [{"id": "a1", "email": "u1@test.com", "enabled": True}]}
            refreshed = []
            def _refresh_list(self, select_id=None):
                self.refreshed.append(select_id)

        win = _DummyWin()
        with patch("launcher_window.save_data") as mock_save, \
             patch("launcher_window.is_proxy_running", return_value=True), \
             patch("launcher_window.send_proxy_cmd") as mock_cmd:
            launcher_window.LauncherWindow.on_account_toggled(win, "a1", False)
            self.assertFalse(win.data["profiles"][0]["enabled"])
            self.assertEqual(win.refreshed, ["a1"])
            mock_save.assert_called_once_with(win.data)
            mock_cmd.assert_called_once_with(win, "reload")


if __name__ == "__main__":
    unittest.main()
