# -*- coding: utf-8 -*-
"""Unit tests for launcher_cert module and certificate verification."""

import os
import sys
import unittest
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "launcher"))

from launcher_cert import (
    ensure_certificates, ensure_combined_ca_bundle,
    is_root_ca_installed, COMBINED_CA_BUNDLE, ROOT_CA
)


class TestLauncherCert(unittest.TestCase):
    def test_ensure_certificates(self):
        ok = ensure_certificates()
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(ROOT_CA))

    def test_ensure_combined_ca_bundle(self):
        bundle_path = ensure_combined_ca_bundle()
        self.assertTrue(os.path.exists(bundle_path))
        self.assertEqual(bundle_path, COMBINED_CA_BUNDLE)
        # Verify size > 100KB (includes Mozilla roots + Root CA)
        self.assertGreater(os.path.getsize(bundle_path), 100000)

        with open(bundle_path, "rb") as f:
            content = f.read()
        self.assertIn(b"Antigravity Local Root CA", content)

    def test_is_root_ca_installed_does_not_crash(self):
        # Should return boolean safely
        res = is_root_ca_installed()
        self.assertIsInstance(res, bool)

    def test_leaf_cert_altnames(self):
        # Run node to verify leaf certificate has oauth2.googleapis.com
        node_script = """
        const forge = require('./proxy/node_modules/node-forge');
        const { createLeafCertificate } = require('./proxy/cert_provider');
        const path = require('path');
        const creds = createLeafCertificate(path.join(__dirname, 'proxy', 'certs'));
        if (!creds || !creds.cert) process.exit(1);
        const c = forge.pki.certificateFromPem(creds.cert.split('-----END CERTIFICATE-----')[0] + '-----END CERTIFICATE-----');
        const san = c.getExtension('subjectAltName');
        const names = san.altNames.map(a => a.value);
        if (!names.includes('oauth2.googleapis.com')) process.exit(2);
        console.log('Leaf OK');
        process.exit(0);
        """
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        res = subprocess.run(["node", "-e", node_script], cwd=repo_root, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Leaf OK", res.stdout)


if __name__ == "__main__":
    unittest.main()
