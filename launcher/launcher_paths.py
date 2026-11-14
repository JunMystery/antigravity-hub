# -*- coding: utf-8 -*-
"""
Module quản lý đường dẫn tệp tin, dò tìm nhị phân và chứng chỉ cho Antigravity Launcher.
Hỗ trợ đa nền tảng Windows, Linux và macOS.
"""

import os
import sys
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROXY_DIR = os.path.join(BASE_DIR, "proxy")
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
ASSET_ICO = os.path.join(ASSETS_DIR, "Antigravity.ico")
ASSET_PNG = os.path.join(ASSETS_DIR, "Antigravity.png")

def get_config_dir() -> str:
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return os.path.join(os.environ["APPDATA"], "antigravity-launcher")
    return os.path.expanduser("~/.config/antigravity-launcher")

def get_profiles_base_dir() -> str:
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return os.path.join(os.environ["APPDATA"], "Antigravity-Profiles")
    return os.path.expanduser("~/.config/Antigravity-Profiles")

CONFIG_DIR = get_config_dir()
PROFILES_FILE = os.path.join(CONFIG_DIR, "profiles.json")
ACCOUNTS_FILE = os.path.join(CONFIG_DIR, "accounts.json")
PROFILES_BASE_DIR = get_profiles_base_dir()

def find_app_binary() -> str:
    """Tự động dò tìm executable Antigravity trên máy tính người dùng."""
    if os.environ.get("ANTIGRAVITY_BIN") and os.path.exists(os.environ["ANTIGRAVITY_BIN"]):
        return os.environ["ANTIGRAVITY_BIN"]

    if sys.platform == "win32":
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Antigravity\Antigravity.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Antigravity\Antigravity.exe"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        which_exe = shutil.which("Antigravity.exe") or shutil.which("antigravity.exe")
        return which_exe or candidates[0]

    which_bin = shutil.which("antigravity")
    if which_bin:
        return which_bin
    candidates = [
        os.path.expanduser("~/Applications/Antigravity-x64/antigravity"),
        os.path.expanduser("~/Applications/Antigravity/antigravity"),
        "/opt/Antigravity/antigravity",
        "/usr/local/bin/antigravity"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return os.path.expanduser("~/Applications/Antigravity-x64/antigravity")

APP_BINARY = find_app_binary()

def find_ide_binary() -> str:
    """Tự động dò tìm Antigravity IDE (VS Code Code Editor) trên máy tính."""
    if os.environ.get("ANTIGRAVITY_IDE_BIN") and os.path.exists(os.environ["ANTIGRAVITY_IDE_BIN"]):
        return os.environ["ANTIGRAVITY_IDE_BIN"]

    if sys.platform == "win32":
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Antigravity IDE\Antigravity.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Antigravity IDE\Antigravity.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        which_ide = shutil.which("antigravity-ide.exe") or shutil.which("code.cmd") or shutil.which("code.exe")
        return which_ide or ""

    which_ide = shutil.which("antigravity-ide") or shutil.which("code")
    if which_ide:
        return which_ide
    candidates = [
        os.path.expanduser("~/.local/share/programs/antigravity-ide/antigravity-ide"),
        "/opt/antigravity-ide/antigravity-ide",
        "/usr/local/bin/antigravity-ide",
        "/usr/bin/code"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return ""

IDE_BINARY = find_ide_binary()

def get_app_binary(data=None) -> str:
    if data and data.get("settings", {}).get("app_binary"):
        return data["settings"]["app_binary"]
    return APP_BINARY

def get_ide_binary(data=None) -> str:
    if data and data.get("settings", {}).get("ide_binary"):
        return data["settings"]["ide_binary"]
    return find_ide_binary()

def find_app_icon(bin_path=None, preferred_ext=None) -> str:
    """Tìm icon ứng dụng từ thư mục assets nội bộ hoặc từ binary."""
    if preferred_ext == "ico" and os.path.exists(ASSET_ICO):
        return ASSET_ICO
    if preferred_ext == "png" and os.path.exists(ASSET_PNG):
        return ASSET_PNG
    if sys.platform == "win32" and os.path.exists(ASSET_ICO):
        return ASSET_ICO
    if os.path.exists(ASSET_PNG):
        return ASSET_PNG
    if os.path.exists(ASSET_ICO):
        return ASSET_ICO
    if bin_path:
        d = os.path.dirname(bin_path)
        for icon_name in ("Antigravity.png", "Antigravity.ico", "icon.png"):
            p = os.path.join(d, icon_name)
            if os.path.exists(p):
                return p
    return os.path.join(BASE_DIR, "icon.png")

APP_ICON = find_app_icon(APP_BINARY)

def get_proxy_script_path() -> str:
    """Xác định đường dẫn kịch bản Micro-Proxy tương đối theo repo."""
    bundled = os.path.join(PROXY_DIR, "index.js")
    if os.path.exists(bundled):
        return bundled
    custom = os.path.expanduser("~/.config/antigravity-launcher/proxy/index.js")
    return custom if os.path.exists(custom) else bundled

def get_root_ca_path() -> str:
    """Xác định đường dẫn chứng chỉ Root CA tương đối theo repo."""
    return os.path.join(PROXY_DIR, "certs", "ca.crt")

ROOT_CA = get_root_ca_path()
PROXY_SCRIPT = get_proxy_script_path()
PROXY_PORT = 20130
PID_FILE = os.path.join(CONFIG_DIR, "proxy.pid")
LAUNCHED_APPS_FILE = os.path.join(CONFIG_DIR, "launched_apps.json")

CACHE_TTL = 180           # 3 phút cache cho mỗi tài khoản
MANUAL_COOLDOWN = 30      # 30 giây cooldown sau khi bấm nút làm mới thủ công

DEFAULT_CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
DEFAULT_CLIENT_SECRET = "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"
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", DEFAULT_CLIENT_ID)
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", DEFAULT_CLIENT_SECRET)
USER_AGENT = "antigravity/hub/2.24.0 linux/x64"

PROXY_PAC = (
    "data:application/x-ns-proxy-autoconfig;base64,"
    "ZnVuY3Rpb24gRmluZFByb3h5Rm9yVVJMKHVybCwgaG9zdCkgewogICAgaWYgKGhvc3QgPT09ICdkYWlseS1jbG91ZGNvZGUtcGEuZ29vZ2xlYXBpcy5jb20nIHx8IGhvc3QgPT09ICdjbG91ZGNvZGUtcGEuZ29vZ2xlYXBpcy5jb20nIHx8IGhvc3QgPT09ICdjbG91ZGFpY29tcGFuaW9uLmdvb2dsZWFwaXMuY29tJyB8fCBob3N0ID09PSAnZ2VuZXJhdGl2ZWxhbmd1YWdlLmdvb2dsZWFwaXMuY29tJyB8fCBob3N0LmluZGV4T2YoJ2Nsb3VkY29kZScpICE9PSAtMSB8fCBob3N0LmluZGV4T2YoJ2NvbXBhbmlvbicpICE9PSAtMSB8fCBob3N0LmluZGV4T2YoJ2dlbmVyYXRpdmVsYW5ndWFnZScpICE9PSAtMSB8fCB1cmwuaW5kZXhPZignY2xvdWRjb2RlJykgIT09IC0xIHx8IHVybC5pbmRleE9mKCdnZW5lcmF0aXZlbGFuZ3VhZ2UnKSAhPT0gLTEgfHwgdXJsLmluZGV4T2YoJ2Nsb3VkYWljb21wYW5pb24nKSAhPT0gLTEpIHsKICAgICAgICByZXR1cm4gJ1BST1hZIDEyNy4wLjAuMToyMDEzMDsgRElSRUNUJzsKICAgIH0KICAgIHJldHVybiAnRElSRUNUJzsKfQ=="
)

def get_certificate_spki_fingerprint(cert_path: str) -> str:
    """Trích xuất mã băm SPKI SHA-256 Base64 của chứng chỉ cho Chromium pinning."""
    if not cert_path or not os.path.exists(cert_path):
        return ""
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        import hashlib, base64
        with open(cert_path, "rb") as f:
            c = x509.load_pem_x509_certificate(f.read())
        der = c.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        return base64.b64encode(hashlib.sha256(der).digest()).decode("ascii")
    except Exception:
        pass
    try:
        import subprocess, hashlib, base64
        r1 = subprocess.run(["openssl", "x509", "-in", cert_path, "-pubkey", "-noout"], capture_output=True, text=True, check=True)
        r2 = subprocess.run(["openssl", "pkey", "-pubin", "-outform", "der"], input=r1.stdout.encode(), capture_output=True, check=True)
        return base64.b64encode(hashlib.sha256(r2.stdout).digest()).decode("ascii")
    except Exception:
        return ""
