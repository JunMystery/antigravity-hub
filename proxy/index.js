#!/usr/bin/env node
/**
 * Antigravity Standalone Round Robin Token Rotator Proxy (Port: 20130)
 * Independent of 9router: Local SSL CA, Google OAuth PKCE, Epoch parsing,
 * Passthrough startup, Priority-based Round Robin, Instant Failover & auto-retry on 401.
 */

function getTimestampPrefix() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `[${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}]`;
}
const _origLog = console.log;
const _origWarn = console.warn;
const _origError = console.error;
console.log = (...args) => _origLog(getTimestampPrefix(), ...args);
console.warn = (...args) => _origWarn(getTimestampPrefix(), ...args);
console.error = (...args) => _origError(getTimestampPrefix(), ...args);

const http = require("node:http");
const https = require("node:https");
const net = require("node:net");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");

const { createLeafCertificate } = require("./cert_provider");
const { isAiChatEndpoint, executeGoogleChatRequest } = require("./chat_handler");
const { extractModelName } = require("./chat_payload_helper");
const { handleOAuthRoute } = require("./oauth_handler");
const { AccountRotator } = require("./account_rotator");
const { buildLiveStatusPayload } = require("./account_routing");
const { buildRequestContext } = require("./model_rule_engine");
const { agentPool } = require("./agent_pool");
const { sessionAffinity } = require("./session_affinity");
const { destroyStream, attachConnectTunnelCleanup, handleClientError } = require("./socket_cleanup");

const PROXY_PORT = 20130;
const userHome = os.homedir();
const isWin = process.platform === "win32" && process.env.APPDATA;
const CONFIG_DIR = isWin ? path.join(process.env.APPDATA, "antigravity-launcher") : path.join(userHome, ".config", "antigravity-launcher");
const CERTS_DIR = path.join(CONFIG_DIR, "certs");
const LEGACY_CERTS_DIR = path.join(__dirname, "certs");
const ACCOUNTS_FILE = path.join(CONFIG_DIR, "accounts.json");
const PROFILES_FILE = path.join(CONFIG_DIR, "profiles.json");
const PROFILES_BASE_DIR = isWin ? path.join(process.env.APPDATA, "Antigravity-Profiles") : path.join(userHome, ".config", "Antigravity-Profiles");
const STATUS_FILE = path.join(CONFIG_DIR, "live_status.json");
const CMD_FILE = path.join(CONFIG_DIR, "proxy_cmd.json");
const ROTATOR_STATE_FILE = path.join(CONFIG_DIR, "rotator_state.json");

const DEFAULT_CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com";
const DEFAULT_CLIENT_SECRET = "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";

const CONFIG = {
  GOOGLE_CLIENT_ID: process.env.GOOGLE_CLIENT_ID || DEFAULT_CLIENT_ID,
  GOOGLE_CLIENT_SECRET: process.env.GOOGLE_CLIENT_SECRET || DEFAULT_CLIENT_SECRET,
  ACCOUNTS_FILE, PROFILES_FILE, ROTATOR_STATE_FILE
};

function writeLiveStatus(info) {
  try {
    fs.writeFileSync(STATUS_FILE, JSON.stringify(info, null, 2), "utf8");
  } catch (_) {}
}

function migrateLegacyCerts() {
  const targetCrt = path.join(CERTS_DIR, "ca.crt");
  const targetKey = path.join(CERTS_DIR, "ca.key");
  if (fs.existsSync(targetCrt) && fs.existsSync(targetKey)) return;
  const legacyCrt = path.join(LEGACY_CERTS_DIR, "ca.crt");
  const legacyKey = path.join(LEGACY_CERTS_DIR, "ca.key");
  if (fs.existsSync(legacyCrt) && fs.existsSync(legacyKey)) {
    fs.mkdirSync(CERTS_DIR, { recursive: true });
    fs.copyFileSync(legacyCrt, targetCrt);
    fs.copyFileSync(legacyKey, targetKey);
  }
}

console.log("[MITM-INIT] Khoi tao chung chi SSL cho *.googleapis.com...");
migrateLegacyCerts();
const leafCredentials = createLeafCertificate(CERTS_DIR);
console.log("[MITM-INIT] [OK] Chung chi SSL da san sang.");

const rotator = new AccountRotator(CONFIG);
rotator.loadState();
setInterval(() => rotator.loadState(false), 5000);
const curInitAcc = rotator.getCurrentAccount();
console.log(`[ROUND-ROBIN] Da nap ${rotator.accounts.length} tai khoan active (Khoi tao tai: [${curInitAcc?.email || "Chua co"}], nguong: ${rotator.requestsPerAccount} req/tai khoan).`);

function getRequestContext(sessionId = null, isSubagent = false, allocation = null) {
  return buildRequestContext(rotator, CONFIG, writeLiveStatus, sessionId, isSubagent, allocation);
}

const oauthContext = {
  config: CONFIG, proxyPort: PROXY_PORT, profilesFile: PROFILES_FILE, profilesBaseDir: PROFILES_BASE_DIR,
  loadState: () => rotator.loadState(), writeLiveStatus,
  get requestsPerAccount() { return rotator.requestsPerAccount; },
  get requestCount() { return rotator.requestCount; }
};

// Internal HTTPS Server for SSL Decryption
const internalHttpsServer = https.createServer(leafCredentials, (req, res) => {
  const reqUrl = req.url || "/";
  const isChat = isAiChatEndpoint(reqUrl);

  if (!isChat) {
    const rawHost = req.headers["host"] || "daily-cloudcode-pa.googleapis.com";
    const host = rawHost.split(":")[0];
    const fwdHeaders = { ...req.headers };
    delete fwdHeaders["host"];
    fwdHeaders["host"] = host;

    let activeGRes = null;

    const gReq = https.request({
      hostname: host, port: 443, path: reqUrl, method: req.method,
      headers: fwdHeaders, timeout: 30000
    }, (gRes) => {
      activeGRes = gRes;
      if (gRes.statusCode === 401) {
        console.warn(`[AUTH-SHIELD] [NON-CHAT] Upstream 401 on: ${reqUrl}. Forwarding status directly to client.`);
      }
      res.writeHead(gRes.statusCode, gRes.headers);
      gRes.pipe(res);
      gRes.on("close", () => {
        activeGRes = null;
        if (!gRes.complete && !res.writableEnded && !res.destroyed) {
          res.destroy();
        }
      });
      gRes.on("end", () => { activeGRes = null; });
      gRes.on("error", () => {
        destroyStream(gRes);
        activeGRes = null;
        if (!res.writableEnded) res.end();
      });
    });

    gReq.on("timeout", () => {
      console.warn(`[NON-CHAT-TIMEOUT] Timeout 30s tren endpoint non-chat: ${reqUrl}`);
      if (activeGRes) destroyStream(activeGRes);
      gReq.destroy(new Error("Non-chat request timeout"));
    });

    gReq.on("error", (e) => {
      if (activeGRes) destroyStream(activeGRes);
      if (!res.headersSent) {
        res.writeHead(502, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Bad Gateway", message: e.message }));
      } else if (!res.writableEnded) {
        res.end();
      }
    });

    res.on("close", () => {
      if (activeGRes) destroyStream(activeGRes);
      if (!gReq.destroyed) destroyStream(gReq);
    });

    req.pipe(gReq);
    return;
  }

  // AI Chat & Subagent requests
  const chunks = [];
  req.on("error", () => {
    if (!res.writableEnded && !res.destroyed) res.destroy();
  });
  req.on("data", (chunk) => chunks.push(chunk));
  req.on("end", async () => {
    const bodyBuffer = Buffer.concat(chunks);
    const rawHost = req.headers["host"] || "daily-cloudcode-pa.googleapis.com";
    const allocation = rotator.allocateAccountForRequest(reqUrl, rawHost, req.headers, bodyBuffer);
    const currentAcc = allocation.account;
    const isSub = allocation.isSubagent;
    const accName = currentAcc ? currentAcc.email : "UNKNOWN";
    const servedCount = allocation.servedCount;
    const reqThreshold = allocation.requestsPerAccount || rotator.requestsPerAccount;
    const reqNum = allocation.requestNumber;
    const tag = isSub ? "[SUBAGENT]" : "[MAIN]";
    const stickyFlag = allocation.isSticky ? "[STICKY] " : (allocation.isNewSubagent ? "[NEW-SUB] " : "");
    const modelName = allocation.modelName || extractModelName(reqUrl, bodyBuffer);
    const modelTag = modelName ? `[MODEL: ${modelName}] ` : "";
    const lockTag = allocation.lockReason === "model_rule"
      ? `[RULE: ${allocation.matchedRule}] `
      : (allocation.lockReason === "pinned" ? "[PINNED] " : "");

    console.log(`[ROUND-ROBIN #${reqNum}] ${tag} ${stickyFlag}${lockTag}${req.method} ${modelTag}${reqUrl.split("?")[0]} -> [ACC: ${accName}] (${servedCount}/${reqThreshold} req)`);

    writeLiveStatus(buildLiveStatusPayload(rotator, {
      active: true, account: currentAcc, account_email: accName,
      account_name: currentAcc?.name || accName, current_req: servedCount,
      requests_per_account: reqThreshold,
      total_requests: reqNum, endpoint: `${tag} ${reqUrl.split("?")[0]}`,
      method: req.method, status: "sending", model_routed: allocation.matchedRule || "",
      model_rule_strategy: allocation.ruleStrategy || ""
    }));

    executeGoogleChatRequest(currentAcc, bodyBuffer, reqUrl, req.method, req.headers, res, getRequestContext(allocation.sessionId, isSub, allocation))
      .catch((err) => {
        console.error(`[CHAT-HANDLER-ERR] Loi khong mong doi tren [${accName}]:`, err.message);
        if (!res.headersSent && !res.destroyed && !res.closed) {
          res.writeHead(502, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "Bad Gateway", message: err.message }));
        } else if (!res.writableEnded && !res.destroyed) {
          res.destroy();
        }
      });
  });
});
internalHttpsServer.requestTimeout = 0;
internalHttpsServer.on("clientError", handleClientError);

function checkCmdFile() {
  if (fs.existsSync(CMD_FILE)) {
    try {
      const content = fs.readFileSync(CMD_FILE, "utf8").trim();
      fs.unlinkSync(CMD_FILE);
      if (content) {
        const cmdObj = JSON.parse(content);
        if (cmdObj.cmd) rotator.handleCommand(cmdObj.cmd, null, writeLiveStatus, cmdObj);
      }
    } catch (_) {}
  }
}
setInterval(checkCmdFile, 500);

// Proxy HTTP Server (handles CONNECT tunnels, Control API & OAuth callback)
const proxyServer = http.createServer(async (req, res) => {
  try {
    const isOAuth = await handleOAuthRoute(req, res, oauthContext);
    if (isOAuth) return;

    const parsedUrl = new URL(req.url, `http://${req.headers.host || "127.0.0.1"}`);
    if (parsedUrl.pathname === "/_proxy_action") {
      const params = Object.fromEntries(parsedUrl.searchParams.entries());
      rotator.handleCommand(params.cmd, res, writeLiveStatus, params);
      return;
    }
  } catch (_) {}
  res.writeHead(200, { "Content-Type": "text/plain" });
  res.end("Antigravity Standalone Round Robin Proxy is running.\n");
});

proxyServer.on("connect", (req, clientSocket, head) => {
  const [targetHost, targetPort] = req.url.split(":");
  const port = parseInt(targetPort, 10) || 443;
  const isTargetAiHost = /cloudcode|companion|generativelanguage/i.test(targetHost);

  if (isTargetAiHost) {
    clientSocket.write("HTTP/1.1 200 Connection Established\r\n\r\n");
    if (head && head.length > 0) clientSocket.unshift(head);
    internalHttpsServer.emit("connection", clientSocket);
    return;
  }

  const serverSocket = net.connect(port, targetHost, () => {
    clientSocket.write("HTTP/1.1 200 Connection Established\r\n\r\n");
    serverSocket.write(head);
    serverSocket.pipe(clientSocket);
    clientSocket.pipe(serverSocket);
  });
  attachConnectTunnelCleanup(clientSocket, serverSocket);
});
proxyServer.on("clientError", handleClientError);

proxyServer.listen(PROXY_PORT, "127.0.0.1", () => {
  const initAcc = rotator.getCurrentAccount() || rotator.accounts[0];
  writeLiveStatus(buildLiveStatusPayload(rotator, {
    account: initAcc,
    account_email: initAcc?.email || "San sang",
    account_name: initAcc?.name || initAcc?.email || "San sang"
  }));

  console.log(`\n============================================================`);
  console.log(`[PROXY] Antigravity Standalone Round Robin Proxy dang chay (Port ${PROXY_PORT})`);
  console.log(`   Tai khoan tham gia: ${rotator.accounts.length} accounts`);
  console.log(`   Tai khoan hien tai: ${initAcc?.email || "None"} (${rotator.currentAccRequestsServed}/${rotator.requestsPerAccount} req)`);
  console.log(`   Nguong chuyen doi: ${rotator.requestsPerAccount} request/tai khoan`);
  console.log(`   Socket Pool: Dedicated Per-Account HTTPS Agent active`);
  console.log(`============================================================\n`);
});

function gracefulShutdown() {
  rotator.saveRotatorState();
  agentPool.clearAllAgents();
  process.exit(0);
}

process.on("SIGINT", gracefulShutdown);
process.on("SIGTERM", gracefulShutdown);
process.on("exit", () => {
  rotator.saveRotatorState();
  agentPool.clearAllAgents();
});
