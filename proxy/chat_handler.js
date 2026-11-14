const https = require("node:https");
const { ensureValidToken, refreshGoogleAccessToken } = require("./token_manager");
const { getAgentForAccount } = require("./agent_pool");

/**
 * Kiem tra xem endpoint co phai la AI Chat / Code Generation khong
 */
function isAiChatEndpoint(url) {
  if (!url) return false;
  return (
    url.includes(":generateContent") ||
    url.includes(":streamGenerateContent") ||
    url.includes(":generateChat") ||
    url.includes(":streamGenerateChat")
  );
}

/**
 * Dynamic Payload & Project ID Rewrite:
 * 1. Rewrite truong 'project' theo account.projectId (fallback 'aicode-consumers').
 * 2. Chuan hoa metadata.ideVersion = '2.24.0' chuan Antigravity.
 * 3. Tra ve Buffer moi da duoc serialize lai.
 */
function rewriteChatPayload(bodyBuffer, account) {
  if (!bodyBuffer || bodyBuffer.length === 0) return bodyBuffer;
  try {
    const rawStr = bodyBuffer.toString("utf8");
    const json = JSON.parse(rawStr);
    let modified = false;

    // Gan dung Project ID cua tai khoan dang active
    const targetProject = account?.projectId || "aicode-consumers";
    if (json.project !== targetProject) {
      json.project = targetProject;
      modified = true;
    }

    // Chuan hoa metadata.ideVersion tuong thich Google CloudCode
    if (json.metadata && typeof json.metadata === "object") {
      json.metadata.ideVersion = "2.24.0";
      modified = true;
    }

    return modified ? Buffer.from(JSON.stringify(json), "utf8") : bodyBuffer;
  } catch (_) {
    return bodyBuffer;
  }
}

/**
 * Doc toan bo noi dung response loi tu Google (phuc vu diagnostic logging)
 */
function readErrorBody(res) {
  return new Promise((resolve) => {
    const chunks = [];
    res.on("data", (chunk) => chunks.push(chunk));
    res.on("end", () => {
      try {
        resolve(Buffer.concat(chunks).toString("utf8"));
      } catch {
        resolve("");
      }
    });
    res.on("error", () => resolve(""));
  });
}

/**
 * Gui Chat Request len Google Cloud Code voi co che:
 * 1. Dedicated Per-Account HTTPS Agent: Co lap 100% socket giua cac tai khoan.
 * 2. Dynamic Payload & Project ID Rewrite theo tung tai khoan.
 * 3. Cap moi Token chu dong truoc khi gui neu token het han / sap het han.
 * 4. Tu dong ep cap lai token ngay khi bi HTTP 401 Unauthorized tu Google.
 * 5. Tu dong chuyen tai khoan ke tiep (Auto-Failover) khi bi 429, 403 hoac 404.
 * 6. Stream-aware Inactivity Timeout & Force End: Chong treo/nuot request tuyet doi.
 */
async function executeGoogleChatRequest(account, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context, attempt = 1) {
  const totalAccs = context.accounts.length || 1;
  const accName = account ? account.email : "UNKNOWN";
  const rawHost = origHeaders["host"] || "daily-cloudcode-pa.googleapis.com";
  const host = rawHost.split(":")[0];

  if (clientRes.destroyed || clientRes.closed) {
    console.log(`[CLIENT-CLOSED] Ket noi IDE da dong truoc khi gui request cho [${accName}]`);
    return;
  }

  // 1. Dam bao Token con han su dung truoc khi gui di
  if (account) {
    await ensureValidToken(account, context.config);
  }

  if (clientRes.destroyed || clientRes.closed) return;

  // 2. Dynamic Payload Rewrite theo tai khoan dang gui
  const finalBodyBuffer = rewriteChatPayload(bodyBuffer, account);

  const fwdHeaders = { ...origHeaders };
  delete fwdHeaders["host"];
  fwdHeaders["host"] = host;

  // Chuan hoa User-Agent tuong thich Antigravity
  fwdHeaders["user-agent"] = "antigravity/2.24.0 linux/x64";

  if (account && account.accessToken) {
    fwdHeaders["authorization"] = `Bearer ${account.accessToken}`;
  }

  if (finalBodyBuffer && finalBodyBuffer.length > 0) {
    fwdHeaders["content-length"] = finalBodyBuffer.length;
  }

  // Su dung Agent doc lap cho tai khoan nay
  const accountAgent = getAgentForAccount(account);

  const outgoingOptions = {
    hostname: host,
    port: 443,
    path: reqUrl,
    method: reqMethod,
    headers: fwdHeaders,
    agent: accountAgent,
    timeout: 35000
  };

  let gResFinished = false;

  const gReq = https.request(outgoingOptions, async (gRes) => {
    // XU LY 401 UNAUTHORIZED: Ep cap moi token ngay lap tuc
    if (gRes.statusCode === 401 && attempt <= totalAccs * 2) {
      const errText = await readErrorBody(gRes);
      console.warn(`[AUTO-FAILOVER-401] [WARN] Tai khoan ${accName} bi HTTP 401: ${errText.slice(0, 150)}. Dang cap moi Token...`);

      refreshGoogleAccessToken(account, context.config).then((refreshed) => {
        if (clientRes.destroyed || clientRes.closed) return;
        if (refreshed) {
          console.log(`[AUTO-FAILOVER-401] [OK] Cap moi token thanh cong cho ${accName}. Thu lai request...`);
          executeGoogleChatRequest(account, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context, attempt + 1);
        } else {
          console.warn(`[AUTO-FAILOVER-401] [FAIL] Refresh token that bai cho ${accName}. Chuyen sang tai khoan ke tiep...`);
          context.nextAccount();
          const nextAcc = context.getCurrentAccount();
          executeGoogleChatRequest(nextAcc, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context, attempt + 1);
        }
      });
      return;
    }

    // XU LY 429 (QUOTA) HOAC 403 (FORBIDDEN) HOAC 404 (PROJECT NOT FOUND): Auto-Failover
    if ((gRes.statusCode === 429 || gRes.statusCode === 403 || gRes.statusCode === 404) && attempt <= totalAccs) {
      const errText = await readErrorBody(gRes);
      console.warn(`[AUTO-FAILOVER] [WARN] Tai khoan ${accName} bi HTTP ${gRes.statusCode}: ${errText.slice(0, 200)}! Dang doi tai khoan tiep theo...`);

      context.nextAccount();
      const nextAcc = context.getCurrentAccount();

      context.writeLiveStatus({
        active: true,
        status: "FAILOVER",
        error_account: accName,
        error_code: gRes.statusCode,
        message: `[WARN] ${accName} bi loi ${gRes.statusCode} -> Dang tu dong doi sang ${nextAcc?.email}...`,
        timestamp: Date.now(),
        account_email: nextAcc?.email || accName,
        account_name: nextAcc?.name || accName,
        current_req: 1,
        requests_per_account: context.requestsPerAccount,
        total_requests: context.requestCount,
        endpoint: (reqUrl || "/").split("?")[0],
        method: reqMethod
      });

      if (clientRes.destroyed || clientRes.closed) return;
      executeGoogleChatRequest(nextAcc, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context, attempt + 1);
      return;
    }

    // Phan hoi thanh cong hoac loi khong nam trong dien failover
    context.writeLiveStatus({
      active: false,
      timestamp: Date.now(),
      account_email: accName,
      account_name: account?.name || accName,
      current_req: context.currentAccRequestsServed,
      requests_per_account: context.requestsPerAccount,
      total_requests: context.requestCount,
      endpoint: (reqUrl || "/").split("?")[0],
      method: reqMethod,
      status: gRes.statusCode === 200 ? "success" : `http_${gRes.statusCode}`,
      statusCode: gRes.statusCode
    });

    // Bat su kien ket thuc stream that su de giai phong co gResFinished
    gRes.on("end", () => {
      gResFinished = true;
    });

    gRes.on("close", () => {
      gResFinished = true;
    });

    // Bat loi stream truc tiep tu phia Google upstream
    gRes.on("error", (err) => {
      console.error(`[STREAM-ERR] Loi stream tu Google (${accName}):`, err.message);
      gResFinished = true;
      if (!clientRes.writableEnded) {
        clientRes.end();
      }
    });

    clientRes.writeHead(gRes.statusCode, gRes.headers);
    gRes.pipe(clientRes);
  });

  // Client Abort / Socket Cleanup: giai phong socket upstream neu client IDE dong ket noi
  clientRes.on("close", () => {
    if (!gResFinished && !gReq.destroyed) {
      console.log(`[CLIENT-ABORT] Client IDE da dong ket noi som. Huy socket upstream cho [${accName}]`);
      gReq.destroy();
    }
  });

  gReq.on("timeout", () => {
    console.warn(`[UPSTREAM-TIMEOUT] [WARN] Het thoi gian cho ket noi Google (${host}) sau 35s cho [${accName}]`);
    gReq.destroy(new Error("Upstream connection timeout"));
  });

  gReq.on("error", (e) => {
    console.error(`[UPSTREAM-ERR] Loi ket noi Google (${host}) tren [${accName}]:`, e.message);
    gResFinished = true;

    if (attempt <= totalAccs && !clientRes.headersSent && !clientRes.destroyed && !clientRes.closed) {
      context.nextAccount();
      const nextAcc = context.getCurrentAccount();
      console.warn(`[AUTO-FAILOVER-NET] [WARN] Loi socket (${e.message}). Doi sang ${nextAcc?.email}...`);
      executeGoogleChatRequest(nextAcc, bodyBuffer, reqUrl, reqMethod, origHeaders, clientRes, context, attempt + 1);
      return;
    }

    if (!clientRes.headersSent) {
      clientRes.writeHead(502, { "Content-Type": "application/json" });
      clientRes.end(JSON.stringify({ error: "Bad Gateway", message: e.message }));
    } else if (!clientRes.writableEnded) {
      // Headers da gui ma gap loi socket upstream -> Ket thuc clientRes ngay de tranh treo IDE vinh vien!
      console.warn(`[FORCE-END] Dong clientRes.end() sau loi socket upstream de tranh treo IDE`);
      clientRes.end();
    }
  });

  if (finalBodyBuffer && finalBodyBuffer.length > 0) {
    gReq.write(finalBodyBuffer);
  }
  gReq.end();
}

module.exports = {
  isAiChatEndpoint,
  rewriteChatPayload,
  executeGoogleChatRequest
};
