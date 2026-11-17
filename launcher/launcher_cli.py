# -*- coding: utf-8 -*-
"""
Module xử lý giao diện dòng lệnh (CLI) cho Antigravity Launcher.
"""

import os
import sys
import time
import json
import re
import webbrowser
import shutil
import subprocess
import urllib.request
import concurrent.futures
from datetime import datetime

from launcher_storage import (
    load_data, save_data, load_accounts, PROFILES_BASE_DIR
)
from launcher_proxy import (
    is_proxy_running, stop_proxy, ensure_proxy_running, launch_profile
)
from launcher_quota_fetcher import fetch_single_account_quota

def run_cli(args):
    """Điều hướng và thực thi các tham số dòng lệnh CLI."""
    data = load_data()
    profiles = data.get("profiles", [])

    if args.backup is not None:
        from launcher_backup import create_backup
        target_path = args.backup if args.backup else None
        ok, msg = create_backup(target_path)
        if ok:
            print(f"[OK] Đã tạo bản sao lưu thành công tại: {msg}")
        else:
            print(f"[ERROR] Sao lưu thất bại: {msg}", file=sys.stderr)
        return

    if args.restore:
        from launcher_backup import restore_backup
        mode = getattr(args, "restore_mode", "replace") or "replace"
        ok, msg = restore_backup(args.restore, mode=mode)
        if ok:
            print(f"[OK] {msg}")
        else:
            print(f"[ERROR] {msg}", file=sys.stderr)
        return

    if getattr(args, "install_cert", False):
        from launcher_cert import install_root_ca
        install_root_ca()
        return

    if args.start_proxy:
        ensure_proxy_running()
        print("Đã kích hoạt Micro-Proxy Round Robin (127.0.0.1:20130).")
        return

    if args.stop_proxy:
        stop_proxy()
        print("Đã dừng Micro-Proxy Round Robin.")
        return

    if args.refresh_quota:
        print("Đang truy vấn Quota Gemini cho toàn bộ tài khoản...")
        accs = load_accounts()
        acc_map = {}
        for a in accs:
            if a.get("email"):
                acc_map[a["email"].lower()] = a
            if a.get("name"):
                acc_map[a["name"].lower()] = a

        def query_profile(p):
            target_email = (p.get("email") or "").lower()
            target_name = (p.get("name") or "").lower()
            acc = acc_map.get(target_email) or acc_map.get(target_name)
            if acc:
                q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid = fetch_single_account_quota(acc, force=True, cached_info=p)
            else:
                q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid = 0, "Không khớp", False, 0, "Không khớp", False
            return p, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(query_profile, profiles))

        now = int(time.time())
        for p, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid in results:
            p["quota_5h_val"] = q5_val
            p["quota_5h"] = q5_text
            p["quota_5h_valid"] = q5_valid
            p["quota_weekly_val"] = qw_val
            p["quota_weekly"] = qw_text
            p["quota_weekly_valid"] = qw_valid
            p["quota_timestamp"] = now
            print(f" - {p.get('name')} ({p.get('email')}): 5h={q5_text}, Weekly={qw_text}")

        save_data(data)
        print("Hoàn tất cập nhật Quota.")
        return

    if args.list:
        if not profiles:
            print("Chưa có tài khoản nào. Sử dụng --add-google để thêm tài khoản.")
            return
        reqs = data.get("settings", {}).get("requests_per_account", 1)
        print(f"Ngưỡng chuyển đổi Round Robin: {reqs} request/tài khoản")
        print(f"{'STT':<5} {'ACTIVE':<8} {'TÀI KHOẢN EMAIL':<28} {'QUOTA 5H':<10} {'QUOTA TUẦN':<12} {'THƯ MỤC PROFILE'}")
        print("-" * 95)
        for idx, p in enumerate(profiles):
            ord_str = f"#{p.get('order', idx + 1)}"
            act = "[x]" if p.get("enabled", True) else "[ ]"
            q5 = p.get("quota_5h", "--")
            qw = p.get("quota_weekly", "--")
            email = p.get("email") or p.get("name") or ""
            data_dir = os.path.basename(p.get("data_dir", "")) or p.get("id", "")
            print(f"{ord_str:<5} {act:<8} {email:<28} {q5:<10} {qw:<12} {data_dir}")
        return

    if args.requests_per_account:
        val = max(1, args.requests_per_account)
        data.setdefault("settings", {})
        data["settings"]["requests_per_account"] = val
        save_data(data)
        print(f"Đã cập nhật ngưỡng Round Robin: {val} request/tài khoản")
        return

    if args.toggle:
        target = args.toggle.strip().lower()
        found = False
        for p in profiles:
            if p.get("id").lower() == target or p.get("name").lower() == target or p.get("email", "").lower() == target:
                p["enabled"] = not p.get("enabled", True)
                found = True
                status = "BẬT" if p["enabled"] else "TẮT"
                print(f"Đã {status} Round Robin cho tài khoản: '{p.get('email', p.get('name'))}'")
                break
        if not found:
            print(f"Không tìm thấy tài khoản: {target}")
            return
        save_data(data)
        return

    if args.add:
        email = args.add.strip()
        safe_slug = email.lower().replace("@", "_").replace(".", "_")
        safe_slug = re.sub(r'[^a-z0-9_]', '', safe_slug)
        existing_ids = {p.get("id") for p in profiles}
        base_slug = safe_slug
        c = 1
        while safe_slug in existing_ids:
            safe_slug = f"{base_slug}_{c}"
            c += 1
        data_dir = os.path.join(PROFILES_BASE_DIR, safe_slug)
        new_profile = {
            "id": safe_slug,
            "name": email,
            "email": email,
            "order": len(profiles) + 1,
            "enabled": True,
            "data_dir": data_dir,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "quota_5h_val": 0,
            "quota_5h": "--",
            "quota_5h_valid": False,
            "quota_weekly_val": 0,
            "quota_weekly": "--",
            "quota_weekly_valid": False,
            "quota_timestamp": 0
        }
        profiles.append(new_profile)
        data["profiles"] = profiles
        save_data(data)
        print(f"Đã thêm tài khoản: '{email}' (Thư mục: {data_dir})")
        return

    if args.delete:
        target = args.delete.strip().lower()
        found = False
        new_profiles = []
        for p in profiles:
            if p.get("id", "").lower() == target or (p.get("email") and p.get("email").lower() == target) or (p.get("name") and p.get("name").lower() == target):
                found = True
                print(f"Đã gỡ tài khoản: '{p.get('email', p.get('name'))}' ({p.get('data_dir')} vẫn được giữ an toàn)")
            else:
                new_profiles.append(p)
        if not found:
            print(f"Không tìm thấy tài khoản: {target}")
            return
        for idx, p in enumerate(new_profiles):
            p["order"] = idx + 1
        data["profiles"] = new_profiles
        save_data(data)
        return

    if args.launch:
        target = args.launch.strip().lower()
        matched = None
        for p in profiles:
            if p.get("id", "").lower() == target or (p.get("email") and p.get("email").lower() == target) or (p.get("name") and p.get("name").lower() == target):
                matched = p
                break
        if not matched:
            print(f"Không tìm thấy tài khoản: '{target}'. Danh sách hiện có:")
            for p in profiles:
                print(f" - {p.get('email', p.get('name'))} (Thư mục: {p.get('data_dir')})")
            return

        use_proxy = args.proxy if args.proxy is not None else data.get("settings", {}).get("use_proxy", True)
        print(f"Khởi chạy Antigravity cho tài khoản '{matched.get('email', matched.get('name'))}'...")
        print(f"Thư mục: {matched['data_dir']}")
        print(f"Round Robin Proxy: {'BẬT (Port 20130)' if use_proxy else 'TẮT (Direct)'}")
        launch_profile(matched["data_dir"], use_proxy)
        return

    if args.add_google:
        ensure_proxy_running()
        try:
            req = urllib.request.Request("http://127.0.0.1:20130/_oauth/start")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            auth_url = data.get("authUrl")
            state = data.get("state")
        except Exception as e:
            print(f"Lỗi kết nối Micro-Proxy: {e}", file=sys.stderr)
            return

        print("\n" + "=" * 62)
        print("[AUTH] ĐĂNG NHẬP GOOGLE OAUTH 2.0")
        print("=" * 62)
        print("1. Đang mở trình duyệt xác thực Google...")
        webbrowser.open(auth_url)
        print(f"   Nếu trình duyệt không tự mở, hãy truy cập link sau:\n   {auth_url}\n")
        print("2. Hoàn tất cấp quyền trên trình duyệt.")
        print("   (Micro-Proxy đang tự động bắt callback trên http://localhost:20130/oauth/callback)")
        print("\n[...] Đang đợi callback xác thực (hoặc nhấn Ctrl+C để hủy)...")

        accs_before = len(load_accounts())
        start_t = time.time()
        while time.time() - start_t < 180:
            time.sleep(1)
            accs_now = load_accounts()
            if len(accs_now) > accs_before:
                new_acc = accs_now[-1]
                print("\n" + "=" * 62)
                print(f"[OK] ĐĂNG NHẬP THÀNH CÔNG: {new_acc.get('email')} ({new_acc.get('name')})")
                print(f"   Project ID: {new_acc.get('projectId', 'N/A')}")
                print(f"   Đã lưu vào accounts.json và profiles.json.")
                print("=" * 62 + "\n")
                print("Đang cập nhật Quota ban đầu...")
                launcher_cmd = shutil.which("antigravity-launcher") or sys.argv[0]
                cmd = [sys.executable, launcher_cmd, "--refresh-quota"] if launcher_cmd.endswith(".py") else [launcher_cmd, "--refresh-quota"]
                subprocess.run(cmd)
                return

        print("Hết thời gian chờ (3 phút). Vui lòng thử lại.")
        return
