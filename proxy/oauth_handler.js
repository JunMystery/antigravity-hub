const {
  generatePkceChallenge,
  buildGoogleAuthUrl,
  exchangeAuthCode,
  fetchUserInfo,
  fetchProjectId,
  saveAuthorizedAccount
} = require("./oauth_flow");

const pendingSessions = new Map();

function cleanupExpiredSessions() {
  const now = Date.now();
  for (const [state, sess] of pendingSessions.entries()) {
    if (now - sess.createdAt > 10 * 60 * 1000) {
      pendingSessions.delete(state);
    }
  }
}
setInterval(cleanupExpiredSessions, 60 * 1000);

function renderHtml(title, message, isSuccess = true) {
  const color = isSuccess ? "#27ae60" : "#e74c3c";
  const icon = isSuccess ? "[OK]" : "[FAIL]";
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${title}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #0f172a; color: #f8fafc; text-align: center; }
    .card { background: #1e293b; padding: 40px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); max-width: 480px; border: 1px solid #334155; }
    h1 { font-size: 24px; color: ${color}; margin-top: 10px; }
    p { font-size: 15px; color: #94a3b8; line-height: 1.6; }
    .btn { display: inline-block; margin-top: 20px; padding: 10px 24px; background: #3b82f6; color: #fff; text-decoration: none; border-radius: 6px; font-weight: bold; }
  </style>
</head>
<body>
  <div class="card">
    <div style="font-size: 48px;">${icon}</div>
    <h1>${title}</h1>
    <p>${message}</p>
    <p style="font-size: 13px; color: #64748b;">Bạn có thể đóng tab này và quay lại Antigravity Launcher.</p>
  </div>
</body>
</html>`;
}

async function handleOAuthRoute(req, res, context) {
  try {
    const url = new URL(req.url, `http://${req.headers.host || "127.0.0.1"}`);

    if (url.pathname === "/_oauth/start") {
      const { codeVerifier, codeChallenge, state } = generatePkceChallenge();
      const redirectUri = `http://localhost:${context.proxyPort}/oauth/callback`;
      const authUrl = buildGoogleAuthUrl(context.config, codeChallenge, state, redirectUri);

      pendingSessions.set(state, { codeVerifier, redirectUri, createdAt: Date.now() });

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ success: true, authUrl, state, redirectUri }));
      return true;
    }

    if (url.pathname === "/oauth/callback") {
      const code = url.searchParams.get("code");
      const state = url.searchParams.get("state");
      const error = url.searchParams.get("error");

      if (error) {
        res.writeHead(400, { "Content-Type": "text/html; charset=utf-8" });
        res.end(renderHtml("Ủy quyền thất bại", `Google trả về lỗi: ${error}`, false));
        return true;
      }

      if (!code || !state || !pendingSessions.has(state)) {
        res.writeHead(400, { "Content-Type": "text/html; charset=utf-8" });
        res.end(renderHtml("Phiên hết hạn hoặc không hợp lệ", "Không tìm thấy phiên đăng nhập tương ứng. Vui lòng thử lại từ Launcher.", false));
        return true;
      }

      const session = pendingSessions.get(state);
      pendingSessions.delete(state);

      try {
        console.log("[OAUTH-FLOW] [TOKEN] Đang đổi mã Authorization Code lấy Tokens...");
        const tokens = await exchangeAuthCode(code, session.codeVerifier, session.redirectUri, context.config);

        console.log("[OAUTH-FLOW] [USER] Đang truy vấn User Info...");
        const userInfo = await fetchUserInfo(tokens.accessToken);

        console.log("[OAUTH-FLOW] [PROJECT] Đang kiểm tra Google Cloud Project ID...");
        const projectId = await fetchProjectId(tokens.accessToken);

        console.log(`[OAUTH-FLOW] [SAVE] Đang lưu tài khoản [${userInfo.email}]...`);
        const account = saveAuthorizedAccount(
          { ...tokens, ...userInfo, projectId },
          {
            accountsFile: context.config.ACCOUNTS_FILE,
            profilesFile: context.profilesFile,
            profilesBaseDir: context.profilesBaseDir
          }
        );

        context.loadState();
        context.writeLiveStatus({
          active: false,
          timestamp: Date.now(),
          account_email: account.email,
          account_name: account.name,
          current_req: 0,
          requests_per_account: context.requestsPerAccount,
          total_requests: context.requestCount,
          endpoint: "oauth_added",
          method: "LOGIN",
          status: "account_added"
        });

        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(renderHtml("Đăng nhập thành công!", `Tài khoản <b>${userInfo.email}</b> (${userInfo.name}) đã được liên kết thành công vào Antigravity Launcher & Micro-Proxy!`, true));
        return true;
      } catch (err) {
        console.error("[OAUTH-ERR] Lỗi hoàn tất OAuth:", err.message);
        res.writeHead(500, { "Content-Type": "text/html; charset=utf-8" });
        res.end(renderHtml("Lỗi xử lý tài khoản", err.message, false));
        return true;
      }
    }

    if (url.pathname === "/_oauth/manual" && req.method === "POST") {
      let body = "";
      req.on("data", (chunk) => { body += chunk; });
      req.on("end", async () => {
        try {
          const payload = JSON.parse(body || "{}");
          let code = payload.code;
          let state = payload.state;

          if (payload.callbackUrl) {
            const parsed = new URL(payload.callbackUrl);
            code = parsed.searchParams.get("code") || code;
            state = parsed.searchParams.get("state") || state;
          }

          const session = pendingSessions.get(state) || Array.from(pendingSessions.values())[0];
          if (!session || !code) {
            res.writeHead(400, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ success: false, error: "Mã code hoặc session không hợp lệ" }));
            return;
          }

          const tokens = await exchangeAuthCode(code, session.codeVerifier, session.redirectUri, context.config);
          const userInfo = await fetchUserInfo(tokens.accessToken);
          const projectId = await fetchProjectId(tokens.accessToken);

          const account = saveAuthorizedAccount(
            { ...tokens, ...userInfo, projectId },
            {
              accountsFile: context.config.ACCOUNTS_FILE,
              profilesFile: context.profilesFile,
              profilesBaseDir: context.profilesBaseDir
            }
          );

          context.loadState();
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ success: true, email: account.email, name: account.name }));
        } catch (err) {
          res.writeHead(500, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ success: false, error: err.message }));
        }
      });
      return true;
    }
  } catch (_) {}
  return false;
}

module.exports = {
  handleOAuthRoute
};
