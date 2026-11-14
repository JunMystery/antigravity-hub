const fs = require("node:fs");

/**
 * Chuyển đổi an toàn giá trị expiresAt thành Epoch timestamp (ms).
 * Khắc phục triệt để lỗi ISO String (e.g. "2026-11-13T...") trừ số ra NaN.
 */
function getExpiresAtEpoch(val) {
  if (!val) return 0;
  if (typeof val === "number") return val;
  const parsed = Date.parse(val);
  return Number.isNaN(parsed) ? 0 : parsed;
}

/**
 * Ghi đè Access Token và expiresAt mới vào file accounts.json
 */
function persistAccountToken(account, accountsFile) {
  if (!account || !account.accessToken || !accountsFile || !fs.existsSync(accountsFile)) {
    return;
  }
  try {
    const raw = JSON.parse(fs.readFileSync(accountsFile, "utf8"));
    let found = false;
    for (const a of raw.accounts || []) {
      const matchId = a.id && a.id === account.id;
      const matchEmail = a.email && a.email.toLowerCase() === (account.email || "").toLowerCase();
      if (matchId || matchEmail) {
        a.accessToken = account.accessToken;
        a.expiresAt = new Date(account.expiresAt).toISOString();
        found = true;
        break;
      }
    }
    if (found) {
      fs.writeFileSync(accountsFile, JSON.stringify(raw, null, 2), "utf8");
      console.log(`[AUTH-PERSIST] [SAVE] Đã lưu Access Token mới cho [${account.email}] vào accounts.json`);
    }
  } catch (err) {
    console.error(`[AUTH-PERSIST-ERR] Lỗi ghi accounts.json: ${err.message}`);
  }
}

/**
 * Tự động cấp mới Google OAuth Access Token bằng Refresh Token
 */
async function refreshGoogleAccessToken(account, config) {
  if (!account || !account.refreshToken) return null;
  try {
    const res = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: config.GOOGLE_CLIENT_ID,
        client_secret: config.GOOGLE_CLIENT_SECRET,
        grant_type: "refresh_token",
        refresh_token: account.refreshToken
      })
    });

    if (!res.ok) {
      const errText = await res.text();
      console.error(`[AUTH-ERR] Refresh token thất bại cho ${account.email}: HTTP ${res.status} - ${errText}`);
      return null;
    }

    const data = await res.json();
    account.accessToken = data.access_token;
    account.expiresAt = Date.now() + (data.expires_in || 3600) * 1000;
    console.log(`[AUTH-REFRESH] [OK] Đã tự động cấp mới Token từ Google cho: ${account.email}`);

    persistAccountToken(account, config.ACCOUNTS_FILE);
    return account;
  } catch (err) {
    console.error(`[AUTH-ERR] Lỗi gọi Google OAuth token: ${err.message}`);
    return null;
  }
}

/**
 * Kiểm tra và chủ động refresh tất cả token sắp hết hạn (< 15 phút)
 */
async function checkProactiveTokenRefresh(allAccounts, config) {
  const now = Date.now();
  for (const acc of allAccounts) {
    const expiresMs = getExpiresAtEpoch(acc.expiresAt);
    if (!acc.accessToken || expiresMs - now < 15 * 60 * 1000) {
      await refreshGoogleAccessToken(acc, config);
    }
  }
}

/**
 * Đảm bảo tài khoản có token hợp lệ trước khi gửi request (< 5 phút tự refresh)
 */
async function ensureValidToken(account, config) {
  if (!account) return null;
  const expiresMs = getExpiresAtEpoch(account.expiresAt);
  if (!account.accessToken || expiresMs - Date.now() < 5 * 60 * 1000) {
    await refreshGoogleAccessToken(account, config);
  }
  return account.accessToken;
}

module.exports = {
  getExpiresAtEpoch,
  persistAccountToken,
  refreshGoogleAccessToken,
  checkProactiveTokenRefresh,
  ensureValidToken
};
