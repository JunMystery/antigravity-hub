"""
Unit tests for Proxy remediations (P0-1 through P0-5 and P1-1 through P1-5).
"""

import json
import os
import subprocess
import tempfile
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_node(code: str) -> str:
    """Run Node.js snippet in the repo directory and return stdout."""
    res = subprocess.run(
        ["node", "-e", code],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    # Return the last non-empty line (in case logs were emitted earlier)
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""


class TestCertProviderRemediation(unittest.TestCase):
    """P0-1: Leaf certificate bundles Root CA and includes serverAuth EKU."""

    def test_cert_bundling_and_eku(self):
        code = """
        const { createLeafCertificate } = require("./proxy/cert_provider");
        const path = require("path");
        const creds = createLeafCertificate(path.join(__dirname, "proxy/certs"));
        const certCount = (creds.cert.match(/BEGIN CERTIFICATE/g) || []).length;
        console.log(JSON.stringify({ certCount, hasCaProp: !!creds.ca }));
        """
        output = json.loads(run_node(code))
        self.assertEqual(output["certCount"], 2, "Leaf cert must bundle Root CA")
        self.assertTrue(output["hasCaProp"], "Credentials object must include ca property")

        # Verify openssl EKU parsing
        openssl_check = subprocess.run(
            ["node", "-e", """
            const { createLeafCertificate } = require("./proxy/cert_provider");
            const path = require("path");
            const creds = createLeafCertificate(path.join(__dirname, "proxy/certs"));
            process.stdout.write(creds.cert);
            """],
            cwd=REPO_DIR,
            capture_output=True,
            text=True,
            check=True
        )
        x509_out = subprocess.run(
            ["openssl", "x509", "-text", "-noout"],
            input=openssl_check.stdout,
            capture_output=True,
            text=True,
            check=True
        )
        self.assertIn("TLS Web Server Authentication", x509_out.stdout)


class TestTokenManagerRemediation(unittest.TestCase):
    """P0-3: Deduplicate in-flight token refresh promises."""

    def test_in_flight_promise_deduplication(self):
        code = """
        const { refreshGoogleAccessToken } = require("./proxy/token_manager");
        let fetchCount = 0;
        global.fetch = async () => {
          fetchCount++;
          await new Promise(r => setTimeout(r, 60));
          return {
            ok: true,
            json: async () => ({ access_token: "mock-token", expires_in: 3600 })
          };
        };
        const account = { id: "acc-dedup", email: "dedup@test.com", refreshToken: "plain" };
        const config = { GOOGLE_CLIENT_ID: "cid", GOOGLE_CLIENT_SECRET: "csec" };
        (async () => {
          const [r1, r2, r3] = await Promise.all([
            refreshGoogleAccessToken(account, config),
            refreshGoogleAccessToken(account, config),
            refreshGoogleAccessToken(account, config)
          ]);
          console.log(JSON.stringify({ fetchCount, allSame: r1 === r2 && r2 === r3 }));
        })();
        """
        output = json.loads(run_node(code))
        self.assertEqual(output["fetchCount"], 1, "Concurrent refreshes must share 1 fetch call")
        self.assertTrue(output["allSame"], "All callers must receive identical resolved account")


class TestChatPayloadHelperRemediation(unittest.TestCase):
    """P1-2: Payload preservation (GCP project, array metadata, ideVersion)."""

    def test_gcp_project_preservation(self):
        code = """
        const { rewriteChatPayload } = require("./proxy/chat_payload_helper");
        const body = JSON.stringify({ project: "custom-gcp-corp", contents: [] });
        const res = JSON.parse(rewriteChatPayload(Buffer.from(body), { projectId: "other" }, "cloudcode").toString());
        console.log(JSON.stringify({ project: res.project }));
        """
        output = json.loads(run_node(code))
        self.assertEqual(output["project"], "custom-gcp-corp")

    def test_array_metadata_not_polluted(self):
        code = """
        const { rewriteChatPayload } = require("./proxy/chat_payload_helper");
        const body = JSON.stringify({ project: "p", metadata: ["item1", "item2"] });
        const res = JSON.parse(rewriteChatPayload(Buffer.from(body), {}, "cloudcode").toString());
        console.log(JSON.stringify({ isArray: Array.isArray(res.metadata), hasIdeVer: "ideVersion" in res.metadata }));
        """
        output = json.loads(run_node(code))
        self.assertTrue(output["isArray"])
        self.assertFalse(output["hasIdeVer"])

    def test_existing_ide_version_preserved(self):
        code = """
        const { rewriteChatPayload } = require("./proxy/chat_payload_helper");
        const body = JSON.stringify({ project: "p", metadata: { ideVersion: "3.0.0" } });
        const res = JSON.parse(rewriteChatPayload(Buffer.from(body), {}, "cloudcode").toString());
        console.log(JSON.stringify({ ideVersion: res.metadata.ideVersion }));
        """
        output = json.loads(run_node(code))
        self.assertEqual(output["ideVersion"], "3.0.0")


class TestSessionAffinityRemediation(unittest.TestCase):
    """P1-3: Subagent classification & 30m TTL."""

    def test_models_url_not_subagent(self):
        code = """
        const { sessionAffinity } = require("./proxy/session_affinity");
        const isSub = sessionAffinity.isSubagent("/v1beta/models/gemini-pro:generateContent", "generativelanguage.googleapis.com");
        console.log(JSON.stringify({ isSub }));
        """
        output = json.loads(run_node(code))
        self.assertFalse(output["isSub"], "Canonical /models/ URL must not be classified as subagent")

    def test_explicit_header_is_subagent(self):
        code = """
        const { sessionAffinity } = require("./proxy/session_affinity");
        const isSub = sessionAffinity.isSubagent("/v1/chat", "daily-cloudcode-pa.googleapis.com", { "x-subagent-id": "sub-1" });
        console.log(JSON.stringify({ isSub }));
        """
        output = json.loads(run_node(code))
        self.assertTrue(output["isSub"], "Header x-subagent-id must be classified as subagent")


class TestAgentPoolRemediation(unittest.TestCase):
    """P1-4: Extended Thinking timeout >= 120s."""

    def test_timeout_value(self):
        code = """
        const { agentPool } = require("./proxy/agent_pool");
        const agent = agentPool.getAgentForAccount({ email: "thinker@test.com" });
        console.log(JSON.stringify({ timeout: agent.options.timeout }));
        """
        output = json.loads(run_node(code))
        self.assertGreaterEqual(output["timeout"], 120000)


class TestAccountRotatorCooldownRemediation(unittest.TestCase):
    """P0-5 & P1-5: Cooldown preservation and debounced async persistence."""

    def test_cooldown_preservation_across_reload(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            acc_file = os.path.join(tmp_dir, "accounts.json")
            with open(acc_file, "w") as f:
                json.dump({"accounts": [{"id": "acc-1", "email": "a1@test.com", "accessToken": "t1"}]}, f)

            code = f"""
            const {{ AccountRotator }} = require("./proxy/account_rotator");
            const rotator = new AccountRotator({{ ACCOUNTS_FILE: {json.dumps(acc_file)} }});
            rotator.loadState();
            const cooldown = Date.now() + 60000;
            rotator.accounts[0].unhealthyUntil = cooldown;
            rotator.loadState();
            console.log(JSON.stringify({{ preserved: rotator.accounts[0].unhealthyUntil === cooldown }}));
            """
            output = json.loads(run_node(code))
            self.assertTrue(output["preserved"])


if __name__ == "__main__":
    unittest.main()
