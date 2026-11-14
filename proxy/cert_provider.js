const fs = require("node:fs");
const path = require("node:path");
const forge = require("node-forge");

/**
 * Tạo chứng chỉ SSL Leaf cho *.googleapis.com được ký bởi Root CA nội bộ.
 * Phục vụ giải mã và định tuyến MITM an toàn cho Antigravity IDE.
 */
function createLeafCertificate(certsDir) {
  const caCrtPath = path.join(certsDir, "ca.crt");
  const caKeyPath = path.join(certsDir, "ca.key");

  if (!fs.existsSync(caCrtPath) || !fs.existsSync(caKeyPath)) {
    throw new Error(`Không tìm thấy chứng chỉ Root CA tại: ${certsDir}`);
  }

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
      name: "subjectAltName",
      altNames: [
        { type: 2, value: "*.googleapis.com" },
        { type: 2, value: "daily-cloudcode-pa.googleapis.com" },
        { type: 2, value: "cloudcode-pa.googleapis.com" }
      ]
    }
  ]);

  cert.sign(caKey, forge.md.sha256.create());

  return {
    key: forge.pki.privateKeyToPem(keys.privateKey),
    cert: forge.pki.certificateToPem(cert)
  };
}

module.exports = {
  createLeafCertificate
};
