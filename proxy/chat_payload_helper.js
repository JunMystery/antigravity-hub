/**
 * Chat Payload & Endpoint Helper for Antigravity Proxy.
 * Extracts model information, rewrites request payloads, and handles error response parsing.
 */

function isAiChatEndpoint(url) {
  if (!url) return false;
  return (
    url.includes(":generateContent") ||
    url.includes(":streamGenerateContent") ||
    url.includes(":generateChat") ||
    url.includes(":streamGenerateChat") ||
    url.includes(":generateCode") ||
    url.includes(":streamGenerateCode") ||
    url.includes(":completeCode") ||
    url.includes(":streamCompleteCode") ||
    url.includes(":suggestCode") ||
    url.includes(":streamSuggestCode") ||
    url.includes(":inlineCode") ||
    url.includes(":streamInlineCode") ||
    url.includes(":predict") ||
    url.includes(":streamPredict") ||
    url.includes("/models/")
  );
}

function isStreamingEndpoint(urlPath) {
  if (!urlPath) return false;
  return urlPath.toLowerCase().includes("stream") || isAiChatEndpoint(urlPath);
}

function extractModelName(urlPath, body) {
  let json = null;
  if (body) {
    if (Buffer.isBuffer(body)) {
      try {
        json = JSON.parse(body.toString("utf8"));
      } catch (_) {}
    } else if (typeof body === "object") {
      json = body;
    }
  }

  if (json) {
    if (json.model && typeof json.model === "string") {
      return json.model.replace(/^models\//, "").split(":")[0];
    }
    if (json.metadata && typeof json.metadata === "object") {
      if (typeof json.metadata.model === "string") {
        return json.metadata.model.replace(/^models\//, "").split(":")[0];
      }
      if (typeof json.metadata.modelName === "string") {
        return json.metadata.modelName.replace(/^models\//, "").split(":")[0];
      }
    }
    if (Array.isArray(json.requests) && json.requests[0] && json.requests[0].model) {
      return String(json.requests[0].model).replace(/^models\//, "").split(":")[0];
    }
    if (json.request && json.request.model) {
      return String(json.request.model).replace(/^models\//, "").split(":")[0];
    }
  }

  if (urlPath) {
    const match = urlPath.match(/models\/([^/:]+)/);
    if (match) return match[1];
  }

  return "";
}

function rewriteChatPayload(bodyBuffer, account, host = "") {
  if (!bodyBuffer || bodyBuffer.length === 0) return bodyBuffer;
  try {
    const rawStr = bodyBuffer.toString("utf8");
    const json = JSON.parse(rawStr);
    let modified = false;

    const isCloudCode = !host || host.includes("cloudcode");
    if (isCloudCode) {
      if (!json.project && account?.projectId) {
        json.project = account.projectId;
        modified = true;
      } else if (!json.project) {
        json.project = "aicode-consumers";
        modified = true;
      }

      if (json.metadata && typeof json.metadata === "object" && !Array.isArray(json.metadata)) {
        if (!json.metadata.ideVersion) {
          json.metadata.ideVersion = "2.24.0";
          modified = true;
        }
      }
    }

    return modified ? Buffer.from(JSON.stringify(json), "utf8") : bodyBuffer;
  } catch (_) {
    return bodyBuffer;
  }
}

function readErrorBody(res, timeoutMs = 5000) {
  return new Promise((resolve) => {
    if (!res || res.destroyed || res.readableEnded) return resolve("");
    let settled = false;
    const chunks = [];
    const finish = (val) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(val);
    };
    const safeConcat = () => {
      try { return Buffer.concat(chunks).toString("utf8"); } catch { return ""; }
    };
    const timer = setTimeout(() => {
      try { res.destroy(); } catch (_) {}
      finish(safeConcat());
    }, timeoutMs);
    if (typeof timer.unref === "function") timer.unref();
    res.on("data", (chunk) => chunks.push(chunk));
    res.on("end", () => finish(safeConcat()));
    res.on("close", () => finish(safeConcat()));
    res.on("error", () => finish(""));
  });
}

const CLIENT_BUDGET_MS = 58000;
const MIN_FAILOVER_BUDGET_MS = 12000;
const LARGE_PROMPT_BYTE_THRESHOLD = 30000;
const MIN_LARGE_FAILOVER_BUDGET_MS = 25000;
const HOP_BY_HOP_HEADERS = [
  "connection", "proxy-connection", "keep-alive",
  "transfer-encoding", "Transfer-Encoding", "expect"
];

function computeTtfbTimeoutMs(attempt = 1, requestStartedAt = Date.now(), now = Date.now()) {
  const elapsed = Math.max(0, now - requestStartedAt);
  const remaining = Math.max(5000, CLIENT_BUDGET_MS - elapsed);
  if (attempt <= 1) return Math.min(45000, remaining);
  return Math.min(45000, remaining);
}

function hasFailoverBudget(requestStartedAt = Date.now(), bodyBuffer = null, now = Date.now()) {
  const remaining = CLIENT_BUDGET_MS - Math.max(0, now - requestStartedAt);
  if (bodyBuffer && bodyBuffer.length > LARGE_PROMPT_BYTE_THRESHOLD) {
    return remaining >= MIN_LARGE_FAILOVER_BUDGET_MS;
  }
  return remaining >= MIN_FAILOVER_BUDGET_MS;
}

function buildForwardHeaders(origHeaders = {}, host = "", account = null, finalBodyBuffer = null) {
  const userAgent = origHeaders["user-agent"] || (
    process.platform === "win32" ? "antigravity/2.24.0 win32/x64" : "antigravity/2.24.0 linux/x64"
  );
  const fwdHeaders = { ...origHeaders, "user-agent": userAgent };
  for (const h of HOP_BY_HOP_HEADERS) delete fwdHeaders[h];
  delete fwdHeaders["host"];
  fwdHeaders["host"] = host;
  if (!fwdHeaders["x-client-name"]) fwdHeaders["x-client-name"] = "antigravity";
  if (!fwdHeaders["x-client-version"]) fwdHeaders["x-client-version"] = "2.24.0";
  if (account && account.accessToken) {
    fwdHeaders["authorization"] = `Bearer ${account.accessToken}`;
  }
  if (finalBodyBuffer && finalBodyBuffer.length > 0) {
    fwdHeaders["content-length"] = finalBodyBuffer.length;
  }
  return fwdHeaders;
}

function create503AuthShieldPayload(originalStatus = 401, accountName = "") {
  return JSON.stringify({
    error: {
      code: 503,
      message: "Antigravity Proxy: Tat ca token dang duoc lam moi. Session an toan. Vui long thu lai."
    }
  });
}

module.exports = {
  CLIENT_BUDGET_MS,
  MIN_FAILOVER_BUDGET_MS,
  LARGE_PROMPT_BYTE_THRESHOLD,
  MIN_LARGE_FAILOVER_BUDGET_MS,
  isAiChatEndpoint,
  isStreamingEndpoint,
  extractModelName,
  rewriteChatPayload,
  rewriteRequestBody: rewriteChatPayload,
  readErrorBody,
  computeTtfbTimeoutMs,
  hasFailoverBudget,
  buildForwardHeaders,
  create503AuthShieldPayload
};
