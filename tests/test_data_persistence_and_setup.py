# -*- coding: utf-8 -*-
import os
import sys
import json
import shutil
import tempfile
import subprocess
import unittest
from unittest.mock import patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "launcher"))

import launcher_storage
import launcher_cert
import launcher_paths


class TestDataPersistenceAndSetup(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.cfg_dir = os.path.join(self.tmp_dir, "config")
        self.prof_base = os.path.join(self.tmp_dir, "profiles_base")
        os.makedirs(self.cfg_dir, exist_ok=True)
        self.prof_file = os.path.join(self.cfg_dir, "profiles.json")
        self.acc_file = os.path.join(self.cfg_dir, "accounts.json")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_atomic_save_and_corrupt_recovery_from_bak(self):
        with patch.object(launcher_storage, "CONFIG_DIR", self.cfg_dir), \
             patch.object(launcher_storage, "PROFILES_FILE", self.prof_file), \
             patch.object(launcher_storage, "ACCOUNTS_FILE", self.acc_file), \
             patch.object(launcher_storage, "PROFILES_BASE_DIR", self.prof_base):
            original = {
                "settings": {"requests_per_account": 5, "language": "en", "model_rules": [{"pattern": "opus"}]},
                "profiles": [{"id": "a1", "email": "vip@test.com", "order": 1, "enabled": True}]
            }
            launcher_storage.save_data(original)
            original["settings"]["requests_per_account"] = 7
            launcher_storage.save_data(original)

            self.assertTrue(os.path.exists(self.prof_file + ".bak"))
            self.assertFalse(any(name.endswith(".tmp") for name in os.listdir(self.cfg_dir)))

            # Corrupt primary profiles.json -> should auto-recover from .bak
            with open(self.prof_file, "w", encoding="utf-8") as f:
                f.write("{broken_json")
            recovered = launcher_storage.load_data()
            self.assertEqual(recovered["profiles"][0]["email"], "vip@test.com")
            self.assertEqual(recovered["settings"]["model_rules"][0]["pattern"], "opus")
            self.assertTrue(any(".corrupt." in n for n in os.listdir(self.cfg_dir)))

            # Accounts backup recovery
            launcher_storage.save_accounts([{"id": "a1", "email": "vip@test.com", "refreshToken": "r1"}])
            launcher_storage.save_accounts([{"id": "a1", "email": "vip@test.com", "refreshToken": "r2"}])
            os.remove(self.acc_file)
            accs = launcher_storage.load_accounts()
            self.assertEqual(len(accs), 1)
            self.assertEqual(accs[0]["refreshToken"], "r1")

    def test_root_ca_stored_under_config_dir_and_migrates_legacy(self):
        self.assertEqual(
            os.path.normpath(launcher_paths.get_root_ca_path()),
            os.path.normpath(os.path.join(launcher_paths.CONFIG_DIR, "certs", "ca.crt"))
        )
        legacy_dir = os.path.join(self.tmp_dir, "legacy_certs")
        target_dir = os.path.join(self.cfg_dir, "certs")
        os.makedirs(legacy_dir, exist_ok=True)
        with open(os.path.join(legacy_dir, "ca.crt"), "w", encoding="utf-8") as f:
            f.write("LEGACY_CERT_PEM")
        with open(os.path.join(legacy_dir, "ca.key"), "w", encoding="utf-8") as f:
            f.write("LEGACY_KEY_PEM")

        target_crt = os.path.join(target_dir, "ca.crt")
        with patch.object(launcher_cert, "CERTS_DIR", target_dir), \
             patch.object(launcher_cert, "ROOT_CA", target_crt), \
             patch.object(launcher_cert, "LEGACY_CERTS_DIR", legacy_dir):
            self.assertTrue(launcher_cert.ensure_certificates())
        with open(target_crt, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "LEGACY_CERT_PEM")

    def test_oauth_flow_atomic_writes_create_bak(self):
        code = f"""
        const fs = require("node:fs");
        const path = require("node:path");
        const {{ saveAuthorizedAccount }} = require("./proxy/oauth_flow");
        const accFile = {json.dumps(self.acc_file)};
        const profFile = {json.dumps(self.prof_file)};
        const profBase = {json.dumps(self.prof_base)};
        saveAuthorizedAccount({{ email: "a@test.com", accessToken: "t1", refreshToken: "r1", expiresAt: Date.now() + 3600000 }}, {{ accountsFile: accFile, profilesFile: profFile, profilesBaseDir: profBase }});
        saveAuthorizedAccount({{ email: "a@test.com", accessToken: "t2", refreshToken: "r2", expiresAt: Date.now() + 3600000 }}, {{ accountsFile: accFile, profilesFile: profFile, profilesBaseDir: profBase }});
        console.log(JSON.stringify({{ hasAccBak: fs.existsSync(accFile + ".bak"), hasProfBak: fs.existsSync(profFile + ".bak") }}));
        """
        res = subprocess.run(["node", "-e", code], cwd=ROOT_DIR, capture_output=True, text=True, check=True)
        out = json.loads(res.stdout.strip().splitlines()[-1])
        self.assertTrue(out["hasAccBak"])
        self.assertTrue(out["hasProfBak"])

    def test_save_data_guards_partial_empty_wipe_and_recovers_from_accounts(self):
        with patch.object(launcher_storage, "CONFIG_DIR", self.cfg_dir), \
             patch.object(launcher_storage, "PROFILES_FILE", self.prof_file), \
             patch.object(launcher_storage, "ACCOUNTS_FILE", self.acc_file), \
             patch.object(launcher_storage, "PROFILES_BASE_DIR", self.prof_base):
            launcher_storage.save_accounts([{"id": "a1", "email": "vip@test.com", "name": "VIP", "refreshToken": "r1"}])
            launcher_storage.save_data({
                "settings": {"requests_per_account": 3, "model_rules": [{"id": "r1", "pattern": "claude"}]},
                "profiles": [{"id": "a1", "email": "vip@test.com", "name": "VIP", "order": 1, "enabled": True}]
            })
            # Lần lưu thứ hai với dữ liệu hợp lệ để tạo .bak có đủ profiles
            launcher_storage.save_data({
                "settings": {"requests_per_account": 4, "model_rules": [{"id": "r1", "pattern": "claude"}]},
                "profiles": [{"id": "a1", "email": "vip@test.com", "name": "VIP", "order": 1, "enabled": True}]
            })

            # Partial / empty overwrite không được làm mất profiles hay model_rules
            launcher_storage.save_data({"settings": {"window_geometry": "abc"}})
            launcher_storage.save_data({"settings": {"window_maximized": True}, "profiles": []})
            data_after = launcher_storage.load_data()
            self.assertEqual(len(data_after["profiles"]), 1)
            self.assertEqual(data_after["settings"]["model_rules"][0]["pattern"], "claude")
            self.assertEqual(data_after["settings"]["window_maximized"], True)

            # update_settings_fields chỉ cập nhật khóa settings chỉ định
            launcher_storage.update_settings_fields({"window_geometry": "xyz"})
            data_upd = launcher_storage.load_data()
            self.assertEqual(len(data_upd["profiles"]), 1)
            self.assertEqual(data_upd["settings"]["window_geometry"], "xyz")
            self.assertEqual(data_upd["settings"]["model_rules"][0]["pattern"], "claude")

            # Tự phục hồi profiles từ accounts.json nếu profiles.json bị ghi rỗng bên ngoài
            existing_dir = os.path.join(self.prof_base, "vip_test_com")
            os.makedirs(existing_dir, exist_ok=True)
            with open(self.prof_file, "w", encoding="utf-8") as f:
                json.dump({"settings": {"requests_per_account": 4}, "profiles": []}, f)
            recovered = launcher_storage.load_data()
            self.assertEqual(len(recovered["profiles"]), 1)
            self.assertEqual(recovered["profiles"][0]["email"], "vip@test.com")
            self.assertEqual(recovered["profiles"][0]["data_dir"], existing_dir)

            # Xóa chủ động tài khoản cuối cùng vẫn phải xóa được sạch
            final_data = launcher_storage.delete_account_completely(recovered["profiles"][0])
            self.assertEqual(final_data["profiles"], [])
            self.assertEqual(launcher_storage.load_accounts(), [])


if __name__ == "__main__":
    unittest.main()
