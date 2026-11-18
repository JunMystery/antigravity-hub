# -*- coding: utf-8 -*-
"""Regression tests for concurrent proxy stream hang, TTFB budget, and abort-loop remediation."""

import json
import os
import subprocess
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MOCK_CTX_HELPER = """
const EventEmitter = require("node:events");
const https = require("node:https");
const { PassThrough } = require("node:stream");
function makeClientRes() {
  const r = new PassThrough();
  r.headersSent = false;
  r.writableEnded = false;
  r.writeHead = () => { r.headersSent = true; };
  return r;
}
function makeCtx(acc, nextFn) {
  return {
    config: {}, accounts: Array.isArray(acc) ? acc : [acc], requestsPerAccount: 10,
    requestCount: 1, currentAccRequestsServed: 1, rotationPaused: false,
    nextAccount: nextFn || (() => (Array.isArray(acc) ? acc[acc.length - 1] : acc)),
    writeLiveStatus: () => {}
  };
}
"""


def run_node(code: str) -> str:
    res = subprocess.run(
        ["node", "-e", code],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True
    )
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""


class TestProxyHangRemediation(unittest.TestCase):
    """Verify proxy never leaves clientRes hanging open and breaks timeout/abort loops."""

    def test_inactivity_timeout_after_200_destroys_client_res(self):
        code = MOCK_CTX_HELPER + """
        const capturedDelays = [];
        const origSetTimeout = global.setTimeout;
        global.setTimeout = (fn, ms, ...args) => {
          capturedDelays.push(ms);
          return origSetTimeout(fn, ms >= 10000 ? 40 : ms, ...args);
        };
        https.request = (opts, cb) => {
          const req = Object.assign(new EventEmitter(), { destroyed: false, write() {}, destroy() { this.destroyed = true; } });
          req.end = () => origSetTimeout(() => {
            const gRes = Object.assign(new PassThrough(), { statusCode: 200, headers: { "content-type": "text/event-stream" }, complete: false });
            cb(gRes);
          }, 5);
          return req;
        };
        const { executeGoogleChatRequest } = require("./proxy/chat_handler");
        const clientRes = makeClientRes();
        let destroyCalled = false;
        const origDestroy = clientRes.destroy.bind(clientRes);
        clientRes.destroy = (err) => { destroyCalled = true; return origDestroy(err); };
        const acc = { id: "a1", email: "a1@test.com", accessToken: "ya29.ok", expiresAt: Date.now() + 3600000 };
        executeGoogleChatRequest(acc, Buffer.from("{}"), "/v1internal:streamGenerateContent", "POST", {}, clientRes, makeCtx(acc));
        origSetTimeout(() => {
          console.log(JSON.stringify({
            headersSent: clientRes.headersSent, clientDestroyed: clientRes.destroyed, destroyCalled,
            saw120s: capturedDelays.includes(120000), saw45s: capturedDelays.includes(45000)
          }));
          process.exit(0);
        }, 120);
        """
        out = json.loads(run_node(code))
        self.assertTrue(out["headersSent"])
        self.assertTrue(out["clientDestroyed"])
        self.assertTrue(out["destroyCalled"])
        self.assertTrue(out["saw120s"])
        self.assertTrue(out["saw45s"])

    def test_premature_upstream_close_without_end_destroys_client_res(self):
        code = MOCK_CTX_HELPER + """
        https.request = (opts, cb) => {
          const req = Object.assign(new EventEmitter(), { destroyed: false, write() {}, destroy() { this.destroyed = true; } });
          req.end = () => setTimeout(() => {
            const gRes = Object.assign(new PassThrough(), { statusCode: 200, headers: {}, complete: false });
            cb(gRes);
            setTimeout(() => gRes.emit("close"), 15);
          }, 5);
          return req;
        };
        const { executeGoogleChatRequest } = require("./proxy/chat_handler");
        const clientRes = makeClientRes();
        const acc = { id: "a1", email: "a1@test.com", accessToken: "ya29.ok", expiresAt: Date.now() + 3600000 };
        executeGoogleChatRequest(acc, Buffer.from("{}"), "/v1internal:streamGenerateContent", "POST", {}, clientRes, makeCtx(acc));
        setTimeout(() => { console.log(JSON.stringify({ clientDestroyed: clientRes.destroyed })); process.exit(0); }, 80);
        """
        self.assertTrue(json.loads(run_node(code))["clientDestroyed"])

    def test_read_error_body_resolves_on_close_without_end(self):
        code = """
        const EventEmitter = require("node:events");
        const { readErrorBody } = require("./proxy/chat_payload_helper");
        const fakeRes = Object.assign(new EventEmitter(), { destroyed: false });
        const p = readErrorBody(fakeRes, 2000);
        fakeRes.emit("data", Buffer.from("partial_429"));
        fakeRes.emit("close");
        p.then((text) => console.log(JSON.stringify({ text })));
        """
        self.assertEqual(json.loads(run_node(code))["text"], "partial_429")

    def test_failover_detaches_previous_client_close_listener(self):
        code = MOCK_CTX_HELPER + """
        let callNum = 0;
        https.request = (opts, cb) => {
          const cur = ++callNum;
          const req = Object.assign(new EventEmitter(), { destroyed: false, write() {}, destroy() { this.destroyed = true; } });
          req.end = () => setTimeout(() => {
            const gRes = Object.assign(new PassThrough(), { statusCode: cur === 1 ? 429 : 200, headers: {}, complete: true });
            cb(gRes);
            gRes.end(cur === 1 ? "rate limited" : "ok");
          }, 5);
          return req;
        };
        const { executeGoogleChatRequest } = require("./proxy/chat_handler");
        const clientRes = makeClientRes();
        const acc1 = { id: "a1", email: "a1@test.com", accessToken: "ya29.1", expiresAt: Date.now() + 3600000 };
        const acc2 = { id: "a2", email: "a2@test.com", accessToken: "ya29.2", expiresAt: Date.now() + 3600000 };
        executeGoogleChatRequest(acc1, Buffer.from("{}"), "/v1internal:streamGenerateContent", "POST", {}, clientRes, makeCtx([acc1, acc2], () => acc2));
        setTimeout(() => { console.log(JSON.stringify({ callNum, closeListenersLeft: clientRes.listenerCount("close") })); process.exit(0); }, 80);
        """
        out = json.loads(run_node(code))
        self.assertEqual(out["callNum"], 2)
        self.assertEqual(out["closeListenersLeft"], 0)

    def test_budget_aware_ttfb_and_hop_by_hop_headers(self):
        code = """
        const { computeTtfbTimeoutMs, hasFailoverBudget, buildForwardHeaders } = require("./proxy/chat_payload_helper");
        const t0 = 100000;
        const hdrs = buildForwardHeaders(
          { "connection": "keep-alive", "proxy-connection": "keep-alive", "keep-alive": "timeout=5", "transfer-encoding": "chunked", "expect": "100-continue", "content-type": "application/json" },
          "daily-cloudcode-pa.googleapis.com",
          { accessToken: "ya29.abc" },
          Buffer.from('{"a":1}')
        );
        console.log(JSON.stringify({
          a1: computeTtfbTimeoutMs(1, t0, t0),
          a2: computeTtfbTimeoutMs(2, t0, t0 + 25000),
          a3: computeTtfbTimeoutMs(3, t0, t0 + 47000),
          canRetryAt25: hasFailoverBudget(t0, null, t0 + 25000),
          canRetryAt50: hasFailoverBudget(t0, null, t0 + 50000),
          largeBlockedAt35: !hasFailoverBudget(t0, Buffer.alloc(35000), t0 + 35000),
          hasHopByHop: Boolean(hdrs["connection"] || hdrs["proxy-connection"] || hdrs["keep-alive"] || hdrs["expect"] || hdrs["transfer-encoding"]),
          auth: hdrs["authorization"],
          clen: hdrs["content-length"]
        }));
        """
        out = json.loads(run_node(code))
        self.assertEqual((out["a1"], out["a2"], out["a3"]), (45000, 33000, 11000))
        self.assertTrue(out["canRetryAt25"])
        self.assertFalse(out["canRetryAt50"])
        self.assertTrue(out["largeBlockedAt35"])
        self.assertFalse(out["hasHopByHop"])
        self.assertEqual(out["auth"], "Bearer ya29.abc")
        self.assertEqual(out["clen"], 7)

    def test_fresh_socket_retry_on_socket_hang_up_does_not_failover(self):
        code = MOCK_CTX_HELPER + """
        let attempts = 0, nextCalled = 0;
        https.request = (opts, cb) => {
          attempts++;
          const req = Object.assign(new EventEmitter(), { destroyed: false, write() {}, destroy() { this.destroyed = true; } });
          req.end = () => setTimeout(() => {
            if (attempts === 1) {
              req.emit("error", new Error("socket hang up"));
            } else {
              const gRes = Object.assign(new PassThrough(), { statusCode: 200, headers: {}, complete: true });
              cb(gRes);
              gRes.end("ok");
            }
          }, 5);
          return req;
        };
        const { executeGoogleChatRequest } = require("./proxy/chat_handler");
        const clientRes = makeClientRes();
        const acc = { id: "a1", email: "a1@test.com", accessToken: "ya29.1", expiresAt: Date.now() + 3600000 };
        executeGoogleChatRequest(acc, Buffer.from("{}"), "/v1internal:streamGenerateContent", "POST", {}, clientRes, makeCtx([acc], () => { nextCalled++; return acc; }));
        setTimeout(() => {
          console.log(JSON.stringify({ attempts, nextCalled, unhealthy: Boolean(acc.unhealthyUntil) }));
          process.exit(0);
        }, 80);
        """
        out = json.loads(run_node(code))
        self.assertEqual(out["attempts"], 2)
        self.assertEqual(out["nextCalled"], 0)
        self.assertFalse(out["unhealthy"])

    def test_network_timeout_does_not_set_unhealthy_until(self):
        code = MOCK_CTX_HELPER + """
        https.request = (opts, cb) => {
          const req = Object.assign(new EventEmitter(), { destroyed: false, write() {}, destroy() { this.destroyed = true; } });
          req.end = () => setTimeout(() => {
            req.emit("error", new Error("Upstream connection timeout"));
          }, 5);
          return req;
        };
        const { executeGoogleChatRequest } = require("./proxy/chat_handler");
        const clientRes = makeClientRes();
        const acc = { id: "a1", email: "a1@test.com", accessToken: "ya29.1", expiresAt: Date.now() + 3600000 };
        executeGoogleChatRequest(acc, Buffer.from("{}"), "/v1internal:streamGenerateContent", "POST", {}, clientRes, makeCtx([acc]));
        setTimeout(() => {
          console.log(JSON.stringify({ unhealthy: Boolean(acc.unhealthyUntil) }));
          process.exit(0);
        }, 60);
        """
        out = json.loads(run_node(code))
        self.assertFalse(out["unhealthy"])

    def test_pre_header_abort_on_failover_rotates_and_purges_agent(self):
        code = MOCK_CTX_HELPER + """
        const { agentPool } = require("./proxy/agent_pool");
        let nextCalled = 0, destroyedKey = null;
        const origDestroyAgent = agentPool.destroyAgentForAccount.bind(agentPool);
        agentPool.destroyAgentForAccount = (acc) => { destroyedKey = acc?.email || null; return origDestroyAgent(acc); };
        https.request = () => Object.assign(new EventEmitter(), { destroyed: false, write() {}, end() {}, destroy() { this.destroyed = true; } });
        const { executeGoogleChatRequest } = require("./proxy/chat_handler");
        const clientRes = makeClientRes();
        const acc = { id: "a3", email: "ai3@test.com", accessToken: "ya29.3", expiresAt: Date.now() + 3600000 };
        executeGoogleChatRequest(acc, Buffer.from("{}"), "/v1internal:streamGenerateContent", "POST", {}, clientRes, makeCtx(acc, () => { nextCalled++; return acc; }), 2);
        setTimeout(() => {
          clientRes.emit("close");
          setTimeout(() => { console.log(JSON.stringify({ nextCalled, destroyedKey })); process.exit(0); }, 20);
        }, 20);
        """
        out = json.loads(run_node(code))
        self.assertEqual(out["nextCalled"], 1)
        self.assertEqual(out["destroyedKey"], "ai3@test.com")


if __name__ == "__main__":
    unittest.main()
