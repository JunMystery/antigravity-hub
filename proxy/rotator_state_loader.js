const fs = require("node:fs");

function normalizeKey(acc) {
  return String(acc?.email || acc?.name || "").trim().toLowerCase();
}

function buildCooldownMap(prevAccounts = []) {
  const map = new Map();
  const now = Date.now();
  for (const acc of prevAccounts) {
    if (acc && acc.unhealthyUntil && acc.unhealthyUntil > now) {
      if (acc.id) map.set(`id:${String(acc.id).toLowerCase()}`, acc.unhealthyUntil);
      if (acc.email) map.set(`email:${acc.email.toLowerCase()}`, acc.unhealthyUntil);
    }
  }
  return map;
}

function restoreCooldown(acc, cooldownMap) {
  if (!acc || !cooldownMap || cooldownMap.size === 0) return;
  const idKey = acc.id ? `id:${String(acc.id).toLowerCase()}` : null;
  const emailKey = acc.email ? `email:${acc.email.toLowerCase()}` : null;
  if (idKey && cooldownMap.has(idKey)) {
    acc.unhealthyUntil = cooldownMap.get(idKey);
  } else if (emailKey && cooldownMap.has(emailKey)) {
    acc.unhealthyUntil = cooldownMap.get(emailKey);
  }
}

function normalizeRulePatterns(rawRule) {
  if (!rawRule || typeof rawRule !== "object") return [];
  const rawList = Array.isArray(rawRule.patterns) && rawRule.patterns.length > 0
    ? rawRule.patterns
    : (rawRule.pattern ? [rawRule.pattern] : []);
  const seen = new Set();
  const result = [];
  for (const item of rawList) {
    const val = String(item || "").trim();
    if (!val) continue;
    const key = val.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      result.push(val);
    }
  }
  return result;
}

function sanitizeModelRules(rawRules) {
  if (!Array.isArray(rawRules)) return [];
  return rawRules
    .map((r, idx) => {
      if (!r || typeof r !== "object") return null;
      const patterns = normalizeRulePatterns(r);
      if (patterns.length === 0) return null;
      const primaryPattern = patterns[0];
      const defaultName = patterns.length > 1
        ? `${primaryPattern} (+${patterns.length - 1})`
        : primaryPattern;
      const rawType = String(r.match_type || "contains").toLowerCase();
      const matchType = ["contains", "exact", "regex"].includes(rawType) ? rawType : "contains";
      const strategy = String(r.strategy || "").toLowerCase() === "round_robin" ? "round_robin" : "priority";
      const accounts = (Array.isArray(r.accounts) ? r.accounts : [])
        .filter((a) => a && typeof a === "object" && (a.id || a.email))
        .map((a) => ({ id: a.id ? String(a.id) : "", email: a.email ? String(a.email) : "" }));
      const legacyId = r.account_id ? String(r.account_id) : "";
      const legacyEmail = r.account_email ? String(r.account_email) : "";
      if (accounts.length === 0 && (legacyId || legacyEmail)) {
        accounts.push({ id: legacyId, email: legacyEmail });
      }
      return {
        id: r.id ? String(r.id) : `rule_${idx}`,
        name: r.name ? String(r.name) : defaultName,
        pattern: primaryPattern,
        patterns,
        match_type: matchType,
        strategy,
        fallback_to_global: Boolean(r.fallback_to_global),
        accounts,
        account_id: legacyId || accounts[0]?.id || "",
        account_email: legacyEmail || accounts[0]?.email || "",
        enabled: r.enabled !== false
      };
    })
    .filter(Boolean);
}

function loadRotatorDiskState(config, prevAllAccounts = []) {
  if (!config?.ACCOUNTS_FILE || !fs.existsSync(config.ACCOUNTS_FILE)) {
    return null;
  }

  const accData = JSON.parse(fs.readFileSync(config.ACCOUNTS_FILE, "utf8"));
  const rawAccounts = Array.isArray(accData.accounts) ? accData.accounts : [];

  let enabledEmails = null;
  let requestsPerAccount = 1;
  let modelRules = [];
  const orderMap = new Map();

  if (config.PROFILES_FILE && fs.existsSync(config.PROFILES_FILE)) {
    try {
      const cfg = JSON.parse(fs.readFileSync(config.PROFILES_FILE, "utf8"));
      requestsPerAccount = Math.max(1, parseInt(cfg.settings?.requests_per_account, 10) || 1);
      modelRules = sanitizeModelRules(cfg.settings?.model_rules);
      (cfg.profiles || []).forEach((p, idx) => {
        const prio = typeof p.order === "number" ? p.order : (idx + 1);
        if (p.email) orderMap.set(p.email.toLowerCase(), prio);
        if (p.name) orderMap.set(p.name.toLowerCase(), prio);
        if (p.id) orderMap.set(String(p.id).toLowerCase(), prio);
      });
      if (Array.isArray(cfg.profiles) && cfg.profiles.length > 0) {
        enabledEmails = new Set(
          cfg.profiles
            .filter((p) => p.enabled !== false)
            .map((p) => normalizeKey(p))
            .filter(Boolean)
        );
      }
    } catch (_) {}
  }

  const cooldownMap = buildCooldownMap(prevAllAccounts);
  const allTokenAccounts = rawAccounts
    .filter((acc) => Boolean(acc && (acc.accessToken || acc.refreshToken)))
    .map((acc) => {
      const cloned = { ...acc };
      restoreCooldown(cloned, cooldownMap);
      return cloned;
    });

  allTokenAccounts.sort((a, b) => {
    const keyA = normalizeKey(a);
    const keyB = normalizeKey(b);
    return (orderMap.get(keyA) ?? 99999) - (orderMap.get(keyB) ?? 99999);
  });

  const activeAccounts = allTokenAccounts.filter((acc) => {
    if (!enabledEmails) return true;
    return enabledEmails.has(normalizeKey(acc));
  });

  return {
    allTokenAccounts,
    activeAccounts,
    requestsPerAccount,
    modelRules
  };
}

module.exports = {
  loadRotatorDiskState,
  sanitizeModelRules
};
