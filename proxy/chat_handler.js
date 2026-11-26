const https = require("node:https");
const { ensureValidToken, refreshGoogleAccessToken } = require("./token_manager");
const { agentPool, getAgentForAccount } = require("./agent_pool");
const { sessionAffinity } = require("./session_affinity");
const { destroyStream, attachClientCloseHandler, isSocketResetError } = require("./socket_cleanup");
const { extractUsageMetadata, recordTokens, formatTokenCount } = require("./token_tracker");
const {
  isAiChatEndpoint, rewriteChatPayload, readErrorBody, computeTtfbTimeoutMs,
  hasFailoverBudget, buildForwardHeaders, create503AuthShieldPayload
} = require("./chat_payload_helper");
const INACTIVITY_TIMEOUT_MS = 120000; // 120s sliding window cho thinking model context lon

// Gui Chat Request voi Dedicated Agent, Dynamic Rewrite, Auto-Failover va Auth Shield
async function executeGoogleChatRequest(
  account, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context,
  attempt = 1, requestStartedAt = Date.now(), isFreshRetry = false
) {
  const totalAccs = context.maxFailoverAttempts || context.accounts.length || 1;
  const accName = account ? account.email : "UNKNOWN";
  const rawHost = origHeaders["host"] || "daily-cloudcode-pa.googleapis.com";
  const host = rawHost.split(":")[0];

  function send503AuthShield() {
    if (!clientRes.headersSent && !clientRes.destroyed && !clientRes.closed) {
      clientRes.writeHead(503, { "Content-Type": "application/json", "Retry-After": "5" });
      clientRes.end(create503AuthShieldPayload(503, accName));
    }
  }

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
    const fwdHeaders = buildForwardHeaders(origHeaders, host, account, finalBodyBuffer);
    const ttfbTimeoutMs = computeTtfbTimeoutMs(attempt, requestStartedAt);
    const attemptStartedAt = Date.now();
    const outgoingOptions = {
      hostname: host, port: 443, path: reqUrl, method: reqMethod,
      headers: fwdHeaders, agent: getAgentForAccount(account)
    };
    let activeGRes = null;
    let isAborted = false;
    let sessionEnded = false;
    let timeoutTimer = null, timeoutMs = 0;
    let detachClientClose = () => {};

    function clearAllTimeout() { if (timeoutTimer) { clearTimeout(timeoutTimer); timeoutTimer = null; } timeoutMs = 0; }
    function safeEndSession() {
      clearAllTimeout();
      detachClientClose();
      if (!sessionEnded) { sessionEnded = true; sessionAffinity.endRequest(); }
    }
    function resetTimeout(ms) {
      if (timeoutTimer && timeoutMs === ms && typeof timeoutTimer.refresh === "function") { timeoutTimer.refresh(); return; }
      clearAllTimeout();
      timeoutMs = ms;
      timeoutTimer = setTimeout(() => {
        const totalElapsed = Date.now() - requestStartedAt;
        console.warn(`[UPSTREAM-TIMEOUT] [WARN] Timeout (${ms}ms, total=${totalElapsed}ms, attempt=#${attempt}) tren Google (${host}) cho [${accName}]`);
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
        if (hadActiveRes || clientRes.headersSent || reqWasDestroyed) {
          terminateClient(`Upstream inactivity timeout (${ms}ms)`);
        }
      }, ms);
    }

    sessionAffinity.startRequest(account);
    resetTimeout(ttfbTimeoutMs);

    const gReq = https.request(outgoingOptions, async (gRes) => {
      try {
        if (isAborted || clientRes.destroyed || clientRes.closed) {
          destroyStream(gRes);
          safeEndSession();
          return;
        }
        activeGRes = gRes;
        const ttfbMs = Date.now() - attemptStartedAt;
        if (ttfbMs >= 10000) {
          console.log(`[SLOW-TTFB] [${accName}] Nhan header HTTP ${gRes.statusCode} sau ${ttfbMs}ms (attempt #${attempt})`);
        }
        resetTimeout(INACTIVITY_TIMEOUT_MS);

        // XU LY 401 UNAUTHORIZED: Ep cap moi token ngay lap tuc
        const max401Attempts = context.isAccountLocked ? 1 : totalAccs * 2;
        if (gRes.statusCode === 401 && attempt <= max401Attempts) {
          clearAllTimeout();
          const errText = await readErrorBody(gRes);
          console.warn(`[AUTO-FAILOVER-401] [WARN] Tai khoan ${accName} bi HTTP 401: ${errText.slice(0, 150)}. Cap moi Token...`);

          refreshGoogleAccessToken(account, context.config).then((refreshed) => {
            safeEndSession();
            if (isAborted || clientRes.destroyed || clientRes.closed) return;
            if (!refreshed && context.isAccountLocked) { send503AuthShield(); return; }
            const retryAcc = refreshed ? account : context.nextAccount(context.sessionId, true, isSubagent, account);
            if (!retryAcc) { send503AuthShield(); return; }
            if (refreshed) console.log(`[AUTO-FAILOVER-401] [OK] Cap moi token thanh cong cho ${accName}. Thu lai...`);
            else console.warn(`[AUTO-FAILOVER-401] [FAIL] Refresh that bai cho ${accName}. Chuyen tiep...`);
            executeGoogleChatRequest(retryAcc, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context, attempt + 1, requestStartedAt)
              .catch((err) => terminateClient(err?.message || "Retry failed"));
          }).catch((err) => {
            safeEndSession();
            terminateClient(err?.message || "Token refresh failed");
          });
          return;
        }

        // XU LY 429/403/404: Auto-Failover sang account tiep theo (bo qua neu tai khoan dang bi khoa co dinh)
        if ((gRes.statusCode === 429 || gRes.statusCode === 403 || gRes.statusCode === 404) && !context.isAccountLocked && attempt <= totalAccs) {
          clearAllTimeout();
          safeEndSession();
          if (account && (gRes.statusCode === 429 || gRes.statusCode === 403)) {
            account.unhealthyUntil = Date.now() + 60 * 1000;
          }
          const errText = await readErrorBody(gRes);
          console.warn(`[AUTO-FAILOVER] [WARN] Tai khoan ${accName} bi HTTP ${gRes.statusCode}: ${errText.slice(0, 200)}!`);

          const nextAcc = context.nextAccount(context.sessionId, true, isSubagent, account);
          if (!nextAcc) {
            if (!clientRes.headersSent && !clientRes.destroyed && !clientRes.closed) {
              clientRes.writeHead(gRes.statusCode, { "Content-Type": gRes.headers["content-type"] || "application/json" });
              clientRes.end(errText);
            }
            return;
          }
          context.writeLiveStatus({
            active: true, status: "FAILOVER", error_account: accName, error_code: gRes.statusCode,
            message: `[WARN] ${accName} bi loi ${gRes.statusCode} -> Dang doi sang ${nextAcc?.email}...`,
            timestamp: Date.now(), account_email: nextAcc?.email || accName, account_name: nextAcc?.name || accName,
            current_req: 1, requests_per_account: context.requestsPerAccount, total_requests: context.requestCount,
            endpoint: `${tag} ${(reqUrl || "/").split("?")[0]}`, method: reqMethod
          });

          if (isAborted || clientRes.destroyed || clientRes.closed) return;
          executeGoogleChatRequest(nextAcc, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context, attempt + 1, requestStartedAt)
            .catch((err) => terminateClient(err?.message || "Failover retry failed"));
          return;
        }

        // AUTH SHIELD: Mask 401 sang 503 de bao ve session IDE
        if (gRes.statusCode === 401) {
          clearAllTimeout();
          safeEndSession();
          console.error(`[AUTH-SHIELD] [PROTECT] Google tra ve 401 tren [${accName}]. Masking sang 503!`);
          send503AuthShield();
          return;
        }

        if (context.buildLiveStatus) {
          context.writeLiveStatus(context.buildLiveStatus({
            account, account_email: accName, account_name: account?.name || accName,
            endpoint: `${tag} ${(reqUrl || "/").split("?")[0]}`, method: reqMethod,
            statusCode: gRes.statusCode, model_routed: context.modelRouted || ""
          }));
        }

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
          if (!latestMeta) return;
          recordTokens(latestMeta, context?.config?.CONFIG_DIR);
          console.log(`[TOKENS] [${accName}] Sent: ${formatTokenCount(latestMeta.sent)} | Recv: ${formatTokenCount(latestMeta.received)} | Cached: ${formatTokenCount(latestMeta.cached)}`);
          latestMeta = null;
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
          if (!clientRes.destroyed && !clientRes.closed) clientRes.destroy();
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
      onAbort: () => {
        isAborted = true;
        clearAllTimeout();
        if (!clientRes.headersSent) {
          agentPool.destroyAgentForAccount(account);
          if (!context.isAccountLocked && (attempt > 1 || (Date.now() - attemptStartedAt) >= 15000)) {
            context.nextAccount(context.sessionId, true, isSubagent, account);
          }
        }
      },
      accName
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
      agentPool.destroyAgentForAccount(account);

      if (!isFreshRetry && isSocketResetError(e) && !clientRes.headersSent && !clientRes.destroyed && !clientRes.closed && hasFailoverBudget(requestStartedAt, bodyBuffer)) {
        console.warn(`[FRESH-SOCKET-RETRY] [WARN] Socket bi ngat ngam (${e.message}) tren [${accName}]. Thu lai tren ket noi moi...`);
        executeGoogleChatRequest(account, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context, attempt, requestStartedAt, true)
          .catch((err) => terminateClient(err?.message || "Fresh socket retry failed"));
        return;
      }

      const nextAcc = (!context.isAccountLocked && attempt <= totalAccs && hasFailoverBudget(requestStartedAt, bodyBuffer) && !clientRes.headersSent && !clientRes.destroyed && !clientRes.closed)
        ? context.nextAccount(context.sessionId, true, isSubagent, account) : null;
      if (nextAcc) {
        console.warn(`[AUTO-FAILOVER-NET] [WARN] Loi socket (${e.message}). Doi sang ${nextAcc?.email}...`);
        executeGoogleChatRequest(nextAcc, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context, attempt + 1, requestStartedAt, false)
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
