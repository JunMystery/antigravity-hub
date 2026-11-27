# -*- coding: utf-8 -*-
"""
Module sao lưu và phục hồi tài khoản & cấu hình cho Antigravity Launcher.
Hỗ trợ cả CLI (--backup, --restore) và GUI (BackupSettingsGroup).
"""

import os
import re
import sys
import json
import zipfile
from datetime import datetime
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QMessageBox
)

from launcher_i18n import tr
from launcher_theme import set_semantic_text, refresh_semantic_label
from launcher_storage import (
    CONFIG_DIR, ACCOUNTS_FILE, PROFILES_FILE, PROFILES_BASE_DIR,
    find_app_binary, find_ide_binary, load_data, save_data, _secure_write
)

_WIN_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _has_legacy_encrypted_tokens(accounts: list) -> bool:
    """Kiểm tra xem danh sách tài khoản có chứa token mã hóa cũ (enc:v1:/enc:v2:) không."""
    for a in accounts:
        if not isinstance(a, dict):
            continue
        for key in ("accessToken", "refreshToken"):
            val = a.get(key)
            if isinstance(val, str) and (val.startswith("enc:v1:") or val.startswith("enc:v2:")):
                return True
    return False


def _build_safe_slug(profile: dict) -> str:
    raw = str(profile.get("id") or profile.get("email") or profile.get("name") or "account")
    slug = re.sub(r"[^a-z0-9_]", "", raw.lower().replace("@", "_").replace(".", "_"))
    return slug or "account"


def _remap_profile_data_dir(profile: dict) -> bool:
    """Chuẩn hóa data_dir sang đường dẫn hợp lệ của hệ điều hành và user hiện tại."""
    if not isinstance(profile, dict):
        return False
    cur_dir = (profile.get("data_dir") or "").strip()
    slug = _build_safe_slug(profile)
    target_dir = os.path.join(PROFILES_BASE_DIR, slug)

    is_win_path = bool(_WIN_DRIVE_RE.match(cur_dir)) or ("\\" in cur_dir)
    is_posix_path = cur_dir.startswith("/")
    cross_os = (sys.platform == "win32" and is_posix_path) or (sys.platform != "win32" and is_win_path)

    foreign_profiles_dir = False
    if cur_dir and "antigravity-profiles" in cur_dir.lower():
        norm_cur = os.path.normcase(os.path.normpath(cur_dir))
        norm_base = os.path.normcase(os.path.normpath(PROFILES_BASE_DIR))
        if not norm_cur.startswith(norm_base):
            foreign_profiles_dir = True

    if not cur_dir or cross_os or foreign_profiles_dir:
        profile["data_dir"] = target_dir
        return True
    return False


def _sanitize_restored_settings(restored_settings: dict, local_settings: dict) -> dict:
    """Giữ lại đường dẫn binary hợp lệ của máy hiện tại nếu bản sao lưu trỏ tới máy/OS khác."""
    merged = dict(restored_settings) if isinstance(restored_settings, dict) else {}
    local = local_settings if isinstance(local_settings, dict) else {}
    for key, detector in (("app_binary", find_app_binary), ("ide_binary", find_ide_binary)):
        val = (merged.get(key) or "").strip()
        if not val or not os.path.exists(val):
            local_val = (local.get(key) or "").strip()
            merged[key] = local_val if (local_val and os.path.exists(local_val)) else detector()
    return merged


def create_backup(output_path=None) -> tuple[bool, str]:
    """Tạo file zip sao lưu dạng thuần (plain JSON) chứa accounts.json và profiles.json."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if not output_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(os.getcwd(), f"antigravity_backup_{ts}.zip")
        elif os.path.isdir(output_path):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(output_path, f"antigravity_backup_{ts}.zip")

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.exists(ACCOUNTS_FILE):
                zf.write(ACCOUNTS_FILE, arcname="accounts.json")
            if os.path.exists(PROFILES_FILE):
                zf.write(PROFILES_FILE, arcname="profiles.json")
            manifest = {
                "version": "2.0",
                "app": "antigravity-launcher",
                "token_format": "plain",
                "created_at": datetime.now().isoformat()
            }
            zf.writestr("backup_manifest.json", json.dumps(manifest, indent=2))
        return True, output_path
    except Exception as e:
        return False, str(e)


def restore_backup(zip_path: str, mode: str = "replace") -> tuple[bool, str]:
    """Phục hồi cấu hình và tài khoản từ file zip (chế độ: replace hoặc merge)."""
    if not os.path.exists(zip_path) or not zipfile.is_zipfile(zip_path):
        return False, tr("restore.invalid_zip")

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            if "accounts.json" not in names and "profiles.json" not in names:
                return False, tr("restore.invalid_zip")

            raw_acc_content = json.loads(zf.read("accounts.json").decode("utf-8")) if "accounts.json" in names else {}
            bak_profiles_raw = json.loads(zf.read("profiles.json").decode("utf-8")) if "profiles.json" in names else {}

        bak_accounts = raw_acc_content.get("accounts", []) if isinstance(raw_acc_content, dict) else (
            raw_acc_content if isinstance(raw_acc_content, list) else []
        )

        if _has_legacy_encrypted_tokens(bak_accounts):
            return False, tr("restore.incompatible_encryption")

        local_settings = {}
        if os.path.exists(PROFILES_FILE):
            try:
                with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                    local_settings = json.load(f).get("settings", {})
            except Exception:
                local_settings = {}

        if mode == "replace":
            if "accounts.json" in names:
                _secure_write(ACCOUNTS_FILE, {"accounts": bak_accounts})
            if "profiles.json" in names:
                restored_data = dict(bak_profiles_raw) if isinstance(bak_profiles_raw, dict) else {}
                for p in restored_data.get("profiles", []):
                    _remap_profile_data_dir(p)
                if "settings" in restored_data or local_settings:
                    restored_data["settings"] = _sanitize_restored_settings(
                        restored_data.get("settings", {}), local_settings
                    )
                _secure_write(PROFILES_FILE, restored_data)
        else:
            cur_raw_accs = []
            if os.path.exists(ACCOUNTS_FILE):
                try:
                    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                        cur_raw_accs = json.load(f).get("accounts", [])
                except Exception:
                    cur_raw_accs = []

            cur_acc_keys = {(a.get("email") or a.get("id") or "").lower() for a in cur_raw_accs if isinstance(a, dict)}
            for a in bak_accounts:
                if isinstance(a, dict):
                    key = (a.get("email") or a.get("id") or "").lower()
                    if key and key not in cur_acc_keys:
                        cur_raw_accs.append(a)
                        cur_acc_keys.add(key)
            _secure_write(ACCOUNTS_FILE, {"accounts": cur_raw_accs})

            cur_data = load_data()
            cur_profiles = cur_data.get("profiles", [])
            cur_prof_keys = {(p.get("id") or p.get("email") or "").lower() for p in cur_profiles if isinstance(p, dict)}
            bak_profiles = bak_profiles_raw.get("profiles", []) if isinstance(bak_profiles_raw, dict) else []
            for p in bak_profiles:
                if isinstance(p, dict):
                    key = (p.get("id") or p.get("email") or "").lower()
                    if key and key not in cur_prof_keys:
                        p = dict(p)
                        _remap_profile_data_dir(p)
                        p["order"] = len(cur_profiles) + 1
                        cur_profiles.append(p)
                        cur_prof_keys.add(key)
            cur_data["profiles"] = cur_profiles
            save_data(cur_data)

        final_data = load_data()
        path_fixed = False
        for p in final_data.get("profiles", []):
            if isinstance(p, dict):
                if _remap_profile_data_dir(p):
                    path_fixed = True
                target_dir = p.get("data_dir")
                if target_dir:
                    try:
                        os.makedirs(target_dir, exist_ok=True)
                    except OSError:
                        p["data_dir"] = os.path.join(PROFILES_BASE_DIR, _build_safe_slug(p))
                        os.makedirs(p["data_dir"], exist_ok=True)
                        path_fixed = True
        if path_fixed:
            save_data(final_data)

        return True, tr("restore.success", mode=mode)
    except Exception as e:
        return False, str(e)


class BackupSettingsGroup(QGroupBox):
    """Nhóm widget giao diện Sao lưu & Phục hồi cho Settings View."""

    def __init__(self, win, parent=None):
        super().__init__(tr("settings.backup_group"), parent)
        self.win = win
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.lbl_desc = QLabel(tr("settings.backup_desc"))
        self.lbl_desc.setWordWrap(True)
        layout.addWidget(self.lbl_desc)

        row_btn = QHBoxLayout()
        self.btn_backup = QPushButton(tr("btn.backup"))
        self.btn_backup.clicked.connect(self._on_backup)
        row_btn.addWidget(self.btn_backup)

        self.btn_restore = QPushButton(tr("btn.restore"))
        self.btn_restore.clicked.connect(self._on_restore)
        row_btn.addWidget(self.btn_restore)

        self.lbl_status = QLabel()
        row_btn.addWidget(self.lbl_status, 1)
        layout.addLayout(row_btn)

    def _on_backup(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fn, _ = QFileDialog.getSaveFileName(self, tr("backup.save_zip_title"), f"antigravity_backup_{ts}.zip", "Zip Files (*.zip)")
        if not fn:
            return
        ok, msg = create_backup(fn)
        if ok:
            set_semantic_text(self.lbl_status, tr("backup.success", path=os.path.basename(msg)), "green")
            QMessageBox.information(self, tr("settings.backup_group"), tr("backup.success", path=msg))
        else:
            set_semantic_text(self.lbl_status, tr("backup.failed", error=msg), "red")

    def _on_restore(self):
        fn, _ = QFileDialog.getOpenFileName(self, tr("restore.select_zip_title"), "", "Zip Files (*.zip)")
        if not fn:
            return
        mb = QMessageBox(self)
        mb.setWindowTitle(tr("restore.confirm_mode_title"))
        mb.setText(tr("restore.confirm_mode_msg"))
        btn_rep = mb.addButton(tr("restore.btn_replace"), QMessageBox.ButtonRole.AcceptRole)
        btn_mrg = mb.addButton(tr("restore.btn_merge"), QMessageBox.ButtonRole.ActionRole)
        mb.addButton(tr("btn.cancel"), QMessageBox.ButtonRole.RejectRole)
        mb.exec()
        btn = mb.clickedButton()
        if btn not in (btn_rep, btn_mrg):
            return
        mode = "replace" if btn == btn_rep else "merge"
        ok, msg = restore_backup(fn, mode=mode)
        if ok:
            set_semantic_text(self.lbl_status, msg, "green")
            self.win.data = load_data()
            try:
                from launcher_monitor import send_proxy_cmd
                send_proxy_cmd(self.win, "reload")
            except Exception:
                pass
            if hasattr(self.win, "_refresh_list"):
                self.win._refresh_list()
            if hasattr(self.win, "on_refresh_all_quota"):
                self.win.on_refresh_all_quota()
            QMessageBox.information(self, tr("settings.backup_group"), msg)
        else:
            set_semantic_text(self.lbl_status, msg, "red")
            QMessageBox.warning(self, tr("settings.backup_group"), msg)

    def refresh_theme(self):
        refresh_semantic_label(self.lbl_status)

    def retranslate_ui(self):
        self.setTitle(tr("settings.backup_group"))
        self.lbl_desc.setText(tr("settings.backup_desc"))
        self.btn_backup.setText(tr("btn.backup"))
        self.btn_restore.setText(tr("btn.restore"))
