# -*- coding: utf-8 -*-
"""
Unit tests for launcher_backup module (create_backup, restore_backup).
"""

import os
import sys
import json
import shutil
import tempfile
import zipfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "launcher"))

from launcher.launcher_backup import create_backup, restore_backup

class TestLauncherBackup(unittest.TestCase):
    """Kiểm tra chức năng sao lưu và phục hồi tài khoản / cấu hình."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.test_dir, "config")
        os.makedirs(self.config_dir, exist_ok=True)

        self.accounts_file = os.path.join(self.config_dir, "accounts.json")
        self.profiles_file = os.path.join(self.config_dir, "profiles.json")

        self.sample_accounts = {
            "accounts": [
                {"email": "user1@example.com", "token": "token1", "priority": 1},
                {"email": "user2@example.com", "token": "token2", "priority": 2}
            ]
        }
        self.sample_profiles = {
            "profiles": [
                {"id": "user1@example.com", "email": "user1@example.com", "order": 1, "data_dir": os.path.join(self.test_dir, "p1")},
                {"id": "user2@example.com", "email": "user2@example.com", "order": 2, "data_dir": os.path.join(self.test_dir, "p2")}
            ]
        }

        with open(self.accounts_file, "w", encoding="utf-8") as f:
            json.dump(self.sample_accounts, f)
        with open(self.profiles_file, "w", encoding="utf-8") as f:
            json.dump(self.sample_profiles, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("launcher.launcher_backup.CONFIG_DIR")
    @patch("launcher.launcher_backup.ACCOUNTS_FILE")
    @patch("launcher.launcher_backup.PROFILES_FILE")
    def test_create_backup_success(self, mock_prof, mock_acc, mock_cfg):
        mock_cfg.__str__.return_value = self.config_dir
        mock_acc.__str__.return_value = self.accounts_file
        mock_prof.__str__.return_value = self.profiles_file

        zip_out = os.path.join(self.test_dir, "out_backup.zip")
        with patch("launcher.launcher_backup.ACCOUNTS_FILE", self.accounts_file), \
             patch("launcher.launcher_backup.PROFILES_FILE", self.profiles_file):
            ok, path = create_backup(zip_out)

        self.assertTrue(ok)
        self.assertEqual(path, zip_out)
        self.assertTrue(os.path.exists(zip_out))
        self.assertTrue(zipfile.is_zipfile(zip_out))

        with zipfile.ZipFile(zip_out, "r") as zf:
            names = zf.namelist()
            self.assertIn("accounts.json", names)
            self.assertIn("profiles.json", names)
            self.assertIn("backup_manifest.json", names)
            manifest = json.loads(zf.read("backup_manifest.json").decode("utf-8"))
            self.assertEqual(manifest.get("app"), "antigravity-launcher")

    @patch("launcher.launcher_backup.CONFIG_DIR")
    def test_restore_backup_replace_and_merge(self, mock_cfg):
        mock_cfg.__str__.return_value = self.config_dir
        zip_out = os.path.join(self.test_dir, "test_bak.zip")

        with patch("launcher.launcher_backup.ACCOUNTS_FILE", self.accounts_file), \
             patch("launcher.launcher_backup.PROFILES_FILE", self.profiles_file):
            ok, _ = create_backup(zip_out)
            self.assertTrue(ok)

            # Thay đổi dữ liệu hiện tại để test replace
            with open(self.accounts_file, "w", encoding="utf-8") as f:
                json.dump({"accounts": [{"email": "modified@example.com"}]}, f)

            ok_rep, _ = restore_backup(zip_out, mode="replace")
            self.assertTrue(ok_rep)
            with open(self.accounts_file, "r", encoding="utf-8") as f:
                res_acc = json.load(f)
            self.assertEqual(len(res_acc["accounts"]), 2)
            self.assertEqual(res_acc["accounts"][0]["email"], "user1@example.com")

            # Test merge mode: thêm 1 account mới vào current
            with open(self.accounts_file, "w", encoding="utf-8") as f:
                json.dump({"accounts": [{"email": "newuser@example.com"}]}, f)
            with open(self.profiles_file, "w", encoding="utf-8") as f:
                json.dump({"profiles": [{"id": "newuser@example.com", "email": "newuser@example.com", "order": 1}]}, f)

            with patch("launcher.launcher_backup.load_data") as mock_ld, \
                 patch("launcher.launcher_backup.save_data") as mock_sd:
                mock_ld.return_value = {"profiles": [{"id": "newuser@example.com", "email": "newuser@example.com", "order": 1}]}
                ok_mrg, _ = restore_backup(zip_out, mode="merge")
                self.assertTrue(ok_mrg)
                self.assertTrue(mock_sd.called)
                saved_profs = mock_sd.call_args[0][0]["profiles"]
                self.assertEqual(len(saved_profs), 3)

    def test_restore_invalid_zip(self):
        ok, msg = restore_backup("/path/does/not/exist.zip")
        self.assertFalse(ok)

        empty_zip = os.path.join(self.test_dir, "empty.zip")
        with zipfile.ZipFile(empty_zip, "w") as zf:
            zf.writestr("dummy.txt", "hello")
        ok2, msg2 = restore_backup(empty_zip)
        self.assertFalse(ok2)

    def test_restore_rejects_legacy_encrypted_tokens(self):
        legacy_zip = os.path.join(self.test_dir, "legacy_enc.zip")
        with zipfile.ZipFile(legacy_zip, "w") as zf:
            zf.writestr("accounts.json", json.dumps({
                "accounts": [{
                    "email": "old@example.com",
                    "accessToken": "enc:v2:iv:ct:tag",
                    "refreshToken": "enc:v2:iv:ct:tag"
                }]
            }))
        with patch("launcher.launcher_backup.CONFIG_DIR", self.config_dir), \
             patch("launcher.launcher_backup.ACCOUNTS_FILE", self.accounts_file), \
             patch("launcher.launcher_backup.PROFILES_FILE", self.profiles_file):
            ok, msg = restore_backup(legacy_zip, mode="replace")
        self.assertFalse(ok)
        self.assertIn("enc:v1/enc:v2", msg)

    def test_restore_remaps_cross_os_paths_and_binaries(self):
        cross_zip = os.path.join(self.test_dir, "cross_os.zip")
        local_profiles_base = os.path.join(self.test_dir, "local_profiles")
        foreign_path = "/home/otheruser/.config/Antigravity-Profiles/user1_example_com" if os.name == "nt" else r"C:\Users\Other\AppData\Roaming\Antigravity-Profiles\user1_example_com"
        with zipfile.ZipFile(cross_zip, "w") as zf:
            zf.writestr("accounts.json", json.dumps({
                "accounts": [{
                    "email": "user1@example.com",
                    "accessToken": "ya29.plain_token",
                    "refreshToken": "1//plain_refresh"
                }]
            }))
            zf.writestr("profiles.json", json.dumps({
                "settings": {
                    "app_binary": "/nonexistent/other/os/antigravity",
                    "ide_binary": "/nonexistent/other/os/antigravity-ide"
                },
                "profiles": [{
                    "id": "user1_example_com",
                    "email": "user1@example.com",
                    "order": 1,
                    "data_dir": foreign_path
                }]
            }))

        def _read_prof():
            with open(self.profiles_file, "r", encoding="utf-8") as f:
                return json.load(f)

        def _write_prof(d):
            with open(self.profiles_file, "w", encoding="utf-8") as f:
                json.dump(d, f)

        with patch("launcher.launcher_backup.CONFIG_DIR", self.config_dir), \
             patch("launcher.launcher_backup.ACCOUNTS_FILE", self.accounts_file), \
             patch("launcher.launcher_backup.PROFILES_FILE", self.profiles_file), \
             patch("launcher.launcher_backup.PROFILES_BASE_DIR", local_profiles_base), \
             patch("launcher.launcher_backup.load_data", side_effect=_read_prof), \
             patch("launcher.launcher_backup.save_data", side_effect=_write_prof):
            ok, _ = restore_backup(cross_zip, mode="replace")

        self.assertTrue(ok)
        with open(self.profiles_file, "r", encoding="utf-8") as f:
            restored = json.load(f)
        remapped = restored["profiles"][0]["data_dir"]
        self.assertEqual(os.path.normpath(remapped), os.path.normpath(os.path.join(local_profiles_base, "user1_example_com")))
        self.assertTrue(os.path.isdir(remapped))
        self.assertNotEqual(restored["settings"]["app_binary"], "/nonexistent/other/os/antigravity")

        with open(self.accounts_file, "r", encoding="utf-8") as f:
            accs = json.load(f)["accounts"]
        self.assertEqual(accs[0]["accessToken"], "ya29.plain_token")
        self.assertEqual(accs[0]["refreshToken"], "1//plain_refresh")

if __name__ == "__main__":
    unittest.main()
