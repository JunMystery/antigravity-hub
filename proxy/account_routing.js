function isSameAccount(a, b) {
  if (!a || !b) return false;
  if (a.id && b.id && String(a.id) === String(b.id)) return true;
  if (a.email && b.email && a.email.toLowerCase() === b.email.toLowerCase()) return true;
  return false;
}

function findAccountByKey(accounts = [], keyObj = null) {
  if (!Array.isArray(accounts) || accounts.length === 0 || !keyObj) return null;
  const rawId = typeof keyObj === "string" ? keyObj : (keyObj.id || "");
  const rawEmail = typeof keyObj === "string" ? keyObj : (keyObj.email || "");
  const targetId = String(rawId).trim().toLowerCase();
  const targetEmail = String(rawEmail).trim().toLowerCase();
  if (!targetId && !targetEmail) return null;

  return accounts.find((acc) => {
    if (!acc) return false;
    const accId = acc.id ? String(acc.id).trim().toLowerCase() : "";
    const accEmail = (acc.email || acc.name || "").trim().toLowerCase();
    return Boolean((targetId && accId === targetId) || (targetEmail && accEmail === targetEmail));
  }) || null;
}

function matchModelRule(modelName, modelRules = [], allAccounts = []) {
  if (!modelName || !Array.isArray(modelRules) || modelRules.length === 0) return null;
  const lowerModel = String(modelName).trim().toLowerCase();
  if (!lowerModel) return null;

  for (const rule of modelRules) {
    if (!rule || rule.enabled === false) continue;
    const pats = Array.isArray(rule.patterns) && rule.patterns.length > 0
      ? rule.patterns
      : (rule.pattern ? [rule.pattern] : []);
    if (!pats.some((p) => {
      const pat = String(p || "").trim().toLowerCase();
      return Boolean(pat && lowerModel.includes(pat));
    })) continue;

    const ref = (Array.isArray(rule.accounts) && rule.accounts[0]) || {
      id: rule.account_id,
      email: rule.account_email
    };
    const targetAcc = findAccountByKey(allAccounts, ref);
    if (targetAcc) {
      return { account: targetAcc, rule };
    }
  }
  return null;
}

function buildLiveStatusPayload(rotator, extra = {}) {
  const cur = extra.account || rotator.getCurrentAccount();
  const pool = rotator.allAccounts.length > 0 ? rotator.allAccounts : rotator.accounts;
  const pinnedAcc = (rotator.rotationPaused && rotator.pinnedAccountKey)
    ? findAccountByKey(pool, rotator.pinnedAccountKey)
    : null;
  const isPinned = Boolean(pinnedAcc);
  const pinnedEmail = pinnedAcc?.email || "";
  const pinnedId = pinnedAcc?.id || "";

  return {
    active: Boolean(extra.active),
    timestamp: Date.now(),
    account_email: extra.account_email ?? cur?.email ?? "San sang",
    account_name: extra.account_name ?? cur?.name ?? cur?.email ?? "San sang",
    current_req: extra.current_req ?? rotator.currentAccRequestsServed,
    requests_per_account: rotator.requestsPerAccount,
    total_requests: extra.total_requests ?? rotator.requestCount,
    endpoint: extra.endpoint ?? "",
    method: extra.method ?? "",
    status: extra.status ?? (rotator.rotationPaused ? "paused" : "standby"),
    paused: Boolean(rotator.rotationPaused),
    pinned: isPinned,
    pinned_email: pinnedEmail,
    pinned_id: pinnedId,
    model_routed: extra.model_routed || "",
    ...(extra.statusCode !== undefined ? { statusCode: extra.statusCode } : {})
  };
}

function handleRotatorCommand(rotator, cmd, httpRes, writeLiveStatus, params = {}) {
  console.log(`[PROXY-CMD] [CMD] Nhan lenh tu Launcher: ${cmd}`);
  const respond = (statusCode, payload) => {
    if (!httpRes) return;
    httpRes.writeHead(statusCode, { "Content-Type": "application/json" });
    httpRes.end(JSON.stringify(payload));
  };

  if (cmd === "reload") {
    rotator.allAccounts.forEach((a) => { a.unhealthyUntil = 0; });
    rotator.accounts.forEach((a) => { a.unhealthyUntil = 0; });
    rotator.loadState();
    writeLiveStatus(buildLiveStatusPayload(rotator, { endpoint: "reload", method: "RELOAD" }));
    return respond(200, { success: true, count: rotator.accounts.length, allCount: rotator.allAccounts.length });
  }
  rotator.loadState();

  if (cmd === "pin_account") {
    const pool = rotator.allAccounts.length > 0 ? rotator.allAccounts : rotator.accounts;
    const target = findAccountByKey(pool, { id: params?.id, email: params?.email });
    if (!target) {
      return respond(404, { success: false, error: "Account not found" });
    }
    rotator.pinnedAccountKey = { id: target.id || "", email: target.email || "" };
    rotator.rotationPaused = true;
    rotator.currentAccRequestsServed = 0;
    const activeIdx = rotator.accounts.findIndex((a) => isSameAccount(a, target));
    if (activeIdx !== -1) rotator.accountIndex = activeIdx;
    rotator.saveRotatorState();
    writeLiveStatus(buildLiveStatusPayload(rotator, {
      endpoint: `Ghim co dinh: ${target.email}`,
      method: "PIN",
      status: "paused"
    }));
    return respond(200, { success: true, paused: true, pinned: true, email: target.email, id: target.id || "" });
  }

  if (cmd === "next") {
    rotator.nextAccount();
    const cur = rotator.getCurrentAccount();
    writeLiveStatus(buildLiveStatusPayload(rotator, { endpoint: "manual_switch", method: "SWITCH" }));
    return respond(200, { success: true, message: `Switched to ${cur?.email}`, paused: rotator.rotationPaused });
  }

  if (cmd === "toggle_pause" || cmd === "pause" || cmd === "resume" || cmd === "unpin_account") {
    const nextPaused = (cmd === "pause")
      ? true
      : ((cmd === "resume" || cmd === "unpin_account") ? false : !rotator.rotationPaused);
    rotator.rotationPaused = nextPaused;

    if (nextPaused) {
      const cur = rotator.getCurrentAccount();
      if (cur && !rotator.pinnedAccountKey) {
        rotator.pinnedAccountKey = { id: cur.id || "", email: cur.email || "" };
      }
    } else {
      rotator.pinnedAccountKey = null;
    }

    rotator.saveRotatorState();
    const statusLabel = rotator.rotationPaused ? "paused" : "standby";
    console.log(`[ROUND-ROBIN] Che do xoay vong: ${rotator.rotationPaused ? "TAM DUNG (PAUSED)" : "HOAT DONG (STANDBY)"}`);
    writeLiveStatus(buildLiveStatusPayload(rotator, {
      endpoint: rotator.rotationPaused ? "Tam dung xoay vong" : "Dang lang nghe Port 20130",
      method: rotator.rotationPaused ? "PAUSE" : "STANDBY",
      status: statusLabel
    }));
    return respond(200, { success: true, paused: rotator.rotationPaused, pinned: Boolean(rotator.pinnedAccountKey), status: statusLabel });
  }

  return respond(400, { error: "Unknown command" });
}

module.exports = {
  isSameAccount,
  findAccountByKey,
  matchModelRule,
  buildLiveStatusPayload,
  handleRotatorCommand
};
