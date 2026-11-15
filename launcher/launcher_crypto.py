# -*- coding: utf-8 -*-
"""Mã hóa/giải mã Token bảo mật AES-256-GCM với 5-tier Master Key."""

import os
import base64
import hashlib
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    from launcher.launcher_paths import CONFIG_DIR
except ImportError:
    from launcher_paths import CONFIG_DIR

try:
    from launcher.launcher_keyring import is_keyring_available, get_keyring_master_key, set_keyring_master_key
except ImportError:
    from launcher_keyring import is_keyring_available, get_keyring_master_key, set_keyring_master_key

TOKEN_SALT_V1 = "Antigravity-Token-Salt-v1"
TOKEN_SALT_V2 = b"Antigravity-Token-Salt-v2"
ENVELOPE_V1_PREFIX = "enc:v1:"
ENVELOPE_V2_PREFIX = "enc:v2:"
ENVELOPE_PREFIX = ENVELOPE_V1_PREFIX
_CACHED_MASTER_KEY: Optional[bytes] = None


def get_machine_fingerprint() -> str:
    """Xác định mã định danh phần cứng/hệ điều hành duy nhất của máy tính."""
    mk = os.environ.get("ANTIGRAVITY_MASTER_KEY", "").strip()
    if mk and len(mk) != 64:
        return mk
    mid = ""
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    mid = f.read().strip()
                if mid:
                    break
            except Exception:
                pass
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "user"
    computer = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "host"
    if not mid:
        mid = f"{computer}_{user}"
    return f"{mid}:{user}"


def get_legacy_crypto_key() -> bytes:
    """Sinh khóa mã hóa legacy v1 (SHA-256 từ machine fingerprint và salt v1)."""
    return hashlib.sha256(f"{get_machine_fingerprint()}:{TOKEN_SALT_V1}".encode("utf-8")).digest()


def reset_master_key_cache() -> None:
    """Xóa cache khóa trong bộ nhớ để phục vụ reload hoặc kiểm thử."""
    global _CACHED_MASTER_KEY
    _CACHED_MASTER_KEY = None


def resolve_master_key(force_refresh: bool = False) -> bytes:
    """Phân giải Master Key 256-bit theo phân cấp 5 tầng (5-Tier Fallback)."""
    global _CACHED_MASTER_KEY
    if _CACHED_MASTER_KEY is not None and not force_refresh:
        return _CACHED_MASTER_KEY

    # Tier 1: Biến môi trường ANTIGRAVITY_MASTER_KEY
    env_k = os.environ.get("ANTIGRAVITY_MASTER_KEY", "").strip()
    if env_k:
        try:
            _CACHED_MASTER_KEY = bytes.fromhex(env_k) if len(env_k) == 64 else hashlib.sha256(env_k.encode()).digest()
        except ValueError:
            _CACHED_MASTER_KEY = hashlib.sha256(env_k.encode()).digest()
        return _CACHED_MASTER_KEY

    # Tier 2: OS Keyring an toàn
    try:
        if is_keyring_available():
            hex_k = get_keyring_master_key()
            if hex_k and len(hex_k) == 64:
                _CACHED_MASTER_KEY = bytes.fromhex(hex_k)
                return _CACHED_MASTER_KEY
            fresh = os.urandom(32)
            if set_keyring_master_key(fresh.hex()):
                _CACHED_MASTER_KEY = fresh
                return _CACHED_MASTER_KEY
    except Exception:
        pass

    # Tier 3: File cục bộ được bảo vệ ~/.config/antigravity-launcher/.master_key (mode 0600)
    try:
        key_file = os.path.join(CONFIG_DIR, ".master_key")
        if os.path.exists(key_file):
            with open(key_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if len(content) == 64:
                try:
                    _CACHED_MASTER_KEY = bytes.fromhex(content)
                    return _CACHED_MASTER_KEY
                except ValueError:
                    pass
        fresh = os.urandom(32)
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(key_file, "w", encoding="utf-8") as f:
            f.write(fresh.hex() + "\n")
        if os.name != "nt":
            try:
                os.chmod(key_file, 0o600)
            except Exception:
                pass
        _CACHED_MASTER_KEY = fresh
        return _CACHED_MASTER_KEY
    except Exception:
        pass

    # Tier 4: PBKDF2-HMAC-SHA256 ràng buộc phần cứng (100,000 vòng)
    try:
        _CACHED_MASTER_KEY = hashlib.pbkdf2_hmac("sha256", get_machine_fingerprint().encode("utf-8"), TOKEN_SALT_V2, 100000, 32)
        return _CACHED_MASTER_KEY
    except Exception:
        pass

    # Tier 5: Fallback cơ chế legacy v1
    _CACHED_MASTER_KEY = get_legacy_crypto_key()
    return _CACHED_MASTER_KEY


get_crypto_key = resolve_master_key


def encrypt_token(plain_text: str) -> str:
    """Mã hóa token thành envelope enc:v2:<iv>:<ct>:<tag>."""
    if not plain_text or not isinstance(plain_text, str) or plain_text.startswith(ENVELOPE_V2_PREFIX):
        return plain_text or ""
    if plain_text.startswith(ENVELOPE_V1_PREFIX):
        dec = decrypt_token(plain_text)
        if not dec.startswith("enc:"):
            plain_text = dec
    try:
        key = resolve_master_key()
        iv = os.urandom(12)
        ct_tag = AESGCM(key).encrypt(iv, plain_text.encode("utf-8"), None)
        iv_b64 = base64.b64encode(iv).decode("ascii")
        ct_b64 = base64.b64encode(ct_tag[:-16]).decode("ascii")
        tag_b64 = base64.b64encode(ct_tag[-16:]).decode("ascii")
        return f"{ENVELOPE_V2_PREFIX}{iv_b64}:{ct_b64}:{tag_b64}"
    except Exception:
        return plain_text


def decrypt_token(cipher_text: str) -> str:
    """Giải mã token từ envelope (hỗ trợ cả enc:v1: và enc:v2:, plaintext trả về nguyên bản)."""
    if not cipher_text or not isinstance(cipher_text, str) or not cipher_text.startswith("enc:"):
        return cipher_text or ""
    try:
        parts = cipher_text.split(":")
        if len(parts) != 5:
            return cipher_text
        _, ver, iv_b64, ct_b64, tag_b64 = parts
        iv = base64.b64decode(iv_b64)
        ct = base64.b64decode(ct_b64)
        tag = base64.b64decode(tag_b64)
        keys = [get_legacy_crypto_key(), resolve_master_key()] if ver == "v1" else [resolve_master_key(), get_legacy_crypto_key()]
        for k in keys:
            try:
                return AESGCM(k).decrypt(iv, ct + tag, None).decode("utf-8")
            except Exception:
                continue
        return cipher_text
    except Exception:
        return cipher_text


def encrypt_account_tokens(acc: dict) -> dict:
    """Mã hóa các trường token nhạy cảm trong đối tượng account."""
    if not isinstance(acc, dict):
        return acc
    cloned = dict(acc)
    for k in ("accessToken", "refreshToken"):
        if cloned.get(k):
            cloned[k] = encrypt_token(cloned[k])
    return cloned


def decrypt_account_tokens(acc: dict) -> dict:
    """Giải mã các trường token nhạy cảm trong đối tượng account."""
    if not isinstance(acc, dict):
        return acc
    cloned = dict(acc)
    for k in ("accessToken", "refreshToken"):
        if cloned.get(k):
            cloned[k] = decrypt_token(cloned[k])
    return cloned
