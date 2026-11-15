const fs = require("node:fs");
const { checkProactiveTokenRefresh } = require("./token_manager");
const { agentPool } = require("./agent_pool");
const { sessionAffinity } = require("./session_affinity");
const {
  saveRotatorState,
  saveRotatorStateAsync,
  restoreRotatorState,
  resolveRestoredAccount
} = require("./rotator_persistence");

// Quan ly xoay vong tai khoan Round Robin co persistent state va session affinity
class AccountRotator {
  constructor(config) {
    this.config = config;
    this.accounts = [];
    this.accountIndex = 0;
    this.requestCount = 0;
    this.currentAccRequestsServed = 0;
    this.requestsPerAccount = 1;
    this.isRestored = false;
    this.rotationPaused = false;
    this._saveTimer = null;
  }

  getCurrentAccount() {
    const total = this.accounts.length || 1;
    if (this.accounts.length === 0) return null;
    const now = Date.now();
    for (let i = 0; i < this.accounts.length; i++) {
      const acc = this.accounts[(this.accountIndex + i) % total];
      if (!acc.unhealthyUntil || acc.unhealthyUntil < now) return acc;
    }
    return this.accounts[this.accountIndex % total] || null;
  }

  nextAccount(sessionId = null, isFailover = false, isSubagent = false) {
    if (isSubagent && isFailover) return sessionAffinity.failoverSubagent(sessionId, this.accounts);
    const total = this.accounts.length || 1;
    this.accountIndex = (this.accountIndex + 1) % total;
    this.currentAccRequestsServed = 0;
    this.saveRotatorStateDebounced();
    return this.getCurrentAccount();
  }

  allocateAccountForRequest(reqUrl = "/", host = "", headers = {}, bodyBuffer = null) {
    if (this.accounts.length === 0) this.loadState();

    const sessionId = sessionAffinity.extractSessionId(headers, bodyBuffer);
    const isSub = sessionAffinity.isSubagent(reqUrl, host, headers, bodyBuffer, sessionId);

    if (isSub) {
      const subAlloc = sessionAffinity.allocateSubagentAccount(sessionId, this.accounts);
      if (subAlloc && subAlloc.account) {
        return {
          account: subAlloc.account, isSubagent: true, isSticky: subAlloc.isSticky,
          isNewSubagent: subAlloc.isNewSubagent, servedCount: 1,
          requestNumber: subAlloc.requestNumber, sessionId
        };
      }
    }

    if (sessionId && (!sessionAffinity.mainSessionId || !sessionAffinity.isMainSessionActive())) {
      sessionAffinity.setMainSession(sessionId, this.getCurrentAccount());
    }

    const current = this.getCurrentAccount();
    this.requestCount++;
    this.currentAccRequestsServed++;
    const served = this.currentAccRequestsServed;

    if (!this.rotationPaused) {
      if (this.currentAccRequestsServed >= this.requestsPerAccount) this.nextAccount();
      else this.saveRotatorStateDebounced();
    } else {
      this.saveRotatorStateDebounced();
    }

    return {
      account: current, isSubagent: false, servedCount: served,
      requestNumber: this.requestCount, sessionId
    };
  }

  saveRotatorStateDebounced(delay = 500) {
    if (this._saveTimer) return;
    this._saveTimer = setTimeout(() => {
      this._saveTimer = null;
      this.saveRotatorStateAsync().catch(() => {});
    }, delay);
  }

  async saveRotatorStateAsync() {
    if (!this.config?.ROTATOR_STATE_FILE) return;
    const cur = this.getCurrentAccount();
    return saveRotatorStateAsync(this.config.ROTATOR_STATE_FILE, {
      last_account_email: cur?.email || "",
      last_account_id: cur?.id || "",
      account_index: this.accountIndex,
      current_req_served: this.currentAccRequestsServed,
      total_requests: this.requestCount,
      rotation_paused: this.rotationPaused,
      updated_at: Date.now()
    });
  }

  saveRotatorState() {
    if (this._saveTimer) {
      clearTimeout(this._saveTimer);
      this._saveTimer = null;
    }
    if (!this.config?.ROTATOR_STATE_FILE) return;
    const cur = this.getCurrentAccount();
    saveRotatorState(this.config.ROTATOR_STATE_FILE, {
      last_account_email: cur?.email || "",
      last_account_id: cur?.id || "",
      account_index: this.accountIndex,
      current_req_served: this.currentAccRequestsServed,
      total_requests: this.requestCount,
      rotation_paused: this.rotationPaused,
      updated_at: Date.now()
    });
  }

  restoreRotatorState() {
    if (!this.config?.ROTATOR_STATE_FILE) return;
    const state = restoreRotatorState(this.config.ROTATOR_STATE_FILE);
    if (!state) return;
    if (typeof state.total_requests === "number") this.requestCount = state.total_requests;
    if (typeof state.rotation_paused === "boolean") this.rotationPaused = state.rotation_paused;
    if (this.accounts.length === 0) return;

    const resolved = resolveRestoredAccount(this.accounts, state);
    this.accountIndex = resolved.accountIndex;
    this.currentAccRequestsServed = resolved.currentAccRequestsServed;
    const restoredAcc = this.accounts[this.accountIndex];
    if (resolved.matched) {
      console.log(`[ROTATOR-RESTORE] [OK] Khoi phuc tai khoan: [${restoredAcc?.email}] (Luot: ${this.currentAccRequestsServed}/${this.requestsPerAccount})`);
    } else {
      console.log(`[ROTATOR-RESTORE] [FALLBACK] Tai khoan cu khong con active, chuyen sang: [${restoredAcc?.email}]`);
    }
  }

  loadState() {
    try {
      if (!fs.existsSync(this.config.ACCOUNTS_FILE)) return;
      const accData = JSON.parse(fs.readFileSync(this.config.ACCOUNTS_FILE, "utf8"));
      const allAccounts = accData.accounts || [];

      let enabledEmails = null;
      const orderMap = new Map();

      if (fs.existsSync(this.config.PROFILES_FILE)) {
        try {
          const cfg = JSON.parse(fs.readFileSync(this.config.PROFILES_FILE, "utf8"));
          this.requestsPerAccount = Math.max(1, parseInt(cfg.settings?.requests_per_account, 10) || 1);
          (cfg.profiles || []).forEach((p, idx) => {
            const prio = typeof p.order === "number" ? p.order : (idx + 1);
            if (p.email) orderMap.set(p.email.toLowerCase(), prio);
            if (p.name) orderMap.set(p.name.toLowerCase(), prio);
            if (p.id) orderMap.set(p.id.toLowerCase(), prio);
          });
          enabledEmails = new Set(
            (cfg.profiles || []).filter((p) => p.enabled !== false)
              .map((p) => (p.email || p.name || "").toLowerCase())
          );
        } catch (_) {}
      }

      const valid = allAccounts.filter((acc) => {
        const email = (acc.email || acc.name || "").toLowerCase();
        if (enabledEmails && enabledEmails.size > 0 && !enabledEmails.has(email)) return false;
        return Boolean(acc.accessToken || acc.refreshToken);
      });

      valid.sort((a, b) => {
        const keyA = (a.email || a.name || "").toLowerCase();
        const keyB = (b.email || b.name || "").toLowerCase();
        return (orderMap.get(keyA) ?? 99999) - (orderMap.get(keyB) ?? 99999);
      });

      if (valid.length > 0) {
        // Preserve in-memory runtime cooldowns (unhealthyUntil) across disk reloads
        const cooldownMap = new Map();
        for (const existing of this.accounts) {
          if (existing.unhealthyUntil && existing.unhealthyUntil > Date.now()) {
            if (existing.id) cooldownMap.set(String(existing.id).toLowerCase(), existing.unhealthyUntil);
            if (existing.email) cooldownMap.set(existing.email.toLowerCase(), existing.unhealthyUntil);
          }
        }

        for (const fresh of valid) {
          const freshId = fresh.id ? String(fresh.id).toLowerCase() : null;
          const freshEmail = fresh.email ? fresh.email.toLowerCase() : null;
          if (freshId && cooldownMap.has(freshId)) {
            fresh.unhealthyUntil = cooldownMap.get(freshId);
          } else if (freshEmail && cooldownMap.has(freshEmail)) {
            fresh.unhealthyUntil = cooldownMap.get(freshEmail);
          }
        }

        this.accounts = valid;
        if (!this.isRestored) {
          this.restoreRotatorState();
          this.isRestored = true;
        } else {
          this.accountIndex = this.accountIndex % this.accounts.length;
        }
        agentPool.cleanupDeadAgents(valid);
      }
      checkProactiveTokenRefresh(allAccounts, this.config).catch(() => {});
    } catch (err) {
      console.error("[STATE-LOAD-ERR] Loi nap accounts:", err.message);
    }
  }

  handleCommand(cmd, httpRes, writeLiveStatus) {
    console.log(`[PROXY-CMD] [CMD] Nhan lenh tu Launcher: ${cmd}`);
    this.loadState();

    if (cmd === "next") {
      this.nextAccount();
      const cur = this.getCurrentAccount();
      writeLiveStatus({
        active: false, timestamp: Date.now(), account_email: cur?.email || "UNKNOWN",
        account_name: cur?.name || cur?.email || "UNKNOWN", current_req: this.currentAccRequestsServed,
        requests_per_account: this.requestsPerAccount, total_requests: this.requestCount,
        endpoint: "manual_switch", method: "SWITCH", status: this.rotationPaused ? "paused" : "standby",
        paused: this.rotationPaused
      });
      if (httpRes) {
        httpRes.writeHead(200, { "Content-Type": "application/json" });
        httpRes.end(JSON.stringify({ success: true, message: `Switched to ${cur?.email}`, paused: this.rotationPaused }));
      }
      return;
    }

    if (cmd === "toggle_pause" || cmd === "pause" || cmd === "resume") {
      this.rotationPaused = cmd === "pause" ? true : (cmd === "resume" ? false : !this.rotationPaused);
      this.saveRotatorState();
      const cur = this.getCurrentAccount();
      const statusLabel = this.rotationPaused ? "paused" : "standby";
      console.log(`[ROUND-ROBIN] Che do xoay vong: ${this.rotationPaused ? "TAM DUNG (PAUSED)" : "HOAT DONG (STANDBY)"}`);
      writeLiveStatus({
        active: false, timestamp: Date.now(), account_email: cur?.email || "San sang",
        account_name: cur?.name || cur?.email || "San sang", current_req: this.currentAccRequestsServed,
        requests_per_account: this.requestsPerAccount, total_requests: this.requestCount,
        endpoint: this.rotationPaused ? "Tam dung xoay vong" : "Dang lang nghe Port 20130",
        method: this.rotationPaused ? "PAUSE" : "STANDBY", status: statusLabel, paused: this.rotationPaused
      });
      if (httpRes) {
        httpRes.writeHead(200, { "Content-Type": "application/json" });
        httpRes.end(JSON.stringify({ success: true, paused: this.rotationPaused, status: statusLabel }));
      }
      return;
    }

    if (httpRes) {
      httpRes.writeHead(400, { "Content-Type": "application/json" });
      httpRes.end(JSON.stringify({ error: "Unknown command" }));
    }
  }
}

module.exports = { AccountRotator };
