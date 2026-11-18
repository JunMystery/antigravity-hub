# -*- coding: utf-8 -*-
"""Regression tests for concurrent proxy stream hang bugs in chat_handler and helpers."""

import json
import os
import subprocess
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_node(code: str) -> str:
    env = os.environ.copy()
    res = subprocess.run(
        ["node", "-e", code],
        cwd=REPO_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True
    )
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""


class TestProxyHangRemediation(unittest.TestCase):
    """Verify proxy never leaves clientRes hanging open on upstream stall, close, or failover."""

    def test_inactivity_timeout_after_200_destroys_client_res(self):
        """Reproduces 10:24:20 log bug: upstream sends 200 OK then stalls -> clientRes must be destroyed."""
        code = """
        const EventEmitter = require("node:events");
        const https = require("node:https");
        const { PassThrough } = require("node:stream");

        const capturedDelays = [];
        const origSetTimeout = global.setTimeout;
        global.setTimeout = (fn, ms, ...args) => {
          capturedDelays.push(ms);
          const effectiveMs = ms >= 10000 ? 40 : ms;
          return origSetTimeout(fn, effectiveMs, ...args);
        };

        https.request = (opts, cb) => {
          const req = new EventEmitter();
          req.destroyed = false;
          req.write = () => {};
          req.end = () => {
            origSetTimeout(() => {
              const gRes = new PassThrough();
              gRes.statusCode = 200;
              gRes.headers = { "content-type": "text/event-stream" };
              gRes.complete = false;
              cb(gRes);
            }, 5);
          };
          // Emulate Node behavior where gReq already ended and does NOT emit error when gRes destroyed first
          req.destroy = () => { req.destroyed = true; };
          return req;
        };

        const { executeGoogleChatRequest } = require("./proxy/chat_handler");
        const clientRes = new PassThrough();
        clientRes.headersSent = false;
        clientRes.writableEnded = false;
        clientRes.writeHead = () => { clientRes.headersSent = true; };
        let destroyCalled = false;
        const origDestroy = clientRes.destroy.bind(clientRes);
        clientRes.destroy = (err) => { destroyCalled = true; return origDestroy(err); };

        const acc = { id: "a1", email: "a1@test.com", accessToken: "ya29.ok", expiresAt: Date.now() + 3600000 };
        const ctx = {
          config: {}, accounts: [acc], requestsPerAccount: 10, requestCount: 1,
          currentAccRequestsServed: 1, rotationPaused: true,
          nextAccount: () => acc, writeLiveStatus: () => {}
        };

        executeGoogleChatRequest(acc, Buffer.from("{}"), "/v1internal:streamGenerateContent", "POST", {}, clientRes, ctx);

        origSetTimeout(() => {
          console.log(JSON.stringify({
            headersSent: clientRes.headersSent,
            clientDestroyed: clientRes.destroyed,
            destroyCalled,
            saw120s: capturedDelays.includes(120000),
            saw42s: capturedDelays.includes(42000)
          }));
          process.exit(0);
        }, 120);
        """
        out = json.loads(run_node(code))
        self.assertTrue(out["headersSent"])
        self.assertTrue(out["clientDestroyed"], "clientRes must be destroyed on post-200 inactivity timeout")
        self.assertTrue(out["destroyCalled"])
        self.assertTrue(out["saw120s"], "INACTIVITY_TIMEOUT_MS must be 120000ms")
        self.assertTrue(out["saw42s"], "TTFB_TIMEOUT_MS must remain 42000ms")

    def test_premature_upstream_close_without_end_destroys_client_res(self):
        """Upstream closes TCP mid-stream without emitting end (complete=false) -> clientRes destroyed."""
        code = """
        const EventEmitter = require("node:events");
        const https = require("node:https");
        const { PassThrough } = require("node:stream");

        https.request = (opts, cb) => {
          const req = new EventEmitter();
          req.destroyed = false;
          req.write = () => {};
          req.end = () => {
            setTimeout(() => {
              const gRes = new PassThrough();
              gRes.statusCode = 200;
              gRes.headers = {};
              gRes.complete = false;
              cb(gRes);
              setTimeout(() => { gRes.emit("close"); }, 15);
            }, 5);
          };
          req.destroy = () => { req.destroyed = true; };
          return req;
        };

        const { executeGoogleChatRequest } = require("./proxy/chat_handler");
        const clientRes = new PassThrough();
        clientRes.headersSent = false;
        clientRes.writableEnded = false;
        clientRes.writeHead = () => { clientRes.headersSent = true; };

        const acc = { id: "a1", email: "a1@test.com", accessToken: "ya29.ok", expiresAt: Date.now() + 3600000 };
        const ctx = {
          config: {}, accounts: [acc], requestsPerAccount: 10, requestCount: 1,
          currentAccRequestsServed: 1, rotationPaused: false,
          nextAccount: () => acc, writeLiveStatus: () => {}
        };

        executeGoogleChatRequest(acc, Buffer.from("{}"), "/v1internal:streamGenerateContent", "POST", {}, clientRes, ctx);
        setTimeout(() => {
          console.log(JSON.stringify({ clientDestroyed: clientRes.destroyed }));
          process.exit(0);
        }, 80);
        """
        out = json.loads(run_node(code))
        self.assertTrue(out["clientDestroyed"])

    def test_read_error_body_resolves_on_close_without_end(self):
        """readErrorBody must resolve immediately if response emits close without end."""
        code = """
        const EventEmitter = require("node:events");
        const { readErrorBody } = require("./proxy/chat_payload_helper");

        const fakeRes = new EventEmitter();
        fakeRes.destroyed = false;
        const p = readErrorBody(fakeRes, 2000);
        fakeRes.emit("data", Buffer.from("partial_429"));
        fakeRes.emit("close");
        p.then((text) => {
          console.log(JSON.stringify({ text }));
        });
        """
        out = json.loads(run_node(code))
        self.assertEqual(out["text"], "partial_429")

    def test_failover_detaches_previous_client_close_listener(self):
        """Failover across accounts must detach old clientRes close listeners (no listener leak)."""
        code = """
        const EventEmitter = require("node:events");
        const https = require("node:https");
        const { PassThrough } = require("node:stream");

        let callNum = 0;
        https.request = (opts, cb) => {
          callNum++;
          const currentCall = callNum;
          const req = new EventEmitter();
          req.destroyed = false;
          req.write = () => {};
          req.end = () => {
            setTimeout(() => {
              const gRes = new PassThrough();
              if (currentCall === 1) {
                gRes.statusCode = 429;
                gRes.headers = {};
                gRes.complete = true;
                cb(gRes);
                gRes.end("rate limited");
              } else {
                gRes.statusCode = 200;
                gRes.headers = {};
                gRes.complete = true;
                cb(gRes);
                gRes.end("ok");
              }
            }, 5);
          };
          req.destroy = () => { req.destroyed = true; };
          return req;
        };

        const { executeGoogleChatRequest } = require("./proxy/chat_handler");
        const clientRes = new PassThrough();
        clientRes.headersSent = false;
        clientRes.writableEnded = false;
        clientRes.writeHead = () => { clientRes.headersSent = true; };

        const acc1 = { id: "a1", email: "a1@test.com", accessToken: "ya29.1", expiresAt: Date.now() + 3600000 };
        const acc2 = { id: "a2", email: "a2@test.com", accessToken: "ya29.2", expiresAt: Date.now() + 3600000 };
        const ctx = {
          config: {}, accounts: [acc1, acc2], requestsPerAccount: 10, requestCount: 1,
          currentAccRequestsServed: 1, rotationPaused: false,
          nextAccount: () => acc2, writeLiveStatus: () => {}
        };

        executeGoogleChatRequest(acc1, Buffer.from("{}"), "/v1internal:streamGenerateContent", "POST", {}, clientRes, ctx);
        setTimeout(() => {
          console.log(JSON.stringify({
            callNum,
            closeListenersLeft: clientRes.listenerCount("close")
          }));
          process.exit(0);
        }, 80);
        """
        out = json.loads(run_node(code))
        self.assertEqual(out["callNum"], 2)
        self.assertEqual(out["closeListenersLeft"], 0)


if __name__ == "__main__":
    unittest.main()
