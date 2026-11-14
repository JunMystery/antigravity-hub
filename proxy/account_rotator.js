const fs = require("node:fs");
const { checkProactiveTokenRefresh } = require("./token_manager");
const { agentPool } = require("./agent_pool");

/**
 * Quan ly xoay vong tai khoan Round Robin theo thu tu uu tien (Priority / Order)
 * Co co che luu va khoi phuc trang thai ben vung qua file rotator_state.json.
 */
class AccountRotator {
  constructor(config) {
    this.config = config;
    this.accounts = [];
    this.accountIndex = 0;
    this.requestCount = 0;
    this.currentAccRequestsServed = 0;
    this.requestsPerAccount = 1;
    this.isRestored = false;
  }

  getCurrentAccount() {
    const total = this.accounts.length || 1;
    return this.accounts[this.accountIndex % total] || null;
  }

  nextAccount() {
    const total = this.accounts.length || 1;
    this.accountIndex = (this.accountIndex + 1) % total;
    this.currentAccRequestsServed = 0;
    this.saveRotatorState();
    return this.getCurrentAccount();
  }

  /**
   * Phan bo tai khoan nguyen tu cho tung request den, tranh race condition
   */
  allocateAccountForRequest() {
    if (this.accounts.length === 0) {
      this.loadState();
    }
    const current = this.getCurrentAccount();
    this.requestCount++;
    this.currentAccRequestsServed++;
    const served = this.currentAccRequestsServed;

    if (this.currentAccRequestsServed >= this.requestsPerAccount) {
      this.nextAccount();
    } else {
      this.saveRotatorState();
    }

    return {
      account: current,
      servedCount: served,
      requestNumber: this.requestCount
    };
  }

  /**
   * Luu trang thai luot tai khoan hien tai vao rotator_state.json
   */
  saveRotatorState() {
    if (!this.config?.ROTATOR_STATE_FILE) return;
    try {
      const cur = this.getCurrentAccount();
      const state = {
        last_account_email: cur?.email || "",
        last_account_id: cur?.id || "",
        account_index: this.accountIndex,
        current_req_served: this.currentAccRequestsServed,
        total_requests: this.requestCount,
        updated_at: Date.now()
      };
      fs.writeFileSync(this.config.ROTATOR_STATE_FILE, JSON.stringify(state, null, 2), "utf8");
    } catch (err) {
      console.error("[ROTATOR-SAVE-ERR] Loi ghi rotator_state.json:", err.message);
    }
  }

  /**
   * Khoi phuc chinh xac luot tai khoan theo Email hoac tu dong chuyen tiep
   */
  restoreRotatorState() {
    if (!this.config?.ROTATOR_STATE_FILE || !fs.existsSync(this.config.ROTATOR_STATE_FILE)) {
      return;
    }
    try {
      const raw = fs.readFileSync(this.config.ROTATOR_STATE_FILE, "utf8");
      if (!raw) return;
      const state = JSON.parse(raw);
      if (typeof state.total_requests === "number") {
        this.requestCount = state.total_requests;
      }

      if (this.accounts.length === 0) return;

      const targetEmail = (state.last_account_email || "").toLowerCase();
      const targetId = state.last_account_id;

      let foundIdx = -1;
      if (targetId || targetEmail) {
        foundIdx = this.accounts.findIndex((a) => {
          const matchId = targetId && a.id === targetId;
          const matchEmail = targetEmail && (a.email || a.name || "").toLowerCase() === targetEmail;
          return matchId || matchEmail;
        });
      }

      if (foundIdx !== -1) {
        this.accountIndex = foundIdx;
        this.currentAccRequestsServed = Math.max(0, parseInt(state.current_req_served, 10) || 0);
        console.log(`[ROTATOR-RESTORE] [OK] Khoi phuc tai khoan: [${this.accounts[foundIdx].email}] (Luot: ${this.currentAccRequestsServed}/${this.requestsPerAccount})`);
      } else {
        const fallbackIdx = Math.max(0, parseInt(state.account_index, 10) || 0) % this.accounts.length;
        this.accountIndex = fallbackIdx;
        this.currentAccRequestsServed = 0;
        console.log(`[ROTATOR-RESTORE] [FALLBACK] Tai khoan cu khong con active, chuyen sang: [${this.accounts[fallbackIdx].email}]`);
      }
    } catch (err) {
      console.error("[ROTATOR-RESTORE-ERR] Loi doc rotator_state.json:", err.message);
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
            (cfg.profiles || [])
              .filter((p) => p.enabled !== false)
              .map((p) => (p.email || p.name || "").toLowerCase())
          );
        } catch (_) {}
      }

      const valid = [];
      for (const acc of allAccounts) {
        const email = (acc.email || acc.name || "").toLowerCase();
        if (enabledEmails && enabledEmails.size > 0 && !enabledEmails.has(email)) continue;
        if (acc.accessToken || acc.refreshToken) valid.push(acc);
      }

      // Sap xep danh sach theo thu tu uu tien (Priority/Order)
      valid.sort((a, b) => {
        const keyA = (a.email || a.name || "").toLowerCase();
        const keyB = (b.email || b.name || "").toLowerCase();
        const ordA = orderMap.has(keyA) ? orderMap.get(keyA) : 99999;
        const ordB = orderMap.has(keyB) ? orderMap.get(keyB) : 99999;
        return ordA - ordB;
      });

      if (valid.length > 0) {
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
        active: false,
        timestamp: Date.now(),
        account_email: cur?.email || "UNKNOWN",
        account_name: cur?.name || cur?.email || "UNKNOWN",
        current_req: this.currentAccRequestsServed,
        requests_per_account: this.requestsPerAccount,
        total_requests: this.requestCount,
        endpoint: "manual_switch",
        method: "SWITCH",
        status: "idle"
      });
      if (httpRes) {
        httpRes.writeHead(200, { "Content-Type": "application/json" });
        httpRes.end(JSON.stringify({ success: true, message: `Switched to ${cur?.email}` }));
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
