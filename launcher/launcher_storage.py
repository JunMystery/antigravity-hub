# -*- coding: utf-8 -*-
"""
Module quản lý lưu trữ cấu hình và dữ liệu profiles/accounts của Antigravity Launcher.
Tái xuất (re-export) các đường dẫn và hằng số từ launcher_paths để bảo đảm tính tương thích ngược.
"""

import os
import re
import json
import time
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
    """Ghi JSON an toàn qua tệp tạm (atomic os.replace) và giữ bản dự phòng .bak."""
    parent_dir = os.path.dirname(os.path.abspath(path)) or CONFIG_DIR
    os.makedirs(parent_dir, exist_ok=True)
    payload = json.dumps(content, indent=2, ensure_ascii=False)
    if os.path.exists(path):
        try:
            if os.path.getsize(path) > 2:
                with open(path, "r", encoding="utf-8") as rf:
                    json.load(rf)
                shutil.copy2(path, f"{path}.bak")
        except Exception:
            pass

    tmp_path = f"{path}.{os.getpid()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    if os.name != "nt":
        try:
            os.chmod(tmp_path, 0o600)
        except Exception:
            pass
    os.replace(tmp_path, path)

def _read_json_with_backup(path: str):
    """Đọc tệp JSON; tự động khôi phục từ .bak nếu tệp chính bị hỏng hoặc thất lạc."""
    bak_path = f"{path}.bak"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                parsed = json.load(f)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            try:
                shutil.copy2(path, f"{path}.corrupt.{int(time.time())}")
            except Exception:
                pass
    if os.path.exists(bak_path):
        try:
            with open(bak_path, "r", encoding="utf-8") as bf:
                bak_data = json.load(bf)
            if isinstance(bak_data, dict):
                _secure_write(path, bak_data)
                return bak_data
        except Exception:
            pass
    return None

def _default_profiles_data() -> dict:
    return {
        "settings": {
            "use_proxy": True,
            "round_robin_enabled": True,
            "requests_per_account": 1,
            "language": "vi",
            "log_retention_days": 30
        },
        "profiles": []
    }

def load_data() -> dict:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(PROFILES_BASE_DIR, exist_ok=True)
    data = _read_json_with_backup(PROFILES_FILE)
    if data is None:
        default_data = _default_profiles_data()
        if not os.path.exists(PROFILES_FILE):
            save_data(default_data)
        return default_data

    data.setdefault("settings", {})
    data["settings"].setdefault("requests_per_account", 1)
    data["settings"].setdefault("round_robin_enabled", True)
    data["settings"].setdefault("language", "vi")
    data["settings"].setdefault("app_binary", APP_BINARY)
    data["settings"].setdefault("ide_binary", find_ide_binary())
    data["settings"].setdefault("log_retention_days", 30)
    profiles = data.get("profiles", [])
    for idx, p in enumerate(profiles):
        if "order" not in p or not isinstance(p["order"], int):
            p["order"] = idx + 1
    profiles.sort(key=lambda x: x.get("order", 99999))
    for idx, p in enumerate(profiles):
        p["order"] = idx + 1
    data["profiles"] = profiles
    return data

def save_data(data: dict) -> None:
    _secure_write(PROFILES_FILE, data)

def load_accounts() -> list:
    parsed = _read_json_with_backup(ACCOUNTS_FILE)
    if not parsed:
        return []
    raw_accs = parsed.get("accounts", [])
    return [a for a in raw_accs if isinstance(a, dict)]

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
