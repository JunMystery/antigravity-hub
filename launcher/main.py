#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity Launcher & Micro-Proxy Round Robin Coordinator.
Main entry point for GUI and CLI.
"""

import sys
import argparse

from launcher_cli import run_cli
from launcher_window import run_gui

def main():
    parser = argparse.ArgumentParser(description="Antigravity Profile Launcher & Round Robin Manager")
    parser.add_argument("--gui", action="store_true", help="Mở giao diện đồ họa Launcher (Mặc định)")
    parser.add_argument("--list", action="store_true", help="Liệt kê danh sách tài khoản hiện có")
    parser.add_argument("--add", metavar="NAME", help="Thêm tài khoản mới qua dòng lệnh")
    parser.add_argument("--add-google", action="store_true", help="Đăng nhập và thêm tài khoản Google mới qua OAuth 2.0 PKCE")
    parser.add_argument("--delete", metavar="ID_OR_NAME", help="Xóa tài khoản khỏi danh sách")
    parser.add_argument("--toggle", metavar="ID_OR_NAME", help="Bật/Tắt tham gia Round Robin cho tài khoản")
    parser.add_argument("--requests-per-account", type=int, metavar="N", help="Đặt số request trước khi chuyển tài khoản")
    parser.add_argument("--launch", metavar="ID_OR_NAME", help="Khởi chạy tài khoản theo tên hoặc ID")
    parser.add_argument("--start-proxy", action="store_true", help="Kích hoạt Micro-Proxy Round Robin")
    parser.add_argument("--stop-proxy", action="store_true", help="Dừng Micro-Proxy Round Robin")
    parser.add_argument("--refresh-quota", action="store_true", help="Truy vấn và cập nhật Quota cho toàn bộ tài khoản")
    parser.add_argument("--create-shortcut", action="store_true", help="Tạo Desktop Shortcut cho Antigravity Launcher")
    parser.add_argument("--install-cert", action="store_true", help="Cài đặt chứng chỉ Root CA vào Trust Store của hệ điều hành")
    parser.add_argument("--import-9router", action="store_true", help="Nhập danh sách tài khoản Google từ 9router SQLite")
    parser.add_argument("--proxy", dest="proxy", action="store_true", default=None, help="Chạy kèm Round Robin Proxy")
    parser.add_argument("--no-proxy", dest="proxy", action="store_false", help="Chạy không Proxy (Direct)")

    args = parser.parse_args()
    if args.create_shortcut:
        from launcher_shortcut import create_desktop_shortcut
        ok = create_desktop_shortcut()
        if ok:
            print("Đã tạo Desktop Shortcut thành công.")
        else:
            print("Tạo Desktop Shortcut thất bại.", file=sys.stderr)
        return

    if getattr(args, "install_cert", False):
        from launcher_cert import install_root_ca
        ok = install_root_ca()
        if not ok:
            sys.exit(1)
        return

    if args.list or args.add or args.add_google or args.delete or args.launch or args.toggle or args.requests_per_account or args.start_proxy or args.stop_proxy or args.refresh_quota or args.import_9router:
        run_cli(args)
    else:
        run_gui()

if __name__ == "__main__":
    main()
