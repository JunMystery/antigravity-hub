/**
 * @fileoverview Engine dinh tuyen Model Rules nang cao cho Antigravity Micro-Proxy.
 * Ho tro khop contains/exact/regex, da tai khoan uu tien hoac round-robin trong nhom,
 * va kiem soat pham vi fallback khi toan bo tai khoan trong rule gap loi.
 */

const { isSameAccount, findAccountByKey, buildLiveStatusPayload } = require("./account_routing");

function getRulePatterns(rule) {
  if (!rule || typeof rule !== "object") return [];
  const rawList = Array.isArray(rule.patterns) && rule.patterns.length > 0
    ? rule.patterns
    : (rule.pattern ? [rule.pattern] : []);
  return rawList.map((p) => String(p || "").trim()).filter(Boolean);
}

function matchesSinglePattern(target, pat, matchType) {
  if (matchType === "exact") {
    return target.toLowerCase() === pat.toLowerCase();
  }
  if (matchType === "regex") {
    try {
      return new RegExp(pat, "i").test(target);
    } catch {
      return false;
    }
  }
  return target.toLowerCase().includes(pat.toLowerCase());
}

function doesPatternMatch(modelName, rule) {
  if (!modelName || !rule || rule.enabled === false) return false;
  const patterns = getRulePatterns(rule);
  if (patterns.length === 0) return false;

  const target = String(modelName);
  const matchType = String(rule.match_type || "contains").toLowerCase();
  return patterns.some((pat) => matchesSinglePattern(target, pat, matchType));
}

function resolveRulePool(rule, allAccounts) {
  if (!rule || !Array.isArray(allAccounts) || allAccounts.length === 0) return [];
  const rawRefs = Array.isArray(rule.accounts) && rule.accounts.length > 0
    ? rule.accounts
    : [{ id: rule.account_id || "", email: rule.account_email || "" }];

  const pool = [];
  for (const ref of rawRefs) {
    if (!ref || (!ref.id && !ref.email)) continue;
    const acc = findAccountByKey(allAccounts, ref);
    if (acc && !pool.some((existing) => isSameAccount(existing, acc))) {
      pool.push(acc);
    }
  }
  return pool;
}

function isAccountHealthy(acc, now = Date.now()) {
  return Boolean(acc && (!acc.unhealthyUntil || acc.unhealthyUntil <= now));
}

function allocateForModelRule(modelName, modelRules, allAccounts, ruleCursors = new Map()) {
  if (!modelName || !Array.isArray(modelRules) || !Array.isArray(allAccounts) || allAccounts.length === 0) {
    return null;
  }

  const now = Date.now();
  for (let idx = 0; idx < modelRules.length; idx++) {
    const rule = modelRules[idx];
    if (!doesPatternMatch(modelName, rule)) continue;

    const pool = resolveRulePool(rule, allAccounts);
    if (pool.length === 0) continue;

    const fallbackToGlobal = Boolean(rule.fallback_to_global);
    const healthy = pool.filter((acc) => isAccountHealthy(acc, now));

    if (healthy.length === 0) {
      if (fallbackToGlobal) return null;
      return { account: pool[0], rule, rulePool: pool, fallbackToGlobal: false };
    }

    let chosen = healthy[0];
    if (String(rule.strategy || "priority").toLowerCase() === "round_robin") {
      const patterns = getRulePatterns(rule);
      const cursorKey = rule.id || `${idx}:${patterns[0] || ""}`;
      const cursor = ruleCursors.get(cursorKey) || 0;
      chosen = healthy[cursor % healthy.length];
      ruleCursors.set(cursorKey, (cursor + 1) % healthy.length);
    }

    return { account: chosen, rule, rulePool: pool, fallbackToGlobal };
  }

  return null;
}

function pickNextRuleAccount(rulePool, triedAccounts, fallbackToGlobal, globalNextFn, now = Date.now()) {
  const pool = Array.isArray(rulePool) ? rulePool : [];
  const tried = Array.isArray(triedAccounts) ? triedAccounts : [];

  const nextInPool = pool.find(
    (acc) => isAccountHealthy(acc, now) && !tried.some((prev) => isSameAccount(prev, acc))
  );
  if (nextInPool) {
    tried.push(nextInPool);
    return nextInPool;
  }

  if (fallbackToGlobal && typeof globalNextFn === "function") {
    let acc = globalNextFn();
    for (let i = 0; i < pool.length && acc && tried.some((prev) => isSameAccount(prev, acc)); i++) {
      const nextAlt = globalNextFn(acc);
      if (!nextAlt || isSameAccount(nextAlt, acc)) break;
      acc = nextAlt;
    }
    return acc;
  }
  return null;
}

function buildRequestContext(rotator, config, writeLiveStatus, sessionId = null, isSubagent = false, allocation = null) {
  const rulePool = Array.isArray(allocation?.rulePool) ? allocation.rulePool : null;
  const fallbackToGlobal = Boolean(allocation?.fallbackToGlobal);
  const triedAccounts = allocation?.account ? [allocation.account] : [];
  const ruleLocked = Boolean(rulePool && !fallbackToGlobal && rulePool.length <= 1);
  const maxFailoverAttempts = rulePool
    ? rulePool.length + (fallbackToGlobal ? (rotator.accounts.length || 1) : 0)
    : (rotator.accounts.length || 1);
  const globalNextFn = (sId = null, isFail = false, isSub = false, failedAcc = null) =>
    rotator.nextAccount(sId || sessionId, isFail, isSub !== undefined ? isSub : isSubagent, failedAcc);

  return {
    config, sessionId, isSubagent,
    isAccountLocked: rulePool ? ruleLocked : Boolean(allocation?.isLocked),
    maxFailoverAttempts,
    modelRouted: allocation?.matchedRuleName || allocation?.matchedRule || "",
    get accounts() { return rotator.accounts; },
    getCurrentAccount: () => rotator.getCurrentAccount(),
    nextAccount: (sId = null, isFail = false, isSub = false, failedAcc = null) => {
      if (!rulePool) return globalNextFn(sId, isFail, isSub, failedAcc);
      if (failedAcc && !triedAccounts.some((prev) => isSameAccount(prev, failedAcc))) triedAccounts.push(failedAcc);
      return pickNextRuleAccount(
        rulePool, triedAccounts, fallbackToGlobal,
        (altFailed) => globalNextFn(sId, isFail, isSub, altFailed || failedAcc)
      );
    },
    get accountIndex() { return rotator.accountIndex; },
    get currentAccRequestsServed() { return rotator.currentAccRequestsServed; },
    get requestsPerAccount() { return rotator.requestsPerAccount; },
    get requestCount() { return rotator.requestCount; },
    get rotationPaused() { return rotator.rotationPaused; },
    buildLiveStatus: (extra) => buildLiveStatusPayload(rotator, extra),
    writeLiveStatus
  };
}

module.exports = {
  getRulePatterns,
  doesPatternMatch,
  resolveRulePool,
  allocateForModelRule,
  pickNextRuleAccount,
  buildRequestContext
};
