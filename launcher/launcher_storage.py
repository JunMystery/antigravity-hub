# -*- coding: utf-8 -*-
"""
Module quản lý lưu trữ cấu hình và dữ liệu profiles/accounts của Antigravity Launcher.
Tái xuất (re-export) các đường dẫn và hằng số từ launcher_paths để bảo đảm tính tương thích ngược.
"""

import os
import re
import json
import shutil

# Re-export các đường dẫn, binary detector và hằng số cấu hình từ launcher_paths
from launcher_paths import (
    BASE_DIR, PROXY_DIR, ASSETS_DIR, ASSET_ICO, ASSET_PNG,
    CONFIG_DIR, PROFILES_FILE, ACCOUNTS_FILE, PROFILES_BASE_DIR,
    APP_BINARY, IDE_BINARY, APP_ICON, ROOT_CA, PROXY_SCRIPT, PROXY_PORT,
    PID_FILE, LAUNCHED_APPS_FILE, CACHE_TTL, MANUAL_COOLDOWN,
    CLIENT_ID, CLIENT_SECRET, USER_AGENT, PROXY_PAC,
    get_config_dir, get_profiles_base_dir, find_app_binary, find_ide_binary,
    get_app_binary, get_ide_binary, find_app_icon, get_proxy_script_path,
    get_root_ca_path, get_certificate_spki_fingerprint
)

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^\w\-]', '', text)
    return text or "account"

def _secure_write(path: str, content: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass

def load_data() -> dict:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(PROFILES_BASE_DIR, exist_ok=True)
    if not os.path.exists(PROFILES_FILE):
        default_data = {
            "settings": {
                "use_proxy": True,
                "round_robin_enabled": True,
                "requests_per_account": 1,
                "language": "vi"
            },
            "profiles": []
        }
        save_data(default_data)
        return default_data
    try:
        with open(PROFILES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("settings", {})
            data["settings"].setdefault("requests_per_account", 1)
            data["settings"].setdefault("round_robin_enabled", True)
            data["settings"].setdefault("language", "vi")
            data["settings"].setdefault("app_binary", APP_BINARY)
            data["settings"].setdefault("ide_binary", find_ide_binary())
            profiles = data.get("profiles", [])
            for idx, p in enumerate(profiles):
                if "order" not in p or not isinstance(p["order"], int):
                    p["order"] = idx + 1
            profiles.sort(key=lambda x: x.get("order", 99999))
            for idx, p in enumerate(profiles):
                p["order"] = idx + 1
            data["profiles"] = profiles
            return data
    except Exception:
        return {
            "settings": {
                "use_proxy": True,
                "round_robin_enabled": True,
                "requests_per_account": 1,
                "language": "vi"
            },
            "profiles": []
        }

def save_data(data: dict) -> None:
    _secure_write(PROFILES_FILE, data)

def load_accounts() -> list:
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("accounts", [])
    except Exception:
        return []

def save_accounts(accounts: list) -> None:
    _secure_write(ACCOUNTS_FILE, {"accounts": accounts})

def delete_account_completely(profile: dict) -> dict:
    """Xóa triệt để profile, token và thư mục dữ liệu trên đĩa."""
    sel_id = profile.get("id")
    sel_email = (profile.get("email") or "").lower()
    data_dir = profile.get("data_dir")

    data = load_data()
    data["profiles"] = [
        p for p in data.get("profiles", [])
        if p.get("id") != sel_id and (p.get("email") or "").lower() != sel_email
    ]
    for idx, p in enumerate(data.get("profiles", [])):
        p["order"] = idx + 1
    save_data(data)

    all_accs = load_accounts()
    filtered_accs = [
        a for a in all_accs
        if a.get("id") != sel_id and (a.get("email") or "").lower() != sel_email
    ]
    save_accounts(filtered_accs)

    if data_dir and os.path.exists(data_dir) and os.path.isdir(data_dir):
        try:
            shutil.rmtree(data_dir, ignore_errors=True)
        except Exception:
            pass

    return data
