const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");

function getConfigDir() {
  if (process.platform === "win32" && process.env.APPDATA) {
    return path.join(process.env.APPDATA, "antigravity-launcher");
  }
  return path.join(os.homedir(), ".config", "antigravity-launcher");
}

function getTokenMetricsPath(customConfigDir = null) {
  const dir = customConfigDir || getConfigDir();
  return path.join(dir, "token_metrics.json");
}

function extractUsageMetadata(text) {
  if (!text || typeof text !== "string") return null;
  if (!text.includes("usageMetadata") && !text.includes("promptTokenCount") && !text.includes("prompt_token_count") && !text.includes("input_tokens")) return null;

  const sentMatch = text.match(/"prompt(?:TokenCount|_token_count)"\s*:\s*(\d+)/) ||
                    text.match(/"input_tokens"\s*:\s*(\d+)/);
  const recvMatch = text.match(/"candidates(?:TokenCount|_token_count)"\s*:\s*(\d+)/) ||
                    text.match(/"output_tokens"\s*:\s*(\d+)/);
  const cachedMatch = text.match(/"cached(?:ContentTokenCount|_content_token_count)"\s*:\s*(\d+)/) ||
                      text.match(/"cache_read_input_tokens"\s*:\s*(\d+)/);
  const totalMatch = text.match(/"total(?:TokenCount|_token_count)"\s*:\s*(\d+)/);

  if (!sentMatch && !recvMatch && !totalMatch) return null;

  const sent = sentMatch ? parseInt(sentMatch[1], 10) : 0;
  const received = recvMatch ? parseInt(recvMatch[1], 10) : 0;
  const cached = cachedMatch ? parseInt(cachedMatch[1], 10) : 0;
  const total = totalMatch ? parseInt(totalMatch[1], 10) : (sent + received);

  return { sent, received, cached, total };
}

function loadTokenMetrics(filePath) {
  try {
    if (fs.existsSync(filePath)) {
      const raw = fs.readFileSync(filePath, "utf8");
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        if (!parsed.lifetime) parsed.lifetime = { sent: 0, received: 0, cached: 0, total: 0, requests: 0 };
        if (!parsed.hourly) parsed.hourly = {};
        return parsed;
      }
    }
  } catch (_) {}
  return {
    lifetime: { sent: 0, received: 0, cached: 0, total: 0, requests: 0 },
    hourly: {}
  };
}

function recordTokens(metrics, customConfigDir = null) {
  if (!metrics || typeof metrics !== "object") return;
  const filePath = getTokenMetricsPath(customConfigDir);
  const dir = path.dirname(filePath);

  try {
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const data = loadTokenMetrics(filePath);

    data.lifetime.sent = (data.lifetime.sent || 0) + (metrics.sent || 0);
    data.lifetime.received = (data.lifetime.received || 0) + (metrics.received || 0);
    data.lifetime.cached = (data.lifetime.cached || 0) + (metrics.cached || 0);
    data.lifetime.total = (data.lifetime.total || 0) + (metrics.total || 0);
    data.lifetime.requests = (data.lifetime.requests || 0) + 1;

    const bucketKey = new Date().toISOString().slice(0, 13) + ":00:00Z";
    const bucket = data.hourly[bucketKey] || { s: 0, r: 0, c: 0, t: 0, n: 0 };
    bucket.s += metrics.sent || 0;
    bucket.r += metrics.received || 0;
    bucket.c += metrics.cached || 0;
    bucket.t += metrics.total || 0;
    bucket.n += 1;
    data.hourly[bucketKey] = bucket;

    // Prune buckets older than 31 days
    const cutoffMs = Date.now() - 31 * 86400 * 1000;
    for (const key of Object.keys(data.hourly)) {
      try {
        const t = new Date(key).getTime();
        if (!isNaN(t) && t < cutoffMs) {
          delete data.hourly[key];
        }
      } catch (_) {}
    }

    const tmpFile = `${filePath}.${process.pid}.tmp`;
    fs.writeFileSync(tmpFile, JSON.stringify(data, null, 2), "utf8");
    fs.renameSync(tmpFile, filePath);
  } catch (err) {
    console.error(`[TOKEN-TRACKER-ERR] Không thể ghi token_metrics.json: ${err.message}`);
  }
}

function formatTokenCount(count) {
  if (!count || count <= 0) return "0";
  // Định dạng số nguyên có dấu phẩy phân cách nghìn, triệu, tỉ (000,000)
  return Math.round(count).toLocaleString("en-US");
}

module.exports = {
  getConfigDir,
  getTokenMetricsPath,
  extractUsageMetadata,
  loadTokenMetrics,
  recordTokens,
  formatTokenCount
};
