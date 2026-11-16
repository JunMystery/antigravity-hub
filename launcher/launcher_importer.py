# -*- coding: utf-8 -*-
"""
Module hỗ trợ nhập tài khoản tự động từ các gateway bên thứ ba (như 9router)
vào Antigravity Launcher & Micro-Proxy.
"""

import os
import sqlite3
import json
from datetime import datetime

from launcher_storage import (
    load_data, save_data, save_accounts, load_accounts,
    CONFIG_DIR, PROFILES_BASE_DIR
)


def import_accounts_from_9router() -> bool:
    """Truy vấn cơ sở dữ liệu SQLite của 9router và nhập danh sách tài khoản Google."""
    db_path = os.path.expandvars(r"%APPDATA%\9router\db\data.sqlite")
    if not os.path.exists(db_path):
        # Kiểm tra thêm đường dẫn Linux fallback nếu chạy trên Linux
        db_path = os.path.expanduser("~/.config/9router/db/data.sqlite")

    if not os.path.exists(db_path):
        print(f"[INFO] Không tìm thấy cơ sở dữ liệu 9router tại: {db_path} (Bỏ qua bước nhập tự động).")
        return True

    print(f"Đang đọc dữ liệu tài khoản từ 9router: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, provider, authType, name, email, priority, isActive, data, createdAt, updatedAt
            FROM providerConnections
            WHERE provider = 'antigravity' OR authType = 'oauth'
            ORDER BY priority ASC
        """)
        rows = cursor.fetchall()
    except Exception as e:
        print(f"[ERROR] Lỗi khi truy vấn SQLite 9router: {e}")
        return False

    if not rows:
        print("[WARN] Không tìm thấy tài khoản Antigravity/OAuth nào trong 9router.")
        return False

    print(f"Tìm thấy {len(rows)} tài khoản trong 9router.")

    data = load_data()
    existing_profiles = data.get("profiles", [])
    existing_profile_emails = {(p.get("email") or "").lower(): p for p in existing_profiles}

    existing_accounts = load_accounts()
    existing_acc_emails = {(a.get("email") or "").lower(): a for a in existing_accounts}

    imported_accounts = list(existing_accounts)
    imported_profiles = list(existing_profiles)

    count = 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    for r in rows:
        cid, provider, authType, name, email, priority, isActive, data_str, createdAt, updatedAt = r
        if not email:
            continue
        email_clean = email.strip()
        email_lower = email_clean.lower()

        try:
            conn_data = json.loads(data_str) if data_str else {}
        except Exception:
            conn_data = {}

        access_token = conn_data.get("accessToken", "")
        refresh_token = conn_data.get("refreshToken", "")
        expires_at = conn_data.get("expiresAt", "")
        project_id = conn_data.get("projectId", "aicode-consumers")

        safe_slug = email_lower.replace("@", "_").replace(".", "_")
        safe_slug = "".join([c for c in safe_slug if c.isalnum() or c == "_"])
        data_dir = os.path.join(PROFILES_BASE_DIR, safe_slug)
        os.makedirs(data_dir, exist_ok=True)

        acc_obj = {
            "id": cid or safe_slug,
            "email": email_clean,
            "name": name or email_clean,
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": expires_at or now_str,
            "projectId": project_id
        }

        if email_lower in existing_acc_emails:
            idx = next(i for i, a in enumerate(imported_accounts) if (a.get("email") or "").lower() == email_lower)
            imported_accounts[idx] = acc_obj
        else:
            imported_accounts.append(acc_obj)
            existing_acc_emails[email_lower] = acc_obj

        prof_obj = {
            "id": safe_slug,
            "name": email_clean,
            "email": email_clean,
            "order": priority if isinstance(priority, int) else len(imported_profiles) + 1,
            "enabled": bool(isActive),
            "data_dir": data_dir,
            "created_at": now_str,
            "quota_5h_val": 0,
            "quota_5h": "--",
            "quota_5h_valid": False,
            "quota_weekly_val": 0,
            "quota_weekly": "--",
            "quota_weekly_valid": False,
            "quota_timestamp": 0
        }

        if email_lower in existing_profile_emails:
            idx = next(i for i, p in enumerate(imported_profiles) if (p.get("email") or "").lower() == email_lower)
            imported_profiles[idx].update({
                "enabled": bool(isActive),
                "order": priority if isinstance(priority, int) else imported_profiles[idx].get("order", idx + 1),
                "data_dir": data_dir
            })
        else:
            imported_profiles.append(prof_obj)
            existing_profile_emails[email_lower] = prof_obj

        count += 1
        print(f"  [+] Đã nhập #{priority}: {email_clean} (enabled={bool(isActive)})")

    imported_profiles.sort(key=lambda x: x.get("order", 99999))
    for idx, p in enumerate(imported_profiles):
        p["order"] = idx + 1

    data["profiles"] = imported_profiles
    save_data(data)
    save_accounts(imported_accounts)

    print(f"\n[OK] Đã nhập thành công {count} tài khoản từ 9router vào Antigravity Hub!")
    return True
