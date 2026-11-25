# -*- coding: utf-8 -*-
"""
Module quản lý chứng chỉ số SSL/TLS (launcher_cert.py).
Hỗ trợ sinh chứng chỉ tự ký (Root CA & Leaf), tạo bundle kết hợp (System + Root CA)
và cài đặt chứng chỉ Root CA vào Trust Store của hệ thống trên cả Windows và Linux.
"""

import os
import sys
import shutil
import subprocess

try:
    from launcher.launcher_paths import PROXY_DIR, ROOT_CA
except ImportError:
    from launcher_paths import PROXY_DIR, ROOT_CA

CERTS_DIR = os.path.dirname(ROOT_CA)
LEGACY_CERTS_DIR = os.path.join(PROXY_DIR, "certs")
COMBINED_CA_BUNDLE = os.path.join(CERTS_DIR, "ca-bundle.crt")


def ensure_certificates() -> bool:
    """Đảm bảo chứng chỉ Root CA (ca.crt, ca.key) đã được sinh hoặc di dời sang CONFIG_DIR."""
    ca_crt = ROOT_CA
    ca_key = os.path.join(CERTS_DIR, "ca.key")

    if os.path.exists(ca_crt) and os.path.exists(ca_key):
        return True

    os.makedirs(CERTS_DIR, exist_ok=True)
    legacy_crt = os.path.join(LEGACY_CERTS_DIR, "ca.crt")
    legacy_key = os.path.join(LEGACY_CERTS_DIR, "ca.key")
    if os.path.exists(legacy_crt) and os.path.exists(legacy_key) and os.path.abspath(LEGACY_CERTS_DIR) != os.path.abspath(CERTS_DIR):
        try:
            shutil.copy2(legacy_crt, ca_crt)
            shutil.copy2(legacy_key, ca_key)
            return True
        except Exception:
            pass

    provider_script = os.path.join(PROXY_DIR, "cert_provider.js")
    if not os.path.exists(provider_script):
        return False

    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        res = subprocess.run(
            ["node", provider_script, CERTS_DIR],
            cwd=PROXY_DIR,
            capture_output=True,
            text=True,
            creationflags=creationflags
        )
        return res.returncode == 0 and os.path.exists(ca_crt)
    except Exception as e:
        print(f"[ERROR] Không thể tự động sinh chứng chỉ qua Node.js: {e}", file=sys.stderr)
        return False


def ensure_combined_ca_bundle() -> str:
    """Tạo bundle kết hợp giữa các Root CA chuẩn của Mozilla (certifi) và Root CA nội bộ.
    
    Điều này giải quyết triệt để lỗi 'x509: certificate signed by unknown authority'
    khi ứng dụng (như Golang Cloud Code trong Antigravity) kết nối tới upstream Google
    (oauth2.googleapis.com) trong khi biến SSL_CERT_FILE được cấu hình.
    """
    ensure_certificates()

    if not os.path.exists(ROOT_CA):
        return ROOT_CA

    try:
        import certifi
        roots_pem = certifi.where()
        with open(roots_pem, "rb") as f_roots:
            roots_data = f_roots.read()

        with open(ROOT_CA, "rb") as f_ca:
            ca_data = f_ca.read()

        combined_data = roots_data.rstrip() + b"\n\n# Antigravity Local Root CA\n" + ca_data.strip() + b"\n"

        # Chỉ ghi đè nếu nội dung thay đổi hoặc file chưa tồn tại
        if not os.path.exists(COMBINED_CA_BUNDLE) or os.path.getsize(COMBINED_CA_BUNDLE) != len(combined_data):
            os.makedirs(CERTS_DIR, exist_ok=True)
            with open(COMBINED_CA_BUNDLE, "wb") as f_out:
                f_out.write(combined_data)

        return COMBINED_CA_BUNDLE
    except Exception:
        return ROOT_CA


def is_root_ca_installed() -> bool:
    """Kiểm tra xem Antigravity Root CA đã được thêm vào Trust Store của OS chưa."""
    if not os.path.exists(ROOT_CA):
        return False

    if sys.platform == "win32":
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            res = subprocess.run(
                ["certutil.exe", "-verifystore", "-user", "Root", "Antigravity Root CA"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags
            )
            return res.returncode == 0
        except Exception:
            return False
    else:
        # Linux
        system_targets = [
            "/usr/local/share/ca-certificates/antigravity-ca.crt",
            "/etc/ssl/certs/antigravity-ca.pem",
            "/etc/pki/ca-trust/source/anchors/antigravity-ca.crt"
        ]
        for t in system_targets:
            if os.path.exists(t):
                return True

        # Kiểm tra thêm NSS store (~/.pki/nssdb) nếu có certutil
        nssdb_dir = os.path.expanduser("~/.pki/nssdb")
        if os.path.exists(nssdb_dir) and shutil.which("certutil"):
            try:
                res = subprocess.run(
                    ["certutil", "-d", f"sql:{nssdb_dir}", "-L", "-n", "Antigravity Root CA"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if res.returncode == 0:
                    return True
            except Exception:
                pass

        return False


def install_root_ca() -> bool:
    """Cài đặt Antigravity Root CA vào Trust Store của hệ điều hành (Windows / Linux)."""
    ensure_certificates()
    ensure_combined_ca_bundle()

    if not os.path.exists(ROOT_CA):
        print(f"[ERROR] Không tìm thấy chứng chỉ: {ROOT_CA}")
        return False

    if is_root_ca_installed():
        print("[OK] Chứng chỉ 'Antigravity Root CA' đã được cài đặt trong Trust Store của hệ thống.")
        return True

    print(f"Đang cài đặt chứng chỉ Root CA: {ROOT_CA}")

    if sys.platform == "win32":
        try:
            print("Vui lòng xác nhận 'Yes' trên hộp thoại bảo mật của Windows nếu xuất hiện...")
            res = subprocess.run(
                ["certutil.exe", "-addstore", "-user", "Root", ROOT_CA],
                capture_output=True,
                text=True,
                timeout=15
            )
            if res.returncode == 0 or is_root_ca_installed():
                print("[OK] Đã cài đặt thành công Antigravity Root CA vào Windows Certificate Store (CurrentUser\\Root)!")
                return True
            else:
                print(f"[WARN] certutil trả về mã: {res.returncode}. Chi tiết: {res.stdout.strip() or res.stderr.strip()}")
                return False
        except subprocess.TimeoutExpired:
            print("[INFO] Quá thời gian chờ xác nhận hộp thoại Windows. Bundle chứng chỉ kết hợp (ca-bundle.crt) đã được tạo để đảm bảo Antigravity hoạt động.")
            return True
        except Exception as e:
            print(f"[ERROR] Lỗi khi cài đặt chứng chỉ trên Windows: {e}")
            return False
    else:
        # Linux
        installed_any = False

        # 1. User NSS DB (dành cho Chrome, Edge, Chromium, VS Code / Antigravity)
        nssdb_dir = os.path.expanduser("~/.pki/nssdb")
        os.makedirs(nssdb_dir, exist_ok=True)
        if shutil.which("certutil"):
            try:
                subprocess.run(["certutil", "-d", f"sql:{nssdb_dir}", "-N", "--empty-password"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                res = subprocess.run(
                    ["certutil", "-d", f"sql:{nssdb_dir}", "-A", "-t", "C,,", "-n", "Antigravity Root CA", "-i", ROOT_CA],
                    capture_output=True,
                    text=True
                )
                if res.returncode == 0:
                    print("[OK] Đã cài đặt Root CA vào thư viện NSS của người dùng (~/.pki/nssdb).")
                    installed_any = True
            except Exception:
                pass

        # 2. System CA Store
        if os.path.exists("/usr/local/share/ca-certificates") and shutil.which("update-ca-certificates"):
            try:
                target = "/usr/local/share/ca-certificates/antigravity-ca.crt"
                # Thử copy trực tiếp hoặc qua sudo nếu có quyền
                if os.access("/usr/local/share/ca-certificates", os.W_OK):
                    shutil.copy2(ROOT_CA, target)
                    subprocess.run(["update-ca-certificates"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    installed_any = True
                    print("[OK] Đã cài đặt Root CA vào /usr/local/share/ca-certificates.")
                else:
                    cmd = f"sudo cp '{ROOT_CA}' '{target}' && sudo update-ca-certificates"
                    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if os.path.exists(target):
                        installed_any = True
                        print("[OK] Đã cài đặt Root CA qua sudo update-ca-certificates.")
            except Exception:
                pass

        if not installed_any:
            print("[INFO] Bundle kết hợp (ca-bundle.crt) đã được chuẩn bị sẵn sàng cho runtime ứng dụng.")

        return True
