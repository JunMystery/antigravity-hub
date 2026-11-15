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
    url.includes(":predict") ||
    url.includes(":streamPredict") ||
    url.includes("/models/")
  );
}

function isStreamingEndpoint(urlPath) {
  if (!urlPath) return false;
  return urlPath.toLowerCase().includes("stream") || isAiChatEndpoint(urlPath);
}

function extractModelName(urlPath, parsedBody) {
  if (parsedBody && parsedBody.model) return String(parsedBody.model);
  if (!urlPath) return "unknown";
  const match = urlPath.match(/models\/([^/:]+)/);
  return match ? match[1] : "gemini-pro";
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
