/**
 * Centralized socket and stream cleanup helpers for Antigravity Proxy.
 * Provides symmetrical destruction for HTTP streams, TCP tunnels, and client disconnects.
 */

function destroyStream(stream) {
  if (!stream || stream.destroyed) return;
  try {
    if (typeof stream.unpipe === "function") stream.unpipe();
  } catch (_) {}
  try {
    stream.destroy();
  } catch (_) {}
}

function attachClientCloseHandler({ clientRes, gReq, getActiveGRes, safeEndSession, onAbort, accName }) {
  if (!clientRes) return;
  clientRes.on("close", () => {
    if (!clientRes.writableEnded) {
      if (typeof onAbort === "function") onAbort();
      console.log(`[CLIENT-ABORT] Client IDE da dong ket noi som. Huy socket upstream cho [${accName || "UNKNOWN"}]`);
      if (typeof getActiveGRes === "function") {
        destroyStream(getActiveGRes());
      }
      if (gReq && !gReq.destroyed) {
        destroyStream(gReq);
      }
      if (typeof safeEndSession === "function") {
        safeEndSession();
      }
    }
  });
}

function attachConnectTunnelCleanup(clientSocket, serverSocket) {
  let isCleaned = false;
  function cleanup() {
    if (isCleaned) return;
    isCleaned = true;
    if (clientSocket && !clientSocket.destroyed) clientSocket.destroy();
    if (serverSocket && !serverSocket.destroyed) serverSocket.destroy();
  }

  clientSocket.on("close", cleanup);
  clientSocket.on("end", cleanup);
  clientSocket.on("error", () => cleanup());

  serverSocket.on("close", cleanup);
  serverSocket.on("end", cleanup);
  serverSocket.on("error", () => {
    if (clientSocket && !clientSocket.destroyed && clientSocket.writable) {
      try {
        clientSocket.write("HTTP/1.1 502 Bad Gateway\r\n\r\n");
      } catch (_) {}
    }
    cleanup();
  });
}

function handleClientError(err, socket) {
  if (!socket) return;
  if (err && (err.code === "ECONNRESET" || !socket.writable)) {
    socket.destroy(err);
    return;
  }
  try {
    socket.end("HTTP/1.1 400 Bad Request\r\n\r\n");
  } catch (_) {
    socket.destroy();
  }
}

module.exports = {
  destroyStream,
  attachClientCloseHandler,
  attachConnectTunnelCleanup,
  handleClientError
};
