/**
 * Rotator state persistence helper for Antigravity Proxy.
 * Handles atomic file writes, crash-resilient JSON state loading, and account resolution.
 */

const fs = require("node:fs");
const path = require("node:path");

function saveRotatorState(stateFilePath, stateData) {
  if (!stateFilePath || !stateData) return false;
  const dir = path.dirname(stateFilePath);
  if (!fs.existsSync(dir)) {
    try {
      fs.mkdirSync(dir, { recursive: true });
    } catch (_) {}
  }
  const tmpPath = `${stateFilePath}.tmp`;
  const payload = JSON.stringify(stateData, null, 2);
  try {
    fs.writeFileSync(tmpPath, payload, "utf8");
    try {
      fs.renameSync(tmpPath, stateFilePath);
      return true;
    } catch (_) {
      fs.writeFileSync(stateFilePath, payload, "utf8");
      try { fs.unlinkSync(tmpPath); } catch (_) {}
      return true;
    }
  } catch (err) {
    console.error("[ROTATOR-SAVE-ERR] Loi ghi rotator_state.json:", err.message);
    return false;
  }
}

async function saveRotatorStateAsync(stateFilePath, stateData) {
  if (!stateFilePath || !stateData) return false;
  const dir = path.dirname(stateFilePath);
  try {
    await fs.promises.mkdir(dir, { recursive: true });
  } catch (_) {}
  const tmpPath = `${stateFilePath}.tmp`;
  const payload = JSON.stringify(stateData, null, 2);
  try {
    await fs.promises.writeFile(tmpPath, payload, "utf8");
    try {
      await fs.promises.rename(tmpPath, stateFilePath);
      return true;
    } catch (_) {
      await fs.promises.writeFile(stateFilePath, payload, "utf8");
      try { await fs.promises.unlink(tmpPath); } catch (_) {}
      return true;
    }
  } catch (err) {
    console.error("[ROTATOR-SAVE-ERR] Loi ghi async rotator_state.json:", err.message);
    return false;
  }
}

function restoreRotatorState(stateFilePath) {
  if (!stateFilePath || !fs.existsSync(stateFilePath)) return null;
  try {
    const raw = fs.readFileSync(stateFilePath, "utf8");
    if (!raw || !raw.trim()) return null;
    return JSON.parse(raw);
  } catch (err) {
    console.error("[ROTATOR-RESTORE-ERR] Loi doc rotator_state.json:", err.message);
    return null;
  }
}

function cleanOrphanedState(stateFilePath) {
  if (!stateFilePath) return;
  const tmpPath = `${stateFilePath}.tmp`;
  try {
    if (fs.existsSync(tmpPath)) {
      const stat = fs.statSync(tmpPath);
      if (Date.now() - stat.mtimeMs > 60000) {
        fs.unlinkSync(tmpPath);
      }
    }
  } catch (_) {}
}

function resolveRestoredAccount(accounts, savedState) {
  if (!Array.isArray(accounts) || accounts.length === 0 || !savedState) {
    return { accountIndex: 0, currentAccRequestsServed: 0, matched: false };
  }
  const targetEmail = (savedState.last_account_email || "").toLowerCase();
  const targetId = savedState.last_account_id;

  let foundIdx = -1;
  if (targetId || targetEmail) {
    foundIdx = accounts.findIndex((a) => {
      const matchId = targetId && a.id === targetId;
      const matchEmail = targetEmail && (a.email || a.name || "").toLowerCase() === targetEmail;
      return matchId || matchEmail;
    });
  }

  if (foundIdx !== -1) {
    const served = Math.max(0, parseInt(savedState.current_req_served, 10) || 0);
    return { accountIndex: foundIdx, currentAccRequestsServed: served, matched: true };
  }

  const fallbackIdx = Math.max(0, parseInt(savedState.account_index, 10) || 0) % accounts.length;
  return { accountIndex: fallbackIdx, currentAccRequestsServed: 0, matched: false };
}

function resolvePinnedKey(savedState) {
  if (!savedState || typeof savedState !== "object") return null;
  const email = String(savedState.pinned_account_email || "").trim();
  const id = String(savedState.pinned_account_id || "").trim();
  if (!email && !id) return null;
  return { id, email };
}

function serializeRuleStates(ruleCursors, modelRules = null) {
  if (!(ruleCursors instanceof Map) || ruleCursors.size === 0) return {};
  const validKeys = new Set();
  if (Array.isArray(modelRules)) {
    modelRules.forEach((r, idx) => {
      if (!r || typeof r !== "object") return;
      const firstPat = (Array.isArray(r.patterns) ? r.patterns.find((p) => String(p || "").trim()) : "") || r.pattern || "";
      validKeys.add(r.id || `${idx}:${String(firstPat).trim()}`);
    });
  }
  const out = {};
  for (const [key, val] of ruleCursors.entries()) {
    if (Array.isArray(modelRules) && !validKeys.has(key)) continue;
    if (typeof val === "number") {
      out[key] = {
        account_index: Math.max(0, Math.floor(val)),
        current_req_served: 0,
        last_account_email: "",
        last_account_id: ""
      };
    } else if (val && typeof val === "object") {
      out[key] = {
        account_index: Math.max(0, parseInt(val.accountIndex, 10) || 0),
        current_req_served: Math.max(0, parseInt(val.served, 10) || 0),
        last_account_email: String(val.lastAccountEmail || ""),
        last_account_id: String(val.lastAccountId || "")
      };
    }
  }
  return out;
}

function restoreRuleStates(rawRuleStates) {
  const map = new Map();
  if (!rawRuleStates || typeof rawRuleStates !== "object") return map;
  for (const [key, val] of Object.entries(rawRuleStates)) {
    if (typeof val === "number") {
      map.set(key, {
        accountIndex: Math.max(0, Math.floor(val)),
        served: 0,
        lastAccountId: "",
        lastAccountEmail: ""
      });
    } else if (val && typeof val === "object") {
      map.set(key, {
        accountIndex: Math.max(0, parseInt(val.account_index, 10) || 0),
        served: Math.max(0, parseInt(val.current_req_served, 10) || 0),
        lastAccountId: String(val.last_account_id || "").trim(),
        lastAccountEmail: String(val.last_account_email || "").trim()
      });
    }
  }
  return map;
}

module.exports = {
  saveRotatorState,
  saveRotatorStateAsync,
  restoreRotatorState,
  cleanOrphanedState,
  resolveRestoredAccount,
  resolvePinnedKey,
  serializeRuleStates,
  restoreRuleStates
};
