const { checkProactiveTokenRefresh } = require("./token_manager");
const { agentPool } = require("./agent_pool");
const { sessionAffinity } = require("./session_affinity");
const { extractModelName } = require("./chat_payload_helper");
const { loadRotatorDiskState } = require("./rotator_state_loader");
const { allocateForModelRule } = require("./model_rule_engine");
const {
  isSameAccount,
  findAccountByKey,
  handleRotatorCommand
} = require("./account_routing");
const {
  saveRotatorState,
  saveRotatorStateAsync,
  restoreRotatorState,
  resolveRestoredAccount,
  resolvePinnedKey,
  serializeRuleStates,
  restoreRuleStates
} = require("./rotator_persistence");

// Quan ly xoay vong tai khoan Round Robin, ghim tai khoan co dinh va dinh tuyen theo Model
class AccountRotator {
  constructor(config) {
    this.config = config;
    this.accounts = [];
    this.allAccounts = [];
    this.modelRules = [];
    this.accountIndex = 0;
    this.requestCount = 0;
    this.currentAccRequestsServed = 0;
    this.requestsPerAccount = 1;
    this.isRestored = false;
    this.rotationPaused = false;
    this.pinnedAccountKey = null;
    this.ruleCursors = new Map();
    this._saveTimer = null;
  }

  getCurrentAccount() {
    const pool = this.allAccounts.length > 0 ? this.allAccounts : this.accounts;
    if (this.rotationPaused && this.pinnedAccountKey) {
      const pinned = findAccountByKey(pool, this.pinnedAccountKey);
      if (pinned) return pinned;
    }

    const total = this.accounts.length;
    if (total === 0) return null;
    const now = Date.now();
    for (let i = 0; i < total; i++) {
      const idx = (this.accountIndex + i) % total;
      const acc = this.accounts[idx];
      if (!acc.unhealthyUntil || acc.unhealthyUntil < now) {
        if (i > 0) {
          this.accountIndex = idx;
          this.currentAccRequestsServed = 0;
        }
        return acc;
      }
    }
    return this.accounts[this.accountIndex % total] || null;
  }

  nextAccount(sessionId = null, isFailover = false, isSubagent = false, failedAccount = null) {
    if (isFailover && this.rotationPaused) {
      return this.getCurrentAccount();
    }

    const total = this.accounts.length || 1;
    if (isFailover) {
      const cur = this.getCurrentAccount();
      if (cur && (!cur.unhealthyUntil || cur.unhealthyUntil <= Date.now())) {
        if (!failedAccount || !isSameAccount(cur, failedAccount)) {
          this.currentAccRequestsServed = 1;
          if (this.currentAccRequestsServed >= this.requestsPerAccount) {
            this.accountIndex = (this.accountIndex + 1) % total;
            this.currentAccRequestsServed = 0;
          }
          this.saveRotatorStateDebounced();
          return cur;
        }
      }
    }
    this.accountIndex = (this.accountIndex + 1) % total;
    this.currentAccRequestsServed = 0;
    this.saveRotatorStateDebounced();
    return this.getCurrentAccount();
  }

  allocateAccountForRequest(reqUrl = "/", host = "", headers = {}, bodyBuffer = null) {
    if (this.allAccounts.length === 0 && this.accounts.length === 0) this.loadState();

    const sessionId = sessionAffinity.extractSessionId(headers, bodyBuffer);
    const isSub = sessionAffinity.isSubagent(reqUrl, host, headers, bodyBuffer, sessionId);
    const modelName = extractModelName(reqUrl, bodyBuffer);
    const pool = this.allAccounts.length > 0 ? this.allAccounts : this.accounts;

    const ruleMatch = allocateForModelRule(modelName, this.modelRules, pool, this.ruleCursors, this.requestsPerAccount);
    if (ruleMatch) {
      this.requestCount++;
      this.saveRotatorStateDebounced();
      return {
        account: ruleMatch.account,
        isSubagent: isSub,
        servedCount: ruleMatch.servedCount,
        requestsPerAccount: ruleMatch.requestsPerAccount,
        ruleStrategy: ruleMatch.ruleStrategy,
        ruleCursorKey: ruleMatch.ruleCursorKey,
        startIndex: ruleMatch.startIndex,
        requestNumber: this.requestCount,
        sessionId,
        isLocked: !ruleMatch.fallbackToGlobal && ruleMatch.rulePool.length <= 1,
        lockReason: "model_rule",
        modelName,
        matchedRule: ruleMatch.rule.name || ruleMatch.rule.pattern,
        matchedRuleName: ruleMatch.rule.name || ruleMatch.rule.pattern,
        rulePool: ruleMatch.rulePool,
        fallbackToGlobal: ruleMatch.fallbackToGlobal
      };
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
      account: current,
      isSubagent: isSub,
      servedCount: served,
      requestsPerAccount: this.requestsPerAccount,
      ruleStrategy: "",
      requestNumber: this.requestCount,
      sessionId,
      isLocked: Boolean(this.rotationPaused),
      lockReason: this.rotationPaused ? "pinned" : null,
      modelName,
      matchedRule: ""
    };
  }

  _buildPersistPayload() {
    const cur = this.getCurrentAccount();
    return {
      last_account_email: cur?.email || "",
      last_account_id: cur?.id || "",
      account_index: this.accountIndex,
      current_req_served: this.currentAccRequestsServed,
      total_requests: this.requestCount,
      rotation_paused: this.rotationPaused,
      pinned_account_email: this.pinnedAccountKey?.email || "",
      pinned_account_id: this.pinnedAccountKey?.id || "",
      rule_states: serializeRuleStates(this.ruleCursors, this.modelRules),
      updated_at: Date.now()
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
    return saveRotatorStateAsync(this.config.ROTATOR_STATE_FILE, this._buildPersistPayload());
  }

  saveRotatorState() {
    if (this._saveTimer) {
      clearTimeout(this._saveTimer);
      this._saveTimer = null;
    }
    if (!this.config?.ROTATOR_STATE_FILE) return;
    saveRotatorState(this.config.ROTATOR_STATE_FILE, this._buildPersistPayload());
  }

  restoreRotatorState() {
    if (!this.config?.ROTATOR_STATE_FILE) return;
    const state = restoreRotatorState(this.config.ROTATOR_STATE_FILE);
    if (!state) return;
    if (typeof state.total_requests === "number") this.requestCount = state.total_requests;
    if (typeof state.rotation_paused === "boolean") this.rotationPaused = state.rotation_paused;
    this.pinnedAccountKey = resolvePinnedKey(state);
    if (state.rule_states && typeof state.rule_states === "object") {
      this.ruleCursors = restoreRuleStates(state.rule_states);
    }

    if (this.accounts.length > 0) {
      const resolved = resolveRestoredAccount(this.accounts, state);
      this.accountIndex = resolved.accountIndex;
      this.currentAccRequestsServed = resolved.currentAccRequestsServed;
    }

    const pool = this.allAccounts.length > 0 ? this.allAccounts : this.accounts;
    if (this.rotationPaused && !this.pinnedAccountKey && pool.length > 0) {
      const cur = this.accounts[this.accountIndex] || pool[0];
      if (cur) this.pinnedAccountKey = { id: cur.id || "", email: cur.email || "" };
    }

    const restoredAcc = this.getCurrentAccount();
    if (restoredAcc) {
      console.log(`[ROTATOR-RESTORE] [OK] Khoi phuc tai khoan: [${restoredAcc.email}] (Paused=${this.rotationPaused})`);
    }
  }

  loadState() {
    try {
      const loaded = loadRotatorDiskState(this.config, this.allAccounts);
      if (!loaded) return;

      this.allAccounts = loaded.allTokenAccounts;
      this.accounts = loaded.activeAccounts;
      this.requestsPerAccount = loaded.requestsPerAccount;
      this.modelRules = loaded.modelRules;

      if (this.accounts.length > 0) {
        if (!this.isRestored) {
          this.restoreRotatorState();
          this.isRestored = true;
        } else {
          this.accountIndex = this.accountIndex % this.accounts.length;
        }
        agentPool.cleanupDeadAgents(this.allAccounts);
      } else if (!this.isRestored && this.allAccounts.length > 0) {
        this.restoreRotatorState();
        this.isRestored = true;
      }
      checkProactiveTokenRefresh(this.allAccounts, this.config).catch(() => {});
    } catch (err) {
      console.error("[STATE-LOAD-ERR] Loi nap accounts:", err.message);
    }
  }

  handleCommand(cmd, httpRes, writeLiveStatus, params = {}) {
    return handleRotatorCommand(this, cmd, httpRes, writeLiveStatus, params);
  }
}

module.exports = { AccountRotator };
