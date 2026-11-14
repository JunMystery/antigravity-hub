# -*- coding: utf-8 -*-
"""
Module quản lý mã hóa/giải mã Token bảo mật AES-256-GCM với Machine-Bound Key.
Hỗ trợ giải mã chéo 100% với Node.js Micro-Proxy và tự động di trú token cũ.
"""

import os
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TOKEN_SALT = "Antigravity-Token-Salt-v1"
ENVELOPE_PREFIX = "enc:v1:"

def get_machine_fingerprint() -> str:
    """Xác định mã định danh phần cứng/hệ điều hành duy nhất của máy tính."""
    master_key = os.environ.get("ANTIGRAVITY_MASTER_KEY")
    if master_key:
        return master_key.strip()

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

def get_crypto_key() -> bytes:
    """Sinh khóa mã hóa AES-256 (32 bytes) từ Machine Fingerprint và Salt."""
    fp = get_machine_fingerprint()
    return hashlib.sha256(f"{fp}:{TOKEN_SALT}".encode("utf-8")).digest()

def encrypt_token(plain_text: str) -> str:
    """Mã hóa token thành envelope enc:v1:<iv>:<ct>:<tag>."""
    if not plain_text or not isinstance(plain_text, str):
        return ""
    if plain_text.startswith(ENVELOPE_PREFIX):
        return plain_text

    try:
        key = get_crypto_key()
        aes = AESGCM(key)
        iv = os.urandom(12)
        ct_with_tag = aes.encrypt(iv, plain_text.encode("utf-8"), None)
        ct = ct_with_tag[:-16]
        tag = ct_with_tag[-16:]

        iv_b64 = base64.b64encode(iv).decode("ascii")
        ct_b64 = base64.b64encode(ct).decode("ascii")
        tag_b64 = base64.b64encode(tag).decode("ascii")
        return f"{ENVELOPE_PREFIX}{iv_b64}:{ct_b64}:{tag_b64}"
    except Exception:
        return plain_text

def decrypt_token(cipher_text: str) -> str:
    """Giải mã token từ chuỗi enc:v1:... (nếu là plaintext cũ thì trả về nguyên bản)."""
    if not cipher_text or not isinstance(cipher_text, str):
        return ""
    if not cipher_text.startswith(ENVELOPE_PREFIX):
        return cipher_text

    try:
        parts = cipher_text.split(":")
        if len(parts) != 5:
            return cipher_text
        _, _, iv_b64, ct_b64, tag_b64 = parts
        iv = base64.b64decode(iv_b64)
        ct = base64.b64decode(ct_b64)
        tag = base64.b64decode(tag_b64)

        key = get_crypto_key()
        aes = AESGCM(key)
        plain_bytes = aes.decrypt(iv, ct + tag, None)
        return plain_bytes.decode("utf-8")
    except Exception:
        return cipher_text

def encrypt_account_tokens(acc: dict) -> dict:
    """Mã hóa các trường token nhạy cảm trong đối tượng account."""
    if not isinstance(acc, dict):
        return acc
    cloned = dict(acc)
    if "accessToken" in cloned and cloned["accessToken"]:
        cloned["accessToken"] = encrypt_token(cloned["accessToken"])
    if "refreshToken" in cloned and cloned["refreshToken"]:
        cloned["refreshToken"] = encrypt_token(cloned["refreshToken"])
    return cloned

def decrypt_account_tokens(acc: dict) -> dict:
    """Giải mã các trường token nhạy cảm trong đối tượng account."""
    if not isinstance(acc, dict):
        return acc
    cloned = dict(acc)
    if "accessToken" in cloned and cloned["accessToken"]:
        cloned["accessToken"] = decrypt_token(cloned["accessToken"])
    if "refreshToken" in cloned and cloned["refreshToken"]:
        cloned["refreshToken"] = decrypt_token(cloned["refreshToken"])
    return cloned
