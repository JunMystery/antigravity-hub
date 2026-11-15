# -*- coding: utf-8 -*-
"""Comprehensive unit and integration tests for SEC-02 Keyring and Crypto Hardening."""

import os
import sys
import shutil
import tempfile
import unittest
import subprocess
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "launcher"))

from launcher_keyring import (
    is_keyring_available, get_keyring_master_key,
    set_keyring_master_key, delete_keyring_master_key
)
from launcher_crypto import (
    resolve_master_key, reset_master_key_cache,
    encrypt_token, decrypt_token,
    encrypt_account_tokens, decrypt_account_tokens,
    get_legacy_crypto_key, get_machine_fingerprint,
    ENVELOPE_V1_PREFIX, ENVELOPE_V2_PREFIX
)
from launcher_storage import load_accounts


class TestKeyringModule(unittest.TestCase):
    """Test safe probing, CRUD, and exception safety in launcher_keyring."""

    def test_keyring_crud_mocked(self):
        backend_mock = MagicMock()
        backend_mock.priority = 10
        backend_mock.__class__.__module__ = "keyring.backends.SecretService"
        passwords = {}

        def mock_set(svc, usr, pwd): passwords[(svc, usr)] = pwd
        def mock_get(svc, usr): return passwords.get((svc, usr))
        def mock_del(svc, usr):
            if (svc, usr) in passwords: del passwords[(svc, usr)]
            else: raise Exception("Password not found")

        with patch.dict("sys.modules", {"keyring": MagicMock(
            get_keyring=MagicMock(return_value=backend_mock),
            get_password=mock_get,
            set_password=mock_set,
            delete_password=mock_del,
            errors=MagicMock(PasswordDeleteError=Exception)
        )}):
            self.assertTrue(is_keyring_available())
            test_key = "a" * 64
            self.assertTrue(set_keyring_master_key(test_key))
            self.assertEqual(get_keyring_master_key(), test_key)
            self.assertFalse(set_keyring_master_key("invalid-key"))
            self.assertTrue(delete_keyring_master_key())
            self.assertIsNone(get_keyring_master_key())
            self.assertTrue(delete_keyring_master_key())  # Idempotent delete

    def test_keyring_unavailable_backends(self):
        with patch.dict("sys.modules", {"keyring": None}):
            self.assertFalse(is_keyring_available())
            self.assertIsNone(get_keyring_master_key())
            self.assertFalse(set_keyring_master_key("b" * 64))
            self.assertFalse(delete_keyring_master_key())

        # Priority 0 or null/fail backend
        null_backend = MagicMock()
        null_backend.priority = 0
        null_backend.__class__.__module__ = "keyring.backends.null"
        with patch.dict("sys.modules", {"keyring": MagicMock(get_keyring=lambda: null_backend)}):
            self.assertFalse(is_keyring_available())


class TestCryptoResolutionAndEnvelope(unittest.TestCase):
    """Test 5-tier fallback hierarchy and AES-256-GCM envelope."""

    def setUp(self):
        reset_master_key_cache()
        self.orig_env = os.environ.get("ANTIGRAVITY_MASTER_KEY")
        if "ANTIGRAVITY_MASTER_KEY" in os.environ:
            del os.environ["ANTIGRAVITY_MASTER_KEY"]

    def tearDown(self):
        reset_master_key_cache()
        if self.orig_env is not None:
            os.environ["ANTIGRAVITY_MASTER_KEY"] = self.orig_env
        elif "ANTIGRAVITY_MASTER_KEY" in os.environ:
            del os.environ["ANTIGRAVITY_MASTER_KEY"]

    def test_tier1_env_resolution(self):
        # 64-char hex
        k_hex = "f" * 64
        os.environ["ANTIGRAVITY_MASTER_KEY"] = k_hex
        key = resolve_master_key(force_refresh=True)
        self.assertEqual(key, bytes.fromhex(k_hex))

        # Raw string passphrase hashed
        os.environ["ANTIGRAVITY_MASTER_KEY"] = "my-custom-passphrase"
        key_raw = resolve_master_key(force_refresh=True)
        self.assertEqual(len(key_raw), 32)

    def test_tier2_keyring_resolution(self):
        mock_k = "e" * 64
        with patch("launcher_crypto.is_keyring_available", return_value=True):
            with patch("launcher_crypto.get_keyring_master_key", return_value=mock_k):
                key = resolve_master_key(force_refresh=True)
                self.assertEqual(key, bytes.fromhex(mock_k))

    def test_tier3_file_resolution(self):
        temp_dir = tempfile.mkdtemp()
        try:
            with patch("launcher_crypto.CONFIG_DIR", temp_dir):
                with patch("launcher_crypto.is_keyring_available", return_value=False):
                    key = resolve_master_key(force_refresh=True)
                    self.assertEqual(len(key), 32)
                    key_file = os.path.join(temp_dir, ".master_key")
                    self.assertTrue(os.path.exists(key_file))
                    # Reload from file
                    reset_master_key_cache()
                    key2 = resolve_master_key(force_refresh=True)
                    self.assertEqual(key, key2)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_tier4_pbkdf2_fallback(self):
        temp_dir = tempfile.mkdtemp()
        try:
            non_writable = os.path.join(temp_dir, "nonexistent_sub", "dir")
            with patch("launcher_crypto.CONFIG_DIR", non_writable):
                with patch("launcher_crypto.is_keyring_available", return_value=False):
                    key = resolve_master_key(force_refresh=True)
                    self.assertEqual(len(key), 32)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_envelope_v2_roundtrip_and_migration(self):
        plain = "ya29.sample_test_token_content"
        enc = encrypt_token(plain)
        self.assertTrue(enc.startswith(ENVELOPE_V2_PREFIX))
        dec = decrypt_token(enc)
        self.assertEqual(dec, plain)

        # Idempotence: encrypting v2 again returns identical v2
        enc2 = encrypt_token(enc)
        self.assertEqual(enc, enc2)

        # Legacy enc:v1: upgrade: decrypts then upgrades to v2
        legacy_key = get_legacy_crypto_key()
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import base64
        iv = os.urandom(12)
        ct_tag = AESGCM(legacy_key).encrypt(iv, plain.encode("utf-8"), None)
        v1_token = f"enc:v1:{base64.b64encode(iv).decode('ascii')}:{base64.b64encode(ct_tag[:-16]).decode('ascii')}:{base64.b64encode(ct_tag[-16:]).decode('ascii')}"
        self.assertEqual(decrypt_token(v1_token), plain)
        upgraded = encrypt_token(v1_token)
        self.assertTrue(upgraded.startswith(ENVELOPE_V2_PREFIX))
        self.assertEqual(decrypt_token(upgraded), plain)

        # Plaintext and invalid formats
        self.assertEqual(decrypt_token(plain), plain)
        self.assertEqual(decrypt_token(""), "")
        self.assertEqual(decrypt_token("enc:invalid:short"), "enc:invalid:short")

        # Tampered ciphertext handled gracefully without raising
        tampered = enc[:-5] + "XXXXX"
        self.assertEqual(decrypt_token(tampered), tampered)

    def test_account_dict_transform(self):
        acc = {"email": "test@domain.com", "accessToken": "ya29.123", "refreshToken": "1//456"}
        enc_acc = encrypt_account_tokens(acc)
        self.assertTrue(enc_acc["accessToken"].startswith(ENVELOPE_V2_PREFIX))
        self.assertTrue(enc_acc["refreshToken"].startswith(ENVELOPE_V2_PREFIX))
        dec_acc = decrypt_account_tokens(enc_acc)
        self.assertEqual(dec_acc["accessToken"], "ya29.123")
        self.assertEqual(dec_acc["refreshToken"], "1//456")


class TestProductionAccountsAndInterop(unittest.TestCase):
    """Test 100% decryption of all 13 existing accounts and Node.js interop."""

    def test_all_13_existing_accounts_decrypt(self):
        accounts = load_accounts()
        self.assertEqual(len(accounts), 13, "System must have 13 accounts")
        for i, acc in enumerate(accounts):
            at = acc.get("accessToken", "")
            rt = acc.get("refreshToken", "")
            self.assertTrue(at.startswith("ya29."), f"Account {i+1} ({acc.get('email')}) accessToken failed")
            self.assertTrue(rt.startswith("1//"), f"Account {i+1} ({acc.get('email')}) refreshToken failed")

    def test_node_cross_runtime_parity(self):
        token = "ya29.cross_runtime_interop_token"
        py_enc = encrypt_token(token)

        # Node decrypts Python v2
        cmd_node_dec = [
            "node", "-e",
            f'const {{ decryptToken }} = require("./proxy/crypto_helper"); console.log(decryptToken("{py_enc}"));'
        ]
        res = subprocess.run(cmd_node_dec, capture_output=True, text=True, check=True)
        self.assertEqual(res.stdout.strip(), token)

        # Python decrypts Node v2
        cmd_node_enc = [
            "node", "-e",
            f'const {{ encryptToken }} = require("./proxy/crypto_helper"); console.log(encryptToken("{token}"));'
        ]
        res2 = subprocess.run(cmd_node_enc, capture_output=True, text=True, check=True)
        node_enc = res2.stdout.strip()
        self.assertTrue(node_enc.startswith("enc:v2:"))
        self.assertEqual(decrypt_token(node_enc), token)

    def test_node_helper_unit_tests(self):
        node_script = """
        const assert = require('assert');
        const helper = require('./proxy/crypto_helper');
        
        // Machine fingerprint non-empty
        const fp = helper.getMachineFingerprint();
        assert.ok(fp.length > 0);

        // Crypto key lengths
        const k1 = helper.getCryptoKey();
        assert.strictEqual(k1.length, 32);
        const k2 = helper.getCryptoKeyV2();
        assert.strictEqual(k2.length, 32);

        // Token encryption and roundtrip
        const plain = 'ya29.node_test_token';
        const enc = helper.encryptToken(plain);
        assert.ok(enc.startsWith('enc:v2:'));
        assert.strictEqual(helper.decryptToken(enc), plain);

        // Idempotence
        assert.strictEqual(helper.encryptToken(enc), enc);

        // Plaintext safety
        assert.strictEqual(helper.decryptToken('plain_token'), 'plain_token');

        // Account dictionary encryption
        const acc = { email: 'node@test.com', accessToken: 'ya29.111', refreshToken: '1//222' };
        const encAcc = helper.encryptAccountTokens(acc);
        assert.ok(encAcc.accessToken.startsWith('enc:v2:'));
        const decAcc = helper.decryptAccountTokens(encAcc);
        assert.strictEqual(decAcc.accessToken, 'ya29.111');
        assert.strictEqual(decAcc.refreshToken, '1//222');
        """
        res = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
        self.assertEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
