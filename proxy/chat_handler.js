const https = require("node:https");
const { ensureValidToken, refreshGoogleAccessToken } = require("./token_manager");
const { getAgentForAccount } = require("./agent_pool");
const { sessionAffinity } = require("./session_affinity");
const { destroyStream, attachClientCloseHandler } = require("./socket_cleanup");
const { extractUsageMetadata, recordTokens, formatTokenCount } = require("./token_tracker");
const {
  isAiChatEndpoint,
  rewriteChatPayload,
  readErrorBody,
  create503AuthShieldPayload
} = require("./chat_payload_helper");

// Gui Chat Request voi Dedicated Agent, Dynamic Rewrite, Auto-Failover va Auth Shield
async function executeGoogleChatRequest(account, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context, attempt = 1) {
  const totalAccs = context.accounts.length || 1;
  const accName = account ? account.email : "UNKNOWN";
  const rawHost = origHeaders["host"] || "daily-cloudcode-pa.googleapis.com";
  const host = rawHost.split(":")[0];

  function terminateClient(reason) {
    if (clientRes.writableEnded || clientRes.destroyed || clientRes.closed) return;
    if (!clientRes.headersSent) {
      clientRes.writeHead(504, { "Content-Type": "application/json" });
      clientRes.end(JSON.stringify({ error: "Gateway Timeout", message: reason }));
    } else {
      console.warn(`[ABORT-STREAM] Destroy clientRes (${reason}) cho [${accName}]`);
      clientRes.destroy();
    }
  }

  try {
    if (clientRes.destroyed || clientRes.closed) {
      console.log(`[CLIENT-CLOSED] Ket noi IDE da dong truoc khi gui request cho [${accName}]`);
      return;
    }
    if (account) await ensureValidToken(account, context.config);
    if (clientRes.destroyed || clientRes.closed) return;

    const finalBodyBuffer = rewriteChatPayload(bodyBuffer, account, host);
    const isSubagent = context.isSubagent !== undefined
      ? context.isSubagent
      : sessionAffinity.isSubagent(reqUrl, host, origHeaders, bodyBuffer, context.sessionId);
    const tag = isSubagent ? "[SUBAGENT]" : "[MAIN]";

    const userAgent = origHeaders["user-agent"] || (process.platform === "win32" ? "antigravity/2.24.0 win32/x64" : "antigravity/2.24.0 linux/x64");
    const fwdHeaders = { ...origHeaders, host, "user-agent": userAgent };
    delete fwdHeaders["host"];
    fwdHeaders["host"] = host;
    if (!fwdHeaders["x-client-name"]) fwdHeaders["x-client-name"] = "antigravity";
    if (!fwdHeaders["x-client-version"]) fwdHeaders["x-client-version"] = "2.24.0";

    if (account && account.accessToken) {
      fwdHeaders["authorization"] = `Bearer ${account.accessToken}`;
    }
    // RFC 7230 §3.3.2 / RFC 9112 §6.1: Delete Transfer-Encoding when sending Content-Length
    delete fwdHeaders["transfer-encoding"];
    delete fwdHeaders["Transfer-Encoding"];
    if (finalBodyBuffer && finalBodyBuffer.length > 0) {
      fwdHeaders["content-length"] = finalBodyBuffer.length;
    }

    // 42s TTFB: chu dong failover truoc nguong timeout 60s cua client IDE
    const TTFB_TIMEOUT_MS = 42000;
    const INACTIVITY_TIMEOUT_MS = 120000; // 120s sliding window cho thinking model context lon

    const outgoingOptions = {
      hostname: host, port: 443, path: reqUrl, method: reqMethod,
      headers: fwdHeaders, agent: getAgentForAccount(account)
    };

    let activeGRes = null;
    let isAborted = false;
    let sessionEnded = false;
    let timeoutTimer = null;
    let detachClientClose = () => {};

    function clearAllTimeout() {
      if (timeoutTimer) {
        clearTimeout(timeoutTimer);
        timeoutTimer = null;
      }
    }

    function safeEndSession() {
      clearAllTimeout();
      detachClientClose();
      if (!sessionEnded) {
        sessionEnded = true;
        sessionAffinity.endRequest();
      }
    }

    function resetTimeout(ms) {
      clearAllTimeout();
      timeoutTimer = setTimeout(() => {
        console.warn(`[UPSTREAM-TIMEOUT] [WARN] Timeout (${ms}ms) tren ket noi Google (${host}) cho [${accName}]`);
        clearAllTimeout();
        safeEndSession();
        const hadActiveRes = Boolean(activeGRes);
        if (activeGRes) {
          const resToKill = activeGRes;
          activeGRes = null;
          destroyStream(resToKill);
        }
        const reqWasDestroyed = gReq.destroyed;
        gReq.destroy(new Error("Upstream connection timeout"));
        // Sau khi da gui header (activeGRes), gReq.on("error") thuong khong ban -> huy clientRes truc tiep
        if (hadActiveRes || clientRes.headersSent || reqWasDestroyed) {
          terminateClient(`Upstream inactivity timeout (${ms}ms)`);
        }
      }, ms);
    }

    sessionAffinity.startRequest(account);
    resetTimeout(TTFB_TIMEOUT_MS);

    const gReq = https.request(outgoingOptions, async (gRes) => {
      try {
        if (isAborted || clientRes.destroyed || clientRes.closed) {
          destroyStream(gRes);
          safeEndSession();
          return;
        }
        activeGRes = gRes;
        resetTimeout(INACTIVITY_TIMEOUT_MS);

        // XU LY 401 UNAUTHORIZED: Ep cap moi token ngay lap tuc
        if (gRes.statusCode === 401 && attempt <= totalAccs * 2) {
          clearAllTimeout();
          const errText = await readErrorBody(gRes);
          console.warn(`[AUTO-FAILOVER-401] [WARN] Tai khoan ${accName} bi HTTP 401: ${errText.slice(0, 150)}. Cap moi Token...`);

          refreshGoogleAccessToken(account, context.config).then((refreshed) => {
            safeEndSession();
            if (isAborted || clientRes.destroyed || clientRes.closed) return;
            const retryAcc = refreshed ? account : context.nextAccount(context.sessionId, true, isSubagent, account);
            if (refreshed) console.log(`[AUTO-FAILOVER-401] [OK] Cap moi token thanh cong cho ${accName}. Thu lai...`);
            else console.warn(`[AUTO-FAILOVER-401] [FAIL] Refresh that bai cho ${accName}. Chuyen tiep...`);
            executeGoogleChatRequest(retryAcc, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context, attempt + 1)
              .catch((err) => terminateClient(err?.message || "Retry failed"));
          }).catch((err) => {
            safeEndSession();
            terminateClient(err?.message || "Token refresh failed");
          });
          return;
        }

        // XU LY 429/403/404: Auto-Failover sang account tiep theo
        if ((gRes.statusCode === 429 || gRes.statusCode === 403 || gRes.statusCode === 404) && attempt <= totalAccs) {
          clearAllTimeout();
          safeEndSession();
          if (account && (gRes.statusCode === 429 || gRes.statusCode === 403)) {
            account.unhealthyUntil = Date.now() + 60 * 1000;
          }
          const errText = await readErrorBody(gRes);
          console.warn(`[AUTO-FAILOVER] [WARN] Tai khoan ${accName} bi HTTP ${gRes.statusCode}: ${errText.slice(0, 200)}!`);

          const nextAcc = context.nextAccount(context.sessionId, true, isSubagent, account);
          context.writeLiveStatus({
            active: true, status: "FAILOVER", error_account: accName, error_code: gRes.statusCode,
            message: `[WARN] ${accName} bi loi ${gRes.statusCode} -> Dang doi sang ${nextAcc?.email}...`,
            timestamp: Date.now(), account_email: nextAcc?.email || accName, account_name: nextAcc?.name || accName,
            current_req: 1, requests_per_account: context.requestsPerAccount, total_requests: context.requestCount,
            endpoint: `${tag} ${(reqUrl || "/").split("?")[0]}`, method: reqMethod
          });

          if (isAborted || clientRes.destroyed || clientRes.closed) return;
          executeGoogleChatRequest(nextAcc, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context, attempt + 1)
            .catch((err) => terminateClient(err?.message || "Failover retry failed"));
          return;
        }

        // AUTH SHIELD: Mask 401 sang 503 de bao ve session IDE
        if (gRes.statusCode === 401) {
          clearAllTimeout();
          safeEndSession();
          console.error(`[AUTH-SHIELD] [PROTECT] Google tra ve 401 tren [${accName}]. Masking sang 503!`);
          if (!clientRes.headersSent && !clientRes.destroyed && !clientRes.closed) {
            clientRes.writeHead(503, { "Content-Type": "application/json", "Retry-After": "5" });
            clientRes.end(create503AuthShieldPayload(503, accName));
          }
          return;
        }

        const isPaused = Boolean(context.rotationPaused);
        context.writeLiveStatus({
          active: false, timestamp: Date.now(), account_email: accName, account_name: account?.name || accName,
          current_req: context.currentAccRequestsServed, requests_per_account: context.requestsPerAccount,
          total_requests: context.requestCount, endpoint: `${tag} ${(reqUrl || "/").split("?")[0]}`,
          method: reqMethod, status: isPaused ? "paused" : "standby", paused: isPaused, statusCode: gRes.statusCode
        });

        let tailBuffer = "";
        let latestMeta = null;

        gRes.on("data", (chunk) => {
          resetTimeout(INACTIVITY_TIMEOUT_MS);
          if (chunk) {
            const textChunk = tailBuffer + chunk.toString("utf8");
            tailBuffer = textChunk.slice(-512);
            const meta = extractUsageMetadata(textChunk);
            if (meta) latestMeta = { ...(latestMeta || {}), ...meta };
          }
        });

        function commitRecordedTokens() {
          if (latestMeta) {
            recordTokens(latestMeta, context?.config?.CONFIG_DIR);
            const sK = formatTokenCount(latestMeta.sent);
            const rK = formatTokenCount(latestMeta.received);
            const cK = formatTokenCount(latestMeta.cached);
            console.log(`[TOKENS] [${accName}] Sent: ${sK} | Recv: ${rK} | Cached: ${cK}`);
            latestMeta = null;
          }
        }

        gRes.on("end", () => { clearAllTimeout(); commitRecordedTokens(); safeEndSession(); activeGRes = null; });
        gRes.on("close", () => {
          clearAllTimeout();
          commitRecordedTokens();
          safeEndSession();
          activeGRes = null;
          if (!gRes.complete && !isAborted) terminateClient("Upstream stream closed prematurely");
        });
        gRes.on("error", (err) => {
          clearAllTimeout();
          console.error(`[STREAM-ERR] Loi stream tu Google (${accName}):`, err.message);
          safeEndSession();
          destroyStream(gRes);
          activeGRes = null;
          if (!clientRes.destroyed && !clientRes.closed) clientRes.destroy(err);
        });

        clientRes.on("error", (err) => {
          console.warn(`[CLIENT-STREAM-ERR] Client stream error tren [${accName}]:`, err.message);
          safeEndSession();
          destroyStream(gRes);
          activeGRes = null;
        });

        if (!clientRes.headersSent && !clientRes.destroyed && !clientRes.closed) {
          clientRes.writeHead(gRes.statusCode, gRes.headers);
          gRes.pipe(clientRes);
        }
      } catch (err) {
        safeEndSession();
        terminateClient(err?.message || "Unexpected response handler error");
      }
    });

    detachClientClose = attachClientCloseHandler({
      clientRes, gReq, getActiveGRes: () => activeGRes,
      safeEndSession: () => { clearAllTimeout(); safeEndSession(); },
      onAbort: () => { isAborted = true; clearAllTimeout(); }, accName
    });

    gReq.on("error", (e) => {
      clearAllTimeout();
      safeEndSession();
      if (activeGRes) destroyStream(activeGRes);

      if (isAborted) {
        console.log(`[CLIENT-CLOSED] Socket upstream bi huy do IDE da ngat ket noi truoc [${accName}]: ${e.message}`);
        return;
      }

      console.error(`[UPSTREAM-ERR] Loi ket noi Google (${host}) tren [${accName}]:`, e.message);

      if (account) account.unhealthyUntil = Date.now() + 60 * 1000;

      if (attempt <= totalAccs && !clientRes.headersSent && !clientRes.destroyed && !clientRes.closed) {
        const nextAcc = context.nextAccount(context.sessionId, true, isSubagent, account);
        console.warn(`[AUTO-FAILOVER-NET] [WARN] Loi socket (${e.message}). Doi sang ${nextAcc?.email}...`);
        executeGoogleChatRequest(nextAcc, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context, attempt + 1)
          .catch((err) => terminateClient(err?.message || "Failover network retry failed"));
        return;
      }

      terminateClient(e.message || "Stream aborted prematurely by upstream");
    });

    if (finalBodyBuffer && finalBodyBuffer.length > 0) gReq.write(finalBodyBuffer);
    gReq.end();
  } catch (err) {
    terminateClient(err?.message || "Internal proxy error");
  }
}

module.exports = {
  isAiChatEndpoint,
  rewriteChatPayload,
  executeGoogleChatRequest
};
