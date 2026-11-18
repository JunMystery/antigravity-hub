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
    const IDLE_FREE_SOCKET_MS = 8000;
    const key = this.getAccountKey(account);
    if (!this.agents.has(key)) {
      const agent = new https.Agent({
        keepAlive: true,
        keepAliveMsecs: 3000,
        maxFreeSockets: 1,
        maxSockets: 15,
        scheduling: "lifo",
        timeout: 120000
      });
      // Huy socket free roi >8s de tranh tai su dung ket noi ban-mo bi Google Frontend dong ngam
      const origKeepAlive = agent.keepSocketAlive.bind(agent);
      agent.keepSocketAlive = (socket) => {
        const kept = origKeepAlive(socket);
        if (kept) {
          const onIdle = () => socket.destroy();
          socket._idleKill = onIdle;
          socket.setTimeout(IDLE_FREE_SOCKET_MS, onIdle);
        }
        return kept;
      };
      const origReuse = agent.reuseSocket.bind(agent);
      agent.reuseSocket = (socket, req) => {
        if (socket._idleKill) {
          socket.removeListener("timeout", socket._idleKill);
          socket._idleKill = null;
        }
        socket.setTimeout(120000);
        return origReuse(socket, req);
      };
      this.agents.set(key, agent);
    }
    return this.agents.get(key);
  }

  evictIdleSockets(account) {
    const key = this.getAccountKey(account);
    const agent = this.agents.get(key);
    if (agent && agent.freeSockets) {
      for (const name in agent.freeSockets) {
        const sockets = agent.freeSockets[name] || [];
        while (sockets.length > 0) {
          const sock = sockets.shift();
          if (sock && !sock.destroyed) sock.destroy();
        }
      }
    }
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
