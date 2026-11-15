const fs = require("node:fs");
const path = require("node:path");
const forge = require("node-forge");

/**
 * Tự động sinh chứng chỉ Root CA nội bộ (ca.crt, ca.key) nếu chưa tồn tại.
 */
function ensureRootCertificate(certsDir) {
  const caCrtPath = path.join(certsDir, "ca.crt");
  const caKeyPath = path.join(certsDir, "ca.key");

  if (fs.existsSync(caCrtPath) && fs.existsSync(caKeyPath)) {
    try {
      if (process.platform !== "win32") fs.chmodSync(caKeyPath, 0o600);
    } catch (_) {}
    return;
  }

  fs.mkdirSync(certsDir, { recursive: true });
  console.log("[MITM-INIT] Phat hien thieu Root CA. Dang tu dong sinh chung chi Root CA noi bo...");

  const keys = forge.pki.rsa.generateKeyPair(2048);
  const cert = forge.pki.createCertificate();
  cert.publicKey = keys.publicKey;
  cert.serialNumber = String(Date.now());
  cert.validity.notBefore = new Date(Date.now() - 24 * 3600 * 1000);
  cert.validity.notAfter = new Date(Date.now() + 10 * 365 * 24 * 3600 * 1000);

  const attrs = [
    { name: "commonName", value: "Antigravity Root CA" },
    { name: "organizationName", value: "Antigravity Launcher Proxy" },
    { name: "countryName", value: "VN" }
  ];
  cert.setSubject(attrs);
  cert.setIssuer(attrs);

  cert.setExtensions([
    { name: "basicConstraints", cA: true, critical: true },
    { name: "keyUsage", keyCertSign: true, cRLSign: true, critical: true }
  ]);

  cert.sign(keys.privateKey, forge.md.sha256.create());

  fs.writeFileSync(caKeyPath, forge.pki.privateKeyToPem(keys.privateKey), { encoding: "utf8", mode: 0o600 });
  fs.writeFileSync(caCrtPath, forge.pki.certificateToPem(cert), "utf8");
  console.log(`[MITM-INIT] [OK] Da sinh thanh cong Root CA tai: ${certsDir}`);
}

/**
 * Tạo chứng chỉ SSL Leaf cho *.googleapis.com được ký bởi Root CA nội bộ.
 * Phục vụ giải mã và định tuyến MITM an toàn cho Antigravity IDE.
 */
function createLeafCertificate(certsDir) {
  ensureRootCertificate(certsDir);
  const caCrtPath = path.join(certsDir, "ca.crt");
  const caKeyPath = path.join(certsDir, "ca.key");

  const caCertPem = fs.readFileSync(caCrtPath, "utf8");
  const caKeyPem = fs.readFileSync(caKeyPath, "utf8");
  const caCert = forge.pki.certificateFromPem(caCertPem);
  const caKey = forge.pki.privateKeyFromPem(caKeyPem);

  const keys = forge.pki.rsa.generateKeyPair(2048);
  const cert = forge.pki.createCertificate();
  cert.publicKey = keys.publicKey;
  cert.serialNumber = String(Date.now());
  cert.validity.notBefore = new Date(Date.now() - 24 * 3600 * 1000);
  cert.validity.notAfter = new Date(Date.now() + 365 * 24 * 3600 * 1000);

  const attrs = [
    { name: "commonName", value: "*.googleapis.com" },
    { name: "organizationName", value: "Antigravity Proxy" }
  ];
  cert.setSubject(attrs);
  cert.setIssuer(caCert.subject.attributes);

  cert.setExtensions([
    { name: "basicConstraints", cA: false },
    {
      name: "extKeyUsage",
      serverAuth: true
    },
    {
      name: "subjectAltName",
      altNames: [
        { type: 2, value: "*.googleapis.com" },
        { type: 2, value: "daily-cloudcode-pa.googleapis.com" },
        { type: 2, value: "cloudcode-pa.googleapis.com" },
        { type: 2, value: "generativelanguage.googleapis.com" },
        { type: 2, value: "localhost" },
        { type: 7, ip: "127.0.0.1" }
      ]
    }
  ]);

  cert.sign(caKey, forge.md.sha256.create());

  const leafCertPem = forge.pki.certificateToPem(cert);
  return {
    key: forge.pki.privateKeyToPem(keys.privateKey),
    cert: `${leafCertPem}\n${caCertPem}`,
    ca: caCertPem
  };
}

module.exports = {
  createLeafCertificate
};
