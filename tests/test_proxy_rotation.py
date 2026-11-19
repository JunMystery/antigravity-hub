# -*- coding: utf-8 -*-
"""
Unit tests for Proxy Round-Robin Rotation and Legacy Request Verification.
"""

import json
import os
import subprocess
import tempfile
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run_node(code: str) -> str:
    res = subprocess.run(
        ["node", "-e", code],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""

class TestProxyRoundRobinRotation(unittest.TestCase):
    """Kiem tra xoay vong Round Robin thuan tuy giua cac tai khoan."""

    def test_pure_round_robin_rotation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            acc_file = os.path.join(tmp_dir, "accounts.json")
            with open(acc_file, "w") as f:
                json.dump({
                    "accounts": [
                        {"id": "acc-1", "email": "user1@test.com", "accessToken": "t1"},
                        {"id": "acc-2", "email": "user2@test.com", "accessToken": "t2"},
                        {"id": "acc-3", "email": "user3@test.com", "accessToken": "t3"}
                    ]
                }, f)

            code = f"""
            const {{ AccountRotator }} = require("./proxy/account_rotator");
            const rotator = new AccountRotator({{ ACCOUNTS_FILE: {json.dumps(acc_file)} }});
            rotator.loadState();
            rotator.requestsPerAccount = 1;

            const allocated = [];
            for (let i = 0; i < 6; i++) {{
              const a = rotator.allocateAccountForRequest("/v1internal:streamGenerateContent", "daily-cloudcode-pa.googleapis.com", {{
                "client-request-id": "req-" + i,
                "x-client-request-id": "xreq-" + i
              }});
              allocated.push(a.account.email);
            }}
            console.log(JSON.stringify({{ allocated, total: rotator.requestCount }}));
            """
            output = json.loads(run_node(code))
            expected = [
                "user1@test.com", "user2@test.com", "user3@test.com",
                "user1@test.com", "user2@test.com", "user3@test.com"
            ]
            self.assertEqual(output["allocated"], expected)
            self.assertEqual(output["total"], 6)

    def test_multi_request_per_account_threshold(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            acc_file = os.path.join(tmp_dir, "accounts.json")
            with open(acc_file, "w") as f:
                json.dump({
                    "accounts": [
                        {"id": "acc-1", "email": "user1@test.com", "accessToken": "t1"},
                        {"id": "acc-2", "email": "user2@test.com", "accessToken": "t2"}
                    ]
                }, f)

            code = f"""
            const {{ AccountRotator }} = require("./proxy/account_rotator");
            const rotator = new AccountRotator({{ ACCOUNTS_FILE: {json.dumps(acc_file)} }});
            rotator.loadState();
            rotator.requestsPerAccount = 2;

            const allocated = [];
            for (let i = 0; i < 4; i++) {{
              const a = rotator.allocateAccountForRequest("/v1internal:streamGenerateContent", "daily-cloudcode-pa.googleapis.com", {{
                "conversation-id": "same-conversation"
              }});
              allocated.push(a.account.email);
            }}
            console.log(JSON.stringify({{ allocated, total: rotator.requestCount }}));
            """
            output = json.loads(run_node(code))
            expected = ["user1@test.com", "user1@test.com", "user2@test.com", "user2@test.com"]
            self.assertEqual(output["allocated"], expected)
            self.assertEqual(output["total"], 4)

    def test_skip_unhealthy_account_without_double_serving(self):
        """Kiem tra tai khoan unhealthy khong bi lap luot kep (double-serving) tren tai khoan tiep theo."""
        code = """
        const { AccountRotator } = require("./proxy/account_rotator");
        const rotator = new AccountRotator({});
        rotator.accounts = [
          { id: "acc-0", email: "acc0@test.com", unhealthyUntil: Date.now() + 60000 },
          { id: "acc-1", email: "acc1@test.com" },
          { id: "acc-2", email: "acc2@test.com" }
        ];
        rotator.requestsPerAccount = 1;
        const allocated = [];
        for (let i = 0; i < 4; i++) {
          const alloc = rotator.allocateAccountForRequest();
          allocated.push(alloc.account.email);
        }
        console.log(JSON.stringify({ allocated }));
        """
        output = json.loads(run_node(code))
        expected = ["acc1@test.com", "acc2@test.com", "acc1@test.com", "acc2@test.com"]
        self.assertEqual(output["allocated"], expected)

    def test_failover_preserves_round_robin_without_skipping(self):
        """Kiem tra auto-failover sang ngay tai khoan ke tiep ma khong bo qua (skip) tai khoan hop le."""
        code = """
        const { AccountRotator } = require("./proxy/account_rotator");
        const rotator = new AccountRotator({});
        rotator.accounts = [
          { id: "acc-0", email: "acc0@test.com" },
          { id: "acc-1", email: "acc1@test.com" },
          { id: "acc-2", email: "acc2@test.com" }
        ];
        rotator.requestsPerAccount = 1;

        // Request 1 phan bo cho acc0
        const req1 = rotator.allocateAccountForRequest();
        // acc0 gap loi 429 va duoc gan unhealthyUntil
        req1.account.unhealthyUntil = Date.now() + 60000;
        // Failover goi nextAccount voi isFailover = true va failedAccount
        const failoverAcc = rotator.nextAccount(null, true, false, req1.account);

        // Request 2 tiep theo
        const req2 = rotator.allocateAccountForRequest();

        console.log(JSON.stringify({
          req1: req1.account.email,
          failover: failoverAcc.email,
          req2: req2.account.email
        }));
        """
        output = json.loads(run_node(code))
        self.assertEqual(output["req1"], "acc0@test.com")
        self.assertEqual(output["failover"], "acc1@test.com")
        self.assertEqual(output["req2"], "acc2@test.com")

    def test_timeout_failover_cooldown_and_skip(self):
        """Kiem tra khi account bi timeout socket/TTFB, account duoc danh dau unhealthy va rotator tu dong bo qua."""
        code = """
        const { AccountRotator } = require("./proxy/account_rotator");
        const rotator = new AccountRotator({});
        rotator.accounts = [
          { id: "acc-0", email: "acc0@test.com" },
          { id: "acc-1", email: "acc1@test.com" }
        ];
        rotator.requestsPerAccount = 2;

        const req1 = rotator.allocateAccountForRequest();
        // Gia lap upstream timeout tai 42s danh dau unhealthy 60s
        req1.account.unhealthyUntil = Date.now() + 60000;
        const failoverAcc = rotator.nextAccount(null, true, false, req1.account);

        // Cac request tiep theo phai phuc vu boi acc-1 vi acc-0 dang trong cooldown
        const req2 = rotator.allocateAccountForRequest();
        const req3 = rotator.allocateAccountForRequest();

        console.log(JSON.stringify({
          initial: req1.account.email,
          failover: failoverAcc.email,
          subsequent1: req2.account.email,
          subsequent2: req3.account.email
        }));
        """
        output = json.loads(run_node(code))
        self.assertEqual(output["initial"], "acc0@test.com")
        self.assertEqual(output["failover"], "acc1@test.com")
        self.assertEqual(output["subsequent1"], "acc1@test.com")
        self.assertEqual(output["subsequent2"], "acc1@test.com")

class TestPayloadRewriteAndLegacyRequests(unittest.TestCase):
    """Kiem tra rewrite payload hop chuan Google Cloud Code va bao toan project id khi rotate."""

    def test_payload_rewrite_project_and_ide_version(self):
        code = """
        const { rewriteChatPayload } = require("./proxy/chat_payload_helper");
        const acc1 = { email: "u1@test.com", projectId: "custom-proj-1" };
        const accNoProj = { email: "u3@test.com" };

        const initialBody = Buffer.from(JSON.stringify({
          prompt: "hello",
          metadata: { ideType: 9 }
        }), "utf8");

        // Khi request chua co project va gui qua acc1 co projectId
        const res1 = JSON.parse(rewriteChatPayload(initialBody, acc1, "daily-cloudcode-pa.googleapis.com").toString("utf8"));
        // Khi request chua co project va gui qua acc khong co projectId
        const res2 = JSON.parse(rewriteChatPayload(initialBody, accNoProj, "daily-cloudcode-pa.googleapis.com").toString("utf8"));
        // Khi request da co custom enterprise project thi luon bao toan
        const customBody = Buffer.from(JSON.stringify({ project: "enterprise-gcp", prompt: "hi" }), "utf8");
        const res3 = JSON.parse(rewriteChatPayload(customBody, acc1, "daily-cloudcode-pa.googleapis.com").toString("utf8"));

        console.log(JSON.stringify({
          res1_project: res1.project,
          res1_ideVersion: res1.metadata.ideVersion,
          res2_project: res2.project,
          res3_project: res3.project
        }));
        """
        output = json.loads(run_node(code))
        self.assertEqual(output["res1_project"], "custom-proj-1")
        self.assertEqual(output["res1_ideVersion"], "2.24.0")
        self.assertEqual(output["res2_project"], "aicode-consumers")
        self.assertEqual(output["res3_project"], "enterprise-gcp")

class TestLegacyEndpointsRecognition(unittest.TestCase):
    """Kiem tra nhan dien day du cac endpoint AI va legacy Google APIs."""

    def test_legacy_and_code_generation_endpoints(self):
        code = """
        const { isAiChatEndpoint } = require("./proxy/chat_payload_helper");
        const endpoints = [
          "/v1internal:streamGenerateContent",
          "/v1internal:generateContent",
          "/v1internal:streamGenerateChat",
          "/v1internal:generateChat",
          "/v1internal:generateCode",
          "/v1internal:streamGenerateCode",
          "/v1internal:completeCode",
          "/v1internal:streamCompleteCode",
          "/v1internal:suggestCode",
          "/v1internal:streamSuggestCode",
          "/v1internal:inlineCode",
          "/v1internal:streamInlineCode",
          "/v1internal:predict",
          "/v1internal:streamPredict",
          "/v1beta/models/gemini-2.0-flash:streamGenerateContent",
          "/v1/models/gemini-pro"
        ];
        const nonAi = [
          "/v1internal:loadCodeAssist",
          "/v1internal:retrieveUserQuotaSummary",
          "/healthz",
          "/favicon.ico"
        ];
        const aiResults = endpoints.map(e => isAiChatEndpoint(e));
        const nonAiResults = nonAi.map(e => isAiChatEndpoint(e));
        console.log(JSON.stringify({
          allAiTrue: aiResults.every(Boolean),
          allNonAiFalse: nonAiResults.every(r => !r)
        }));
        """
        output = json.loads(run_node(code))
        self.assertTrue(output["allAiTrue"], "All AI and legacy endpoints must be recognized")
        self.assertTrue(output["allNonAiFalse"], "Non-AI endpoints must evaluate to false")

class TestAccountSelectAndFixedMode(unittest.TestCase):
    """Kiem tra chon dich danh tai khoan, giu co dinh khi tat xoay vong va OAuth select_account."""

    def test_manual_select_account_command(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            acc_file = os.path.join(tmp_dir, "accounts.json")
            state_file = os.path.join(tmp_dir, "rotator_state.json")
            with open(acc_file, "w") as f:
                json.dump({
                    "accounts": [
                        {"id": "acc-1", "email": "user1@test.com", "accessToken": "t1"},
                        {"id": "acc-2", "email": "user2@test.com", "accessToken": "t2"},
                        {"id": "acc-3", "email": "user3@test.com", "accessToken": "t3"}
                    ]
                }, f)

            code = f"""
            const {{ AccountRotator }} = require("./proxy/account_rotator");
            const rotator = new AccountRotator({{ ACCOUNTS_FILE: {json.dumps(acc_file)}, ROTATOR_STATE_FILE: {json.dumps(state_file)} }});
            rotator.loadState();
            rotator.accounts[1].unhealthyUntil = Date.now() + 60000;

            function makeMockRes() {{
              return {{
                statusCode: 0,
                body: "",
                writeHead(code) {{ this.statusCode = code; }},
                end(payload) {{ this.body = payload; }}
              }};
            }}

            const resOk = makeMockRes();
            rotator.handleCommand("select", resOk, () => {{}}, {{ target: "user2@test.com" }});
            const afterOk = rotator.getCurrentAccount();

            const resMiss = makeMockRes();
            rotator.handleCommand("select", resMiss, () => {{}}, {{ target: "missing@test.com" }});
            const afterMiss = rotator.getCurrentAccount();

            console.log(JSON.stringify({{
              okStatus: resOk.statusCode,
              okJson: JSON.parse(resOk.body),
              afterOkEmail: afterOk.email,
              afterOkServed: rotator.currentAccRequestsServed,
              afterOkUnhealthy: afterOk.unhealthyUntil,
              missStatus: resMiss.statusCode,
              afterMissEmail: afterMiss.email
            }}));
            """
            output = json.loads(run_node(code))
            self.assertEqual(output["okStatus"], 200)
            self.assertTrue(output["okJson"]["success"])
            self.assertEqual(output["afterOkEmail"], "user2@test.com")
            self.assertEqual(output["afterOkServed"], 0)
            self.assertEqual(output["afterOkUnhealthy"], 0)
            self.assertEqual(output["missStatus"], 404)
            self.assertEqual(output["afterMissEmail"], "user2@test.com")

    def test_load_state_preserves_selected_account_after_reorder(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            acc_file = os.path.join(tmp_dir, "accounts.json")
            prof_file = os.path.join(tmp_dir, "profiles.json")
            state_file = os.path.join(tmp_dir, "rotator_state.json")
            with open(acc_file, "w") as f:
                json.dump({
                    "accounts": [
                        {"id": "uuid-1", "email": "user1@test.com", "accessToken": "t1"},
                        {"id": "uuid-2", "email": "user2@test.com", "accessToken": "t2"},
                        {"id": "uuid-3", "email": "user3@test.com", "accessToken": "t3"}
                    ]
                }, f)
            with open(prof_file, "w") as f:
                json.dump({
                    "settings": {"requests_per_account": 1, "auto_rotation_enabled": True, "active_account_id": ""},
                    "profiles": [
                        {"id": "user1_test_com", "email": "user1@test.com", "order": 1, "enabled": True},
                        {"id": "user2_test_com", "email": "user2@test.com", "order": 2, "enabled": True},
                        {"id": "user3_test_com", "email": "user3@test.com", "order": 3, "enabled": True}
                    ]
                }, f)

            code = f"""
            const fs = require("node:fs");
            const {{ AccountRotator }} = require("./proxy/account_rotator");
            const rotator = new AccountRotator({{
              ACCOUNTS_FILE: {json.dumps(acc_file)},
              PROFILES_FILE: {json.dumps(prof_file)},
              ROTATOR_STATE_FILE: {json.dumps(state_file)}
            }});
            rotator.loadState();
            rotator.selectAccount("user2@test.com");

            // Doi thu tu trong profiles.json dua user2 len vi tri 3
            const profData = JSON.parse(fs.readFileSync({json.dumps(prof_file)}, "utf8"));
            profData.profiles[0].order = 2;
            profData.profiles[1].order = 3;
            profData.profiles[2].order = 1;
            fs.writeFileSync({json.dumps(prof_file)}, JSON.stringify(profData), "utf8");
            rotator.loadState();
            const afterReorder = rotator.getCurrentAccount().email;

            // Thay doi settings.active_account_id sang slug cua user3
            profData.settings.active_account_id = "user3_test_com";
            fs.writeFileSync({json.dumps(prof_file)}, JSON.stringify(profData), "utf8");
            rotator.loadState();
            const afterActiveId = rotator.getCurrentAccount().email;

            console.log(JSON.stringify({{ afterReorder, afterActiveId }}));
            """
            output = json.loads(run_node(code))
            self.assertEqual(output["afterReorder"], "user2@test.com")
            self.assertEqual(output["afterActiveId"], "user3@test.com")

    def test_auto_rotation_disabled_keeps_pinned_account(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            acc_file = os.path.join(tmp_dir, "accounts.json")
            prof_file = os.path.join(tmp_dir, "profiles.json")
            state_file = os.path.join(tmp_dir, "rotator_state.json")
            with open(acc_file, "w") as f:
                json.dump({
                    "accounts": [
                        {"id": "uuid-1", "email": "user1@test.com", "accessToken": "t1"},
                        {"id": "uuid-2", "email": "user2@test.com", "accessToken": "t2"}
                    ]
                }, f)
            with open(prof_file, "w") as f:
                json.dump({
                    "settings": {
                        "requests_per_account": 1,
                        "auto_rotation_enabled": False,
                        "active_account_id": "user2_test_com"
                    },
                    "profiles": [
                        {"id": "user1_test_com", "email": "user1@test.com", "order": 1, "enabled": True},
                        {"id": "user2_test_com", "email": "user2@test.com", "order": 2, "enabled": True}
                    ]
                }, f)

            code = f"""
            const {{ AccountRotator }} = require("./proxy/account_rotator");
            const rotator = new AccountRotator({{
              ACCOUNTS_FILE: {json.dumps(acc_file)},
              PROFILES_FILE: {json.dumps(prof_file)},
              ROTATOR_STATE_FILE: {json.dumps(state_file)}
            }});
            rotator.loadState();
            const allocated = [];
            for (let i = 0; i < 5; i++) {{
              allocated.push(rotator.allocateAccountForRequest().account.email);
            }}
            console.log(JSON.stringify({{ paused: rotator.rotationPaused, allocated }}));
            """
            output = json.loads(run_node(code))
            self.assertTrue(output["paused"])
            self.assertEqual(output["allocated"], ["user2@test.com"] * 5)

    def test_oauth_url_includes_select_account_prompt(self):
        code = """
        const { buildGoogleAuthUrl } = require("./proxy/oauth_flow");
        const url = buildGoogleAuthUrl(
          { GOOGLE_CLIENT_ID: "cid-123" },
          "challenge-xyz",
          "state-abc",
          "http://localhost:20130/oauth/callback"
        );
        console.log(JSON.stringify({ url }));
        """
        output = json.loads(run_node(code))
        self.assertIn("prompt=select_account+consent", output["url"])

if __name__ == "__main__":
    unittest.main()
