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

function create503AuthShieldPayload(originalStatus = 401, accountName = "") {
  return JSON.stringify({
    error: {
      code: 503,
      message: "Antigravity Proxy: Tat ca token dang duoc lam moi. Session an toan. Vui long thu lai."
    }
  });
}

module.exports = {
  isAiChatEndpoint,
  isStreamingEndpoint,
  extractModelName,
  rewriteChatPayload,
  rewriteRequestBody: rewriteChatPayload,
  readErrorBody,
  create503AuthShieldPayload
};
