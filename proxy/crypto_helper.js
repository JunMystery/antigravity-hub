const fs = require("node:fs");
const crypto = require("node:crypto");

const TOKEN_SALT = "Antigravity-Token-Salt-v1";
const ENVELOPE_PREFIX = "enc:v1:";

function getMachineFingerprint() {
  if (process.env.ANTIGRAVITY_MASTER_KEY) {
    return process.env.ANTIGRAVITY_MASTER_KEY.trim();
  }
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
  return crypto.createHash("sha256").update(`${fp}:${TOKEN_SALT}`).digest();
}

function encryptToken(plainText) {
  if (!plainText || typeof plainText !== "string") return "";
  if (plainText.startsWith(ENVELOPE_PREFIX)) return plainText;

  try {
    const key = getCryptoKey();
    const iv = crypto.randomBytes(12);
    const cipher = crypto.createCipheriv("aes-256-gcm", key, iv);
    const ct = Buffer.concat([cipher.update(plainText, "utf8"), cipher.final()]);
    const tag = cipher.getAuthTag();

    const ivB64 = iv.toString("base64");
    const ctB64 = ct.toString("base64");
    const tagB64 = tag.toString("base64");
    return `${ENVELOPE_PREFIX}${ivB64}:${ctB64}:${tagB64}`;
  } catch (_) {
    return plainText;
  }
}

function decryptToken(cipherText) {
  if (!cipherText || typeof cipherText !== "string") return "";
  if (!cipherText.startsWith(ENVELOPE_PREFIX)) return cipherText;

  try {
    const parts = cipherText.split(":");
    if (parts.length !== 5) return cipherText;
    const [, , ivB64, ctB64, tagB64] = parts;
    const iv = Buffer.from(ivB64, "base64");
    const ct = Buffer.from(ctB64, "base64");
    const tag = Buffer.from(tagB64, "base64");

    const key = getCryptoKey();
    const decipher = crypto.createDecipheriv("aes-256-gcm", key, iv);
    decipher.setAuthTag(tag);
    const dec = Buffer.concat([decipher.update(ct), decipher.final()]);
    return dec.toString("utf8");
  } catch (_) {
    return cipherText;
  }
}

function encryptAccountTokens(acc) {
  if (!acc || typeof acc !== "object") return acc;
  const cloned = { ...acc };
  if (cloned.accessToken) cloned.accessToken = encryptToken(cloned.accessToken);
  if (cloned.refreshToken) cloned.refreshToken = encryptToken(cloned.refreshToken);
  return cloned;
}

function decryptAccountTokens(acc) {
  if (!acc || typeof acc !== "object") return acc;
  const cloned = { ...acc };
  if (cloned.accessToken) cloned.accessToken = decryptToken(cloned.accessToken);
  if (cloned.refreshToken) cloned.refreshToken = decryptToken(cloned.refreshToken);
  return cloned;
}

module.exports = {
  getMachineFingerprint,
  getCryptoKey,
  encryptToken,
  decryptToken,
  encryptAccountTokens,
  decryptAccountTokens
};
