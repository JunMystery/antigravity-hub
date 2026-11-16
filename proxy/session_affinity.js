/**
 * Dual-Track Session Affinity & Subagent Round Robin Manager:
 * Track 1: Main Chat Session Affinity & Context Pinning.
 * Track 2: Subagent Round Robin Allocation (Moi Subagent moi bat buoc nhan 1 account moi).
 */

const SUBAGENT_IDLE_TIMEOUT_MS = 60 * 1000; // 60s idle timeout sau khi subagent xong viec
const MAIN_SESSION_TTL_MS = 30 * 60 * 1000; // 30m TTL cho main session

class SessionAffinityManager {
  constructor() {
    this.mainSessionId = null;
    this.mainSessionAccount = null;
    this.mainSessionLastActive = 0;
    this.subagentMap = new Map(); // sessionId -> { email: string, lastUsed: number, requestCount: number }
    this.subagentIndex = 0;
    this.subagentTotalRequests = 0;
    this.inFlightCount = 0;
  }

  extractSessionId(headers = {}, bodyBuffer = null) {
    const h = headers || {};
    // 1. Uu tien conversation/session ID co dinh
    const headerKey = h["conversation-id"] || h["x-conversation-id"] ||
                      h["session-id"] || h["x-session-id"];
    if (headerKey) return String(headerKey);

    // 2. Kiem tra JSON Payload (Antigravity luu conversationId trong metadata)
    if (bodyBuffer && bodyBuffer.length > 0) {
      try {
        const json = JSON.parse(bodyBuffer.toString("utf8"));
        if (json.conversationId) return String(json.conversationId);
        if (json.sessionId) return String(json.sessionId);
        if (json.metadata && typeof json.metadata === "object") {
          if (json.metadata.conversationId) return String(json.metadata.conversationId);
          if (json.metadata.sessionId) return String(json.metadata.sessionId);
        }
      } catch (_) {}
    }

    // Khong su dung x-client-request-id lam session ID vi moi HTTP request co mot request ID rieng biet
    return null;
  }

  isMainSessionActive() {
    return Boolean(
      this.mainSessionId &&
      this.mainSessionLastActive &&
      (Date.now() - this.mainSessionLastActive < MAIN_SESSION_TTL_MS)
    );
  }

  isSubagent(reqUrl, host = "", headers = {}, bodyBuffer = null, sessionId = null) {
    const h = headers || {};
    if (h["x-subagent-id"] || h["subagent-id"] || h["x-antigravity-subagent"]) {
      return true;
    }
    if (host.includes("companion") || (h["user-agent"] && h["user-agent"].includes("antigravity-subagent"))) {
      return true;
    }
    if (sessionId) {
      if (this.subagentMap.has(sessionId)) return true;
      if (this.mainSessionId && sessionId === this.mainSessionId) {
        this.mainSessionLastActive = Date.now();
        return false;
      }
      if (this.mainSessionId && sessionId !== this.mainSessionId) {
        if (this.mainSessionLastActive && (Date.now() - this.mainSessionLastActive < MAIN_SESSION_TTL_MS)) {
          return true;
        }
      }
    }
    return false;
  }

  setMainSession(sessionId, account) {
    if (sessionId) {
      this.mainSessionId = sessionId;
      this.mainSessionLastActive = Date.now();
    }
    if (account) this.mainSessionAccount = account;
  }

  allocateSubagentAccount(sessionId, accounts = []) {
    this.cleanupExpiredSubagents();
    if (!accounts || accounts.length === 0) return null;
    const now = Date.now();
    const total = accounts.length;

    // 1. Subagent hien tai con dang chay trong 1 task (< 60s idle) -> Giu nguyen Prompt Cache
    if (sessionId && this.subagentMap.has(sessionId)) {
      const entry = this.subagentMap.get(sessionId);
      if (now - entry.lastUsed <= SUBAGENT_IDLE_TIMEOUT_MS) {
        entry.lastUsed = now;
        entry.requestCount++;
        this.subagentTotalRequests++;
        const boundAcc = accounts.find((a) => (a.email || a.name || "").toLowerCase() === entry.email.toLowerCase());
        if (boundAcc) {
          return { account: boundAcc, isSticky: true, requestNumber: this.subagentTotalRequests, isNewSubagent: false };
        }
      }
    }

    // 2. Subagent MOI (hoac session idle > 60s) -> BAT BUOC Round Robin sang tai khoan tiep theo!
    const nextIdx = this.subagentMap.size === 0 ? this.subagentIndex : (this.subagentIndex + 1) % total;
    this.subagentIndex = nextIdx;

    let selectedAcc = accounts[this.subagentIndex];
    for (let i = 0; i < total; i++) {
      const candidate = accounts[(this.subagentIndex + i) % total];
      if (!candidate.unhealthyUntil || candidate.unhealthyUntil < now) {
        selectedAcc = candidate;
        this.subagentIndex = (this.subagentIndex + i) % total;
        break;
      }
    }

    this.subagentTotalRequests++;
    const email = (selectedAcc.email || selectedAcc.name || "").toLowerCase();
    if (sessionId) {
      this.subagentMap.set(sessionId, { email, lastUsed: now, requestCount: 1 });
    }

    return {
      account: selectedAcc,
      isSticky: false,
      requestNumber: this.subagentTotalRequests,
      isNewSubagent: true
    };
  }

  failoverSubagent(sessionId, accounts = []) {
    if (!accounts || accounts.length === 0) return null;
    const now = Date.now();
    const total = accounts.length;
    this.subagentIndex = (this.subagentIndex + 1) % total;
    const newAcc = accounts[this.subagentIndex];
    if (sessionId && newAcc) {
      this.subagentMap.set(sessionId, {
        email: (newAcc.email || newAcc.name || "").toLowerCase(),
        lastUsed: now,
        requestCount: 1
      });
    }
    return newAcc;
  }

  startRequest() { this.inFlightCount++; }
  endRequest() { this.inFlightCount = Math.max(0, this.inFlightCount - 1); }

  cleanupExpiredSubagents() {
    const now = Date.now();
    for (const [id, entry] of this.subagentMap.entries()) {
      if (now - entry.lastUsed > SUBAGENT_IDLE_TIMEOUT_MS) {
        this.subagentMap.delete(id);
      }
    }
  }
}

const sessionAffinity = new SessionAffinityManager();

module.exports = {
  SessionAffinityManager,
  sessionAffinity
};
