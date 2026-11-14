/**
 * Quan ly tinh ket dinh phien (Session Affinity) cho AI Chat va Subagents:
 * 1. Phat hien conversationId / sessionId tu Headers va Body Buffer.
 * 2. Sticky Session Mapping: Khoa co dinh tai khoan va Project ID theo Conversation.
 * 3. In-Flight & Burst Concurrency: Giu nguyen tai khoan khi subagents chay song song.
 */

const SESSION_TTL_MS = 15 * 60 * 1000; // 15 phut
const BURST_WINDOW_MS = 4000; // 4 giay burst window cho subagent concurrent calls

class SessionAffinityManager {
  constructor() {
    this.sessionMap = new Map(); // sessionId -> { email: string, lastUsed: number }
    this.inFlightCount = 0;
    this.lastActiveAccount = null;
    this.lastActiveTime = 0;
  }

  extractSessionId(headers = {}, bodyBuffer = null) {
    // 1. Kiem tra HTTP Headers
    const h = headers || {};
    const headerKey = h["conversation-id"] || h["x-conversation-id"] ||
                      h["session-id"] || h["x-session-id"] ||
                      h["x-client-request-id"] || h["client-request-id"];
    if (headerKey) return String(headerKey);

    // 2. Kiem tra JSON Payload
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
    return null;
  }

  getAffinityAccount(sessionId, accounts = []) {
    this.cleanupExpired();
    if (!sessionId) return null;

    const entry = this.sessionMap.get(sessionId);
    if (!entry) return null;

    entry.lastUsed = Date.now();
    const found = accounts.find((a) => (a.email || a.name || "").toLowerCase() === entry.email.toLowerCase());
    return found || null;
  }

  setAffinity(sessionId, account) {
    if (!sessionId || !account) return;
    const email = (account.email || account.name || "").toLowerCase();
    this.sessionMap.set(sessionId, { email, lastUsed: Date.now() });
  }

  clearAffinity(sessionId) {
    if (sessionId) this.sessionMap.delete(sessionId);
  }

  getBurstAccount(accounts = []) {
    const now = Date.now();
    const isBurst = this.inFlightCount > 0 || (now - this.lastActiveTime < BURST_WINDOW_MS);
    if (isBurst && this.lastActiveAccount) {
      const email = (this.lastActiveAccount.email || this.lastActiveAccount.name || "").toLowerCase();
      const found = accounts.find((a) => (a.email || a.name || "").toLowerCase() === email);
      if (found) return found;
    }
    return null;
  }

  startRequest(account) {
    this.inFlightCount++;
    this.lastActiveAccount = account;
    this.lastActiveTime = Date.now();
  }

  endRequest() {
    this.inFlightCount = Math.max(0, this.inFlightCount - 1);
    this.lastActiveTime = Date.now();
  }

  cleanupExpired() {
    const now = Date.now();
    for (const [id, entry] of this.sessionMap.entries()) {
      if (now - entry.lastUsed > SESSION_TTL_MS) {
        this.sessionMap.delete(id);
      }
    }
  }
}

const sessionAffinity = new SessionAffinityManager();

module.exports = {
  SessionAffinityManager,
  sessionAffinity
};
