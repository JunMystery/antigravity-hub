const https = require("node:https");

/**
 * Quan ly danh sach HTTPS Agent doc lap cho tung tai khoan Google.
 * Giup giu toc do Keep-Alive cao ma khong gay lan lon socket/session giua cac tai khoan.
 */
class AgentPool {
  constructor() {
    this.agents = new Map();
  }

  getAccountKey(account) {
    if (!account) return "default";
    if (account.id) return String(account.id);
    if (account.email) return account.email.toLowerCase();
    return "default";
  }

  getAgentForAccount(account) {
    const key = this.getAccountKey(account);
    if (!this.agents.has(key)) {
      const agent = new https.Agent({
        keepAlive: true,
        keepAliveMsecs: 15000,
        maxSockets: 20,
        timeout: 35000
      });
      this.agents.set(key, agent);
    }
    return this.agents.get(key);
  }

  destroyAgentForAccount(account) {
    const key = this.getAccountKey(account);
    if (this.agents.has(key)) {
      const agent = this.agents.get(key);
      agent.destroy();
      this.agents.delete(key);
    }
  }

  cleanupDeadAgents(activeAccounts = []) {
    const activeKeys = new Set(activeAccounts.map((a) => this.getAccountKey(a)));
    activeKeys.add("default");
    for (const [key, agent] of this.agents.entries()) {
      if (!activeKeys.has(key)) {
        agent.destroy();
        this.agents.delete(key);
      }
    }
  }

  clearAllAgents() {
    for (const agent of this.agents.values()) {
      agent.destroy();
    }
    this.agents.clear();
  }
}

const globalAgentPool = new AgentPool();

module.exports = {
  AgentPool,
  agentPool: globalAgentPool,
  getAgentForAccount: (account) => globalAgentPool.getAgentForAccount(account)
};
