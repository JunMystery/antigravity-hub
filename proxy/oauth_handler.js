const fs = require("node:fs");
const {
  generatePkceChallenge,
  buildGoogleAuthUrl,
  exchangeAuthCode,
  fetchUserInfo,
  fetchProjectId,
  saveAuthorizedAccount
} = require("./oauth_flow");

const pendingSessions = new Map();

const OAUTH_I18N = {
  vi: {
    successTitle: "Đăng nhập thành công!",
    successMsg: (email, name) => `Tài khoản <b>${email}</b> (${name}) đã được liên kết thành công vào Antigravity Hub.`,
    successHint: "Tab này sẽ tự động đóng ngay lập tức. Nếu trình duyệt không tự đóng, vui lòng nhấn nút bên dưới.",
    fallbackHint: "Tài khoản đã được liên kết. Bạn có thể đóng tab này an toàn (Ctrl+W).",
    authFailedTitle: "Ủy quyền thất bại",
    authFailedMsg: (err) => `Google trả về lỗi: ${err}`,
    expiredTitle: "Phiên hết hạn hoặc không hợp lệ",
    expiredMsg: "Không tìm thấy phiên đăng nhập tương ứng. Vui lòng thử lại từ Launcher.",
    processErrTitle: "Lỗi xử lý tài khoản",
    errorHint: "Bạn có thể đóng tab này và thử lại từ Antigravity Hub.",
    closeBtn: "Đóng tab"
  },
  en: {
    successTitle: "Login Successful!",
    successMsg: (email, name) => `Account <b>${email}</b> (${name}) has been successfully linked to Antigravity Hub.`,
    successHint: "This tab will close automatically. If your browser blocks auto-close, click the button below.",
    fallbackHint: "Your account is linked. You can safely close this tab (Ctrl+W).",
    authFailedTitle: "Authorization Failed",
    authFailedMsg: (err) => `Google returned an error: ${err}`,
    expiredTitle: "Session Expired or Invalid",
    expiredMsg: "No matching login session was found. Please try again from the Launcher.",
    processErrTitle: "Account Processing Error",
    errorHint: "You can close this tab and try again from Antigravity Hub.",
    closeBtn: "Close Tab"
  }
};

function resolveLang(preferredLang, profilesFile) {
  let lang = preferredLang;
  if (!lang && profilesFile && fs.existsSync(profilesFile)) {
    try {
      const parsed = JSON.parse(fs.readFileSync(profilesFile, "utf8"));
      lang = parsed?.settings?.language;
    } catch (_) {}
  }
  const normalized = String(lang || "vi").toLowerCase();
  return normalized.startsWith("en") ? "en" : "vi";
}

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function cleanupExpiredSessions() {
  const now = Date.now();
  for (const [state, sess] of pendingSessions.entries()) {
    if (now - sess.createdAt > 10 * 60 * 1000) {
      pendingSessions.delete(state);
    }
  }
}
setInterval(cleanupExpiredSessions, 60 * 1000).unref();

function renderHtml(title, message, isSuccess = true, lang = "vi") {
  const copy = OAUTH_I18N[lang === "en" ? "en" : "vi"];
  const accent = isSuccess ? "#a6e3a1" : "#f38ba8";
  const ringBg = isSuccess ? "rgba(166, 227, 161, 0.14)" : "rgba(243, 139, 168, 0.14)";
  const iconSvg = isSuccess
    ? `<svg width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="${accent}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`
    : `<svg width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="${accent}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
  const pageTitle = isSuccess ? `Antigravity Hub - ${title}` : title;
  const hint = isSuccess ? copy.successHint : copy.errorHint;
  const fallbackHintJson = JSON.stringify(copy.fallbackHint);
  const autoCloseScript = isSuccess
    ? `<script>
    function closeTab() {
      try { window.close(); window.open('', '_self', ''); window.close(); } catch (_) {}
    }
    closeTab();
    window.addEventListener('DOMContentLoaded', () => {
      closeTab();
      setTimeout(closeTab, 120);
      setTimeout(() => {
        if (!window.closed) {
          const hintEl = document.getElementById('oauth-hint');
          const btnEl = document.getElementById('btn-close-tab');
          if (hintEl) hintEl.textContent = ${fallbackHintJson};
          if (btnEl) btnEl.style.display = 'none';
        }
      }, 1200);
    });
    window.addEventListener('load', () => { closeTab(); setTimeout(closeTab, 250); });
  </script>`
    : `<script>
    function closeTab() { try { window.close(); window.open('', '_self', ''); window.close(); } catch (_) {} }
  </script>`;

  return `<!DOCTYPE html>
<html lang="${lang === "en" ? "en" : "vi"}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(pageTitle)}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #1e1e2e; color: #cdd6f4; text-align: center; }
    .card { background: #24273a; padding: 40px 36px; border-radius: 14px; box-shadow: 0 12px 32px rgba(0,0,0,0.45); max-width: 460px; width: calc(100% - 32px); border: 1px solid #363a4f; }
    .icon-wrap { width: 104px; height: 104px; margin: 0 auto 20px; border-radius: 50%; background: ${ringBg}; display: flex; align-items: center; justify-content: center; }
    h1 { font-size: 24px; color: ${accent}; margin: 0 0 12px; }
    p { font-size: 15px; color: #bac2de; line-height: 1.6; margin: 0 0 12px; }
    .hint { font-size: 13px; color: #7f849c; margin-top: 8px; }
    .btn { margin-top: 18px; padding: 10px 24px; background: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
    .btn:hover { background: #45475a; }
  </style>
  ${autoCloseScript}
</head>
<body>
  <div class="card">
    <div class="icon-wrap">${iconSvg}</div>
    <h1>${escapeHtml(title)}</h1>
    <p>${message}</p>
    <p id="oauth-hint" class="hint">${escapeHtml(hint)}</p>
    <button id="btn-close-tab" type="button" class="btn" onclick="closeTab()">${escapeHtml(copy.closeBtn)}</button>
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
      const lang = resolveLang(url.searchParams.get("lang"), context.profilesFile);

      pendingSessions.set(state, { codeVerifier, redirectUri, lang, createdAt: Date.now() });

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ success: true, authUrl, state, redirectUri, lang }));
      return true;
    }

    if (url.pathname === "/oauth/callback") {
      const code = url.searchParams.get("code");
      const state = url.searchParams.get("state");
      const error = url.searchParams.get("error");
      const session = state ? pendingSessions.get(state) : null;
      const lang = resolveLang(session?.lang, context.profilesFile);
      const copy = OAUTH_I18N[lang];

      if (error) {
        res.writeHead(400, { "Content-Type": "text/html; charset=utf-8" });
        res.end(renderHtml(copy.authFailedTitle, copy.authFailedMsg(escapeHtml(error)), false, lang));
        return true;
      }

      if (!code || !state || !session) {
        res.writeHead(400, { "Content-Type": "text/html; charset=utf-8" });
        res.end(renderHtml(copy.expiredTitle, copy.expiredMsg, false, lang));
        return true;
      }

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
        res.end(renderHtml(
          copy.successTitle,
          copy.successMsg(escapeHtml(userInfo.email), escapeHtml(userInfo.name)),
          true,
          lang
        ));
        return true;
      } catch (err) {
        console.error("[OAUTH-ERR] Lỗi hoàn tất OAuth:", err.message);
        res.writeHead(500, { "Content-Type": "text/html; charset=utf-8" });
        res.end(renderHtml(copy.processErrTitle, escapeHtml(err.message), false, lang));
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
            res.end(JSON.stringify({ success: false, error: "Invalid code or session" }));
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
  handleOAuthRoute,
  renderHtml,
  resolveLang
};
