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

function getRuleCursorKey(rule, idx = 0) {
  const patterns = getRulePatterns(rule);
  return rule?.id || `${idx}:${patterns[0] || ""}`;
}

function resolveRuleState(pool, rawState) {
  if (!Array.isArray(pool) || pool.length === 0) return { accountIndex: 0, served: 0 };
  if (typeof rawState === "number") {
    return { accountIndex: Math.max(0, Math.floor(rawState)) % pool.length, served: 0 };
  }
  if (rawState && typeof rawState === "object") {
    if (rawState.lastAccountId || rawState.lastAccountEmail) {
      const matched = findAccountByKey(pool, { id: rawState.lastAccountId, email: rawState.lastAccountEmail });
      const foundIdx = matched ? pool.findIndex((a) => isSameAccount(a, matched)) : -1;
      if (foundIdx !== -1) {
        return { accountIndex: foundIdx, served: Math.max(0, parseInt(rawState.served, 10) || 0) };
      }
    }
    return { accountIndex: Math.max(0, parseInt(rawState.accountIndex, 10) || 0) % pool.length, served: 0 };
  }
  return { accountIndex: 0, served: 0 };
}

function updateRuleCursorState(ruleCursors, cursorKey, pool, chosenIdx, servedCount, threshold) {
  if (!(ruleCursors instanceof Map) || !cursorKey || !Array.isArray(pool) || pool.length === 0) return;
  const advance = servedCount >= threshold;
  const nextIdx = advance ? (chosenIdx + 1) % pool.length : chosenIdx;
  const nextServed = advance ? 0 : servedCount;
  const nextAcc = pool[nextIdx];
  ruleCursors.set(cursorKey, {
    accountIndex: nextIdx,
    served: nextServed,
    lastAccountId: nextAcc?.id || "",
    lastAccountEmail: nextAcc?.email || ""
  });
}

function allocateForModelRule(modelName, modelRules, allAccounts, ruleCursors = new Map(), globalRequestsPerAccount = 1) {
  if (!modelName || !Array.isArray(modelRules) || !Array.isArray(allAccounts) || allAccounts.length === 0) {
    return null;
  }

  const now = Date.now();
  const baseThreshold = Math.max(1, parseInt(globalRequestsPerAccount, 10) || 1);
  for (let idx = 0; idx < modelRules.length; idx++) {
    const rule = modelRules[idx];
    if (!doesPatternMatch(modelName, rule)) continue;

    const pool = resolveRulePool(rule, allAccounts);
    if (pool.length === 0) continue;

    const fallbackToGlobal = Boolean(rule.fallback_to_global);
    const strategy = String(rule.strategy || "priority").toLowerCase() === "round_robin" ? "round_robin" : "priority";
    const rawRuleReqs = parseInt(rule.requests_per_account, 10);
    const effectiveThreshold = Number.isFinite(rawRuleReqs) && rawRuleReqs > 0 ? rawRuleReqs : baseThreshold;
    const cursorKey = getRuleCursorKey(rule, idx);
    const healthy = pool.filter((acc) => isAccountHealthy(acc, now));

    if (healthy.length === 0) {
      if (fallbackToGlobal) return null;
      return {
        account: pool[0], rule, rulePool: pool, fallbackToGlobal: false,
        ruleStrategy: strategy, servedCount: 1,
        requestsPerAccount: strategy === "round_robin" ? effectiveThreshold : 1,
        ruleCursorKey: cursorKey, startIndex: 0
      };
    }

    if (strategy !== "round_robin") {
      const chosen = healthy[0];
      const startIndex = Math.max(0, pool.indexOf(chosen));
      return {
        account: chosen, rule, rulePool: pool, fallbackToGlobal,
        ruleStrategy: "priority", servedCount: 1, requestsPerAccount: 1,
        ruleCursorKey: cursorKey, startIndex
      };
    }

    const state = resolveRuleState(pool, ruleCursors instanceof Map ? ruleCursors.get(cursorKey) : null);
    let startIdx = state.accountIndex % pool.length;
    let baseServed = state.served;
    if (baseServed >= effectiveThreshold) {
      startIdx = (startIdx + 1) % pool.length;
      baseServed = 0;
    }
    let chosenIdx = startIdx;
    let skipped = false;
    for (let i = 0; i < pool.length; i++) {
      const candIdx = (startIdx + i) % pool.length;
      if (isAccountHealthy(pool[candIdx], now)) {
        chosenIdx = candIdx;
        skipped = i > 0;
        break;
      }
    }
    const servedCount = (skipped ? 0 : baseServed) + 1;
    updateRuleCursorState(ruleCursors, cursorKey, pool, chosenIdx, servedCount, effectiveThreshold);
    return {
      account: pool[chosenIdx], rule, rulePool: pool, fallbackToGlobal,
      ruleStrategy: "round_robin", servedCount, requestsPerAccount: effectiveThreshold,
      ruleCursorKey: cursorKey, startIndex: chosenIdx
    };
  }

  return null;
}

function pickNextRuleAccount(rulePool, triedAccounts, fallbackToGlobal, globalNextFn, now = Date.now(), startIndex = 0) {
  const pool = Array.isArray(rulePool) ? rulePool : [];
  const tried = Array.isArray(triedAccounts) ? triedAccounts : [];

  for (let offset = 0; offset < pool.length; offset++) {
    const idx = ((startIndex % pool.length) + pool.length + offset) % pool.length;
    const acc = pool[idx];
    if (isAccountHealthy(acc, now) && !tried.some((prev) => isSameAccount(prev, acc))) {
      tried.push(acc);
      return acc;
    }
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

  let lastRuleIdx = Number.isInteger(allocation?.startIndex) ? allocation.startIndex : 0;
  let currentRuleServed = allocation?.servedCount || 1;
  const ruleStrategy = allocation?.ruleStrategy || "";
  const ruleThreshold = allocation?.requestsPerAccount || rotator.requestsPerAccount;
  const ruleCursorKey = allocation?.ruleCursorKey || "";

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
      const failedIdx = failedAcc ? rulePool.findIndex((a) => isSameAccount(a, failedAcc)) : -1;
      const failStart = rulePool.length > 0 ? ((failedIdx >= 0 ? failedIdx : lastRuleIdx) + 1) % rulePool.length : 0;
      const picked = pickNextRuleAccount(
        rulePool, triedAccounts, fallbackToGlobal,
        (altFailed) => globalNextFn(sId, isFail, isSub, altFailed || failedAcc),
        Date.now(), failStart
      );
      const pickedIdx = picked ? rulePool.findIndex((a) => isSameAccount(a, picked)) : -1;
      if (pickedIdx >= 0) {
        lastRuleIdx = pickedIdx;
        currentRuleServed = 1;
        if (ruleStrategy === "round_robin" && ruleCursorKey && rotator.ruleCursors instanceof Map) {
          updateRuleCursorState(rotator.ruleCursors, ruleCursorKey, rulePool, pickedIdx, 1, ruleThreshold);
          if (typeof rotator.saveRotatorStateDebounced === "function") rotator.saveRotatorStateDebounced();
        }
      }
      return picked;
    },
    get accountIndex() { return rotator.accountIndex; },
    get currentAccRequestsServed() { return rotator.currentAccRequestsServed; },
    get requestsPerAccount() { return rulePool ? ruleThreshold : rotator.requestsPerAccount; },
    get requestCount() { return rotator.requestCount; },
    get rotationPaused() { return rotator.rotationPaused; },
    buildLiveStatus: (extra) => buildLiveStatusPayload(rotator, {
      ...(rulePool ? { current_req: currentRuleServed, requests_per_account: ruleThreshold, model_rule_strategy: ruleStrategy } : {}),
      ...extra
    }),
    writeLiveStatus
  };
}

module.exports = {
  getRulePatterns,
  getRuleCursorKey,
  doesPatternMatch,
  resolveRulePool,
  allocateForModelRule,
  pickNextRuleAccount,
  buildRequestContext
};
