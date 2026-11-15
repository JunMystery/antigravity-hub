const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const crypto = require("node:crypto");

const SALT_V1 = "Antigravity-Token-Salt-v1";
const SALT_V2 = "Antigravity-Token-Salt-v2";
const PREFIX_V1 = "enc:v1:";
const PREFIX_V2 = "enc:v2:";

let _cachedKeyV2 = null;
let _cachedEnvKey = null;

function getConfigDir() {
  if (process.platform === "win32" && process.env.APPDATA) {
    return path.join(process.env.APPDATA, "antigravity-launcher");
  }
  return path.join(os.homedir(), ".config", "antigravity-launcher");
}

function getMachineFingerprint() {
  let mid = "";
  for (const p of ["/etc/machine-id", "/var/lib/dbus/machine-id"]) {
    if (fs.existsSync(p)) {
      try {
        mid = fs.readFileSync(p, "utf8").trim();
        if (mid) break;
      } catch (_) {}
    }
  }
  const user = process.env.USER || process.env.USERNAME || "user";
  const computer = process.env.COMPUTERNAME || process.env.HOSTNAME || "host";
  if (!mid) mid = `${computer}_${user}`;
  return `${mid}:${user}`;
}

function getCryptoKey() {
  const fp = getMachineFingerprint();
  return crypto.createHash("sha256").update(`${fp}:${SALT_V1}`).digest();
}

function getCryptoKeyV2() {
  const envKey = (process.env.ANTIGRAVITY_MASTER_KEY || "").trim();
  if (_cachedKeyV2 && _cachedEnvKey === envKey) {
    return _cachedKeyV2;
  }

  let resolved = null;
  if (envKey.length === 64 && /^[0-9a-fA-F]{64}$/.test(envKey)) {
    resolved = Buffer.from(envKey, "hex");
  }

  if (!resolved) {
    const keyFile = path.join(getConfigDir(), ".master_key");
    if (fs.existsSync(keyFile)) {
      try {
        const fileHex = fs.readFileSync(keyFile, "utf8").trim();
        if (fileHex.length === 64 && /^[0-9a-fA-F]{64}$/.test(fileHex)) {
          resolved = Buffer.from(fileHex, "hex");
        }
      } catch (_) {}
    }
  }

  if (!resolved) {
    const fp = getMachineFingerprint();
    resolved = crypto.pbkdf2Sync(fp, Buffer.from(SALT_V2), 100000, 32, "sha256");
  }

  _cachedEnvKey = envKey;
  _cachedKeyV2 = resolved;
  return resolved;
}

function _resetKeyCache() {
  _cachedKeyV2 = null;
  _cachedEnvKey = null;
}

function encryptToken(plainText, accountName = null) {
  if (!plainText || typeof plainText !== "string") return "";
  if (plainText.startsWith(PREFIX_V2)) return plainText;
  if (plainText.startsWith(PREFIX_V1)) {
    const dec = decryptToken(plainText, accountName);
    if (dec === plainText) return plainText;
    plainText = dec;
  }

  try {
    const key = getCryptoKeyV2();
    const iv = crypto.randomBytes(12);
    const cipher = crypto.createCipheriv("aes-256-gcm", key, iv);
    const ct = Buffer.concat([cipher.update(plainText, "utf8"), cipher.final()]);
    const tag = cipher.getAuthTag();

    const ivB64 = iv.toString("base64");
    const ctB64 = ct.toString("base64");
    const tagB64 = tag.toString("base64");
    return `${PREFIX_V2}${ivB64}:${ctB64}:${tagB64}`;
  } catch (_) {
    return plainText;
  }
}

function decryptToken(cipherText, accountName = null) {
  if (!cipherText || typeof cipherText !== "string") return "";
  if (!cipherText.startsWith("enc:")) return cipherText;

  try {
    const parts = cipherText.split(":");
    if (parts.length !== 5) return cipherText;
    const [, version, ivB64, ctB64, tagB64] = parts;
    const iv = Buffer.from(ivB64, "base64");
    const ct = Buffer.from(ctB64, "base64");
    const tag = Buffer.from(tagB64, "base64");

    const primaryKey = version === "v2" ? getCryptoKeyV2() : getCryptoKey();
    const secondaryKey = version === "v2" ? getCryptoKey() : getCryptoKeyV2();

    for (const key of [primaryKey, secondaryKey]) {
      if (!key) continue;
      try {
        const decipher = crypto.createDecipheriv("aes-256-gcm", key, iv);
        decipher.setAuthTag(tag);
        const dec = Buffer.concat([decipher.update(ct), decipher.final()]);
        return dec.toString("utf8");
      } catch (_) {
        continue;
      }
    }
    return cipherText;
  } catch (_) {
    return cipherText;
  }
}

function encryptAccountTokens(acc) {
  if (!acc || typeof acc !== "object") return acc;
  const cloned = { ...acc };
  const accName = cloned.email || cloned.name || null;
  if (cloned.accessToken) cloned.accessToken = encryptToken(cloned.accessToken, accName);
  if (cloned.refreshToken) cloned.refreshToken = encryptToken(cloned.refreshToken, accName);
  return cloned;
}

function decryptAccountTokens(acc) {
  if (!acc || typeof acc !== "object") return acc;
  const cloned = { ...acc };
  const accName = cloned.email || cloned.name || null;
  if (cloned.accessToken) cloned.accessToken = decryptToken(cloned.accessToken, accName);
  if (cloned.refreshToken) cloned.refreshToken = decryptToken(cloned.refreshToken, accName);
  return cloned;
}

module.exports = {
  getMachineFingerprint,
  getCryptoKey,
  getCryptoKeyV2,
  _resetKeyCache,
  encryptToken,
  decryptToken,
  encryptAccountTokens,
  decryptAccountTokens
};
