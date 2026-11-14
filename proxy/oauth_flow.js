const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { encryptToken } = require("./crypto_helper");

const SCOPES = [
  "https://www.googleapis.com/auth/cloud-platform",
  "https://www.googleapis.com/auth/userinfo.email",
  "https://www.googleapis.com/auth/userinfo.profile",
  "https://www.googleapis.com/auth/cclog",
  "https://www.googleapis.com/auth/experimentsandconfigs",
  "openid"
];

function generatePkceChallenge() {
  const codeVerifier = crypto.randomBytes(32).toString("base64url");
  const codeChallenge = crypto.createHash("sha256").update(codeVerifier).digest("base64url");
  const state = crypto.randomBytes(16).toString("base64url");
  return { codeVerifier, codeChallenge, state };
}

function buildGoogleAuthUrl(config, codeChallenge, state, redirectUri) {
  const params = new URLSearchParams({
    client_id: config.GOOGLE_CLIENT_ID,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: SCOPES.join(" "),
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
    state,
    access_type: "offline",
    prompt: "consent"
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
}

async function exchangeAuthCode(code, codeVerifier, redirectUri, config) {
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: config.GOOGLE_CLIENT_ID,
      client_secret: config.GOOGLE_CLIENT_SECRET,
      code,
      grant_type: "authorization_code",
      redirect_uri: redirectUri,
      code_verifier: codeVerifier
    })
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Đổi mã OAuth thất bại: HTTP ${res.status} - ${errText}`);
  }
  const data = await res.json();
  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    expiresIn: data.expires_in || 3600,
    expiresAt: Date.now() + (data.expires_in || 3600) * 1000,
    scope: data.scope,
    idToken: data.id_token
  };
}

async function fetchUserInfo(accessToken) {
  const res = await fetch("https://www.googleapis.com/oauth2/v1/userinfo", {
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  if (!res.ok) throw new Error(`Lấy userinfo thất bại: HTTP ${res.status}`);
  const data = await res.json();
  return { email: data.email, name: data.name || data.email, picture: data.picture || "" };
}

async function fetchProjectId(accessToken) {
  try {
    const res = await fetch("https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
        "User-Agent": "antigravity/hub/2.24.0 linux/x64"
      },
      body: JSON.stringify({ metadata: { ideType: 9, platform: 3, pluginType: 2 } })
    });
    if (res.ok) {
      const data = await res.json();
      return data.cloudaicompanionProject || data.projectId || "aicode-consumers";
    }
  } catch (_) {}
  return "aicode-consumers";
}

function saveAuthorizedAccount(accountData, { accountsFile, profilesFile, profilesBaseDir }) {
  const accRaw = fs.existsSync(accountsFile) ? JSON.parse(fs.readFileSync(accountsFile, "utf8")) : { accounts: [] };
  const accounts = accRaw.accounts || [];
  const existing = accounts.find((a) => (a.email || "").toLowerCase() === accountData.email.toLowerCase());
  const accId = existing?.id || crypto.randomUUID();
  const newAcc = {
    id: accId,
    email: accountData.email,
    name: accountData.name || accountData.email,
    accessToken: encryptToken(accountData.accessToken),
    refreshToken: encryptToken(accountData.refreshToken),
    expiresAt: new Date(accountData.expiresAt).toISOString(),
    projectId: accountData.projectId || "aicode-consumers"
  };
  if (existing) Object.assign(existing, newAcc);
  else accounts.push(newAcc);
  accRaw.accounts = accounts;
  fs.writeFileSync(accountsFile, JSON.stringify(accRaw, null, 2), { encoding: "utf8", mode: 0o600 });

  const profRaw = fs.existsSync(profilesFile) ? JSON.parse(fs.readFileSync(profilesFile, "utf8")) : { profiles: [] };
  const profiles = profRaw.profiles || [];
  const profMatch = profiles.find((p) => (p.email || p.name || "").toLowerCase() === accountData.email.toLowerCase());

  if (profMatch) {
    profMatch.email = accountData.email;
    profMatch.name = accountData.email;
    profMatch.enabled = true;
    profRaw.profiles = profiles;
    fs.writeFileSync(profilesFile, JSON.stringify(profRaw, null, 2), "utf8");
    return newAcc;
  }

  // Chuẩn hóa tên thư mục thành user_domain_com (loại bỏ @ và dấu chấm)
  const safeSlug = accountData.email.toLowerCase().replace(/[@.]/g, "_").replace(/[^a-z0-9_]/g, "");
  const dataDir = path.join(profilesBaseDir, safeSlug);
  fs.mkdirSync(dataDir, { recursive: true });

  profiles.push({
    id: safeSlug,
    name: accountData.email,
    email: accountData.email,
    order: profiles.length + 1,
    enabled: true,
    data_dir: dataDir,
    created_at: new Date().toISOString().replace("T", " ").slice(0, 16),
    quota_5h_val: 0,
    quota_5h: "--",
    quota_5h_valid: false,
    quota_weekly_val: 0,
    quota_weekly: "--",
    quota_weekly_valid: false,
    quota_timestamp: 0
  });
  profRaw.profiles = profiles;
  fs.writeFileSync(profilesFile, JSON.stringify(profRaw, null, 2), "utf8");
  return newAcc;
}

module.exports = {
  generatePkceChallenge,
  buildGoogleAuthUrl,
  exchangeAuthCode,
  fetchUserInfo,
  fetchProjectId,
  saveAuthorizedAccount
};
