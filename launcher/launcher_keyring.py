# -*- coding: utf-8 -*-
"""
Module tương tác an toàn với Native OS Keyring (Linux SecretService, WinVault, macOS Keychain).
Cung cấp khả năng lưu trữ, truy xuất và xóa Master Key với cơ chế phòng vệ ngoại lệ toàn diện.
"""

import re
from typing import Optional

SERVICE_NAME = "antigravity-launcher"
KEY_USERNAME = "master_key"
_HEX_64_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def is_keyring_available() -> bool:
    """Kiểm tra xem hệ thống có backend OS Keyring hợp lệ hay không.
    
    Không bao giờ ném ngoại lệ. Trả về False trong môi trường headless, SSH,
    Docker, hoặc khi thiếu thư viện/backend phù hợp.
    """
    try:
        import keyring
        backend = keyring.get_keyring()
        if backend is None:
            return False

        priority = getattr(backend, "priority", 0)
        if priority <= 0:
            return False

        module_name = getattr(backend.__class__, "__module__", "").lower()
        if "fail" in module_name or "null" in module_name:
            return False

        return True
    except Exception:
        return False


def get_keyring_master_key() -> Optional[str]:
    """Truy xuất Master Key (chuỗi 64 ký tự hex) từ OS Keyring.
    
    Trả về None nếu keyring không khả dụng, bị khóa, hoặc chưa lưu khóa.
    """
    if not is_keyring_available():
        return None

    try:
        import keyring
        raw_val = keyring.get_password(SERVICE_NAME, KEY_USERNAME)
        if not raw_val:
            return None

        clean_val = raw_val.strip()
        if _HEX_64_PATTERN.match(clean_val):
            return clean_val.lower()
        return None
    except Exception:
        return None


def set_keyring_master_key(key_hex: str) -> bool:
    """Lưu Master Key (chuỗi 64 ký tự hex) vào OS Keyring an toàn.
    
    Trả về True nếu thành công, False nếu thất bại hoặc input không hợp lệ.
    """
    if not isinstance(key_hex, str) or not _HEX_64_PATTERN.match(key_hex.strip()):
        return False

    if not is_keyring_available():
        return False

    try:
        import keyring
        keyring.set_password(SERVICE_NAME, KEY_USERNAME, key_hex.strip().lower())
        return True
    except Exception:
        return False


def delete_keyring_master_key() -> bool:
    """Xóa Master Key khỏi OS Keyring (dùng khi reset thông tin đăng nhập).
    
    Trả về True nếu xóa thành công hoặc khóa không tồn tại, False nếu lỗi quyền/keyring.
    """
    if not is_keyring_available():
        return False

    try:
        import keyring
        errors = getattr(keyring, "errors", None)
        pwd_del_err = getattr(errors, "PasswordDeleteError", Exception) if errors else Exception
        try:
            keyring.delete_password(SERVICE_NAME, KEY_USERNAME)
            return True
        except Exception as e:
            if isinstance(e, pwd_del_err) or "not found" in str(e).lower():
                return True
            return False
    except Exception:
        return False
