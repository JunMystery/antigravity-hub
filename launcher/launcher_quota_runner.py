# -*- coding: utf-8 -*-
"""
Module điều phối các tác vụ quét Quota ngầm và đếm ngược Cooldown cho Launcher Window.
"""

import time
import threading
import concurrent.futures
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from launcher_storage import MANUAL_COOLDOWN, load_accounts, save_data
from launcher_quota_fetcher import fetch_single_account_quota
from launcher_treeview import get_quota_btn_label

def start_refresh_cooldown(win, seconds=MANUAL_COOLDOWN):
    """Bắt đầu đếm ngược cooldown chống spam Google API."""
    win.cooldown_remaining = seconds
    win.btn_refresh_all.set_sensitive(False)
    win.btn_refresh_all.set_label(f"{seconds}s")
    GLib.timeout_add_seconds(1, lambda: cooldown_tick(win))

def cooldown_tick(win):
    """Mỗi giây giảm bộ đếm cooldown; mở lại nút khi hết thời gian chờ."""
    win.cooldown_remaining -= 1
    if win.cooldown_remaining <= 0:
        win.btn_refresh_all.set_label("⟳")
        win.btn_refresh_all.set_sensitive(True)
        return False
    win.btn_refresh_all.set_label(f"{win.cooldown_remaining}s")
    return True

def refresh_single_row_quota(win, path_str):
    """Quét Quota cho riêng một hàng tài khoản được chọn trong TreeView."""
    try:
        tree_iter = win.liststore.get_iter_from_string(path_str)
    except Exception:
        return
    prof_id = win.liststore.get_value(tree_iter, 14)
    prof_email = win.liststore.get_value(tree_iter, 3)
    win.liststore.set_value(tree_iter, 15, get_quota_btn_label(loading=True))

    def worker():
        accs = load_accounts()
        target_email = (prof_email or "").lower()
        matched_acc = next((a for a in accs if a.get("email", "").lower() == target_email or a.get("name", "").lower() == target_email), None)
        prof = next((p for p in win.data.get("profiles", []) if p.get("id") == prof_id), {})
        if matched_acc:
            q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid = fetch_single_account_quota(matched_acc, force=True, cached_info=prof)
        else:
            q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid = 0, "Không khớp", False, 0, "Không khớp", False

        def on_done():
            win._update_row_quota(prof_id, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid)
            for p in win.data.get("profiles", []):
                if p.get("id") == prof_id:
                    p["quota_5h_val"], p["quota_5h"], p["quota_5h_valid"] = q5_val, q5_text, q5_valid
                    p["quota_weekly_val"], p["quota_weekly"], p["quota_weekly_valid"] = qw_val, qw_text, qw_valid
                    p["quota_timestamp"] = int(time.time())
                    break
            save_data(win.data)
            for row in win.liststore:
                if row[14] == prof_id or row[3] == prof_email:
                    row[15] = get_quota_btn_label(loading=False)
                    break
            return False
        GLib.idle_add(on_done)
    threading.Thread(target=worker, daemon=True).start()

def refresh_all_quota(win, widget=None):
    """Quét Quota cho toàn bộ tài khoản bất đồng bộ với ThreadPool."""
    if win.cooldown_remaining > 0:
        return
    win.btn_refresh_all.set_sensitive(False)
    win.btn_refresh_all.set_label("...")
    start_refresh_cooldown(win, MANUAL_COOLDOWN)

    def worker():
        accs = load_accounts()
        profiles = win.data.get("profiles", [])
        acc_map = {a["email"].lower(): a for a in accs if a.get("email")}
        acc_map.update({a["name"].lower(): a for a in accs if a.get("name")})

        def query_profile(p):
            acc = acc_map.get((p.get("email") or "").lower()) or acc_map.get((p.get("name") or "").lower())
            if acc:
                q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid = fetch_single_account_quota(acc, force=True, cached_info=p)
            else:
                q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid = 0, "Không khớp", False, 0, "Không khớp", False
            return p["id"], q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(query_profile, profiles))

        def on_all_done():
            now = int(time.time())
            for pid, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid in results:
                win._update_row_quota(pid, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid)
                for p in win.data.get("profiles", []):
                    if p.get("id") == pid:
                        p["quota_5h_val"], p["quota_5h"], p["quota_5h_valid"] = q5_val, q5_text, q5_valid
                        p["quota_weekly_val"], p["quota_weekly"], p["quota_weekly_valid"] = qw_val, qw_text, qw_valid
                        p["quota_timestamp"] = now
                        break
            save_data(win.data)
            return False
        GLib.idle_add(on_all_done)
    threading.Thread(target=worker, daemon=True).start()

def auto_refresh_quota(win):
    """Tự động quét ngầm theo Cache TTL 3 phút (chỉ chạy khi không đang sửa TT)."""
    if getattr(win, "is_editing_order", False):
        return True

    def worker():
        accs = load_accounts()
        profiles = win.data.get("profiles", [])
        acc_map = {a["email"].lower(): a for a in accs if a.get("email")}
        acc_map.update({a["name"].lower(): a for a in accs if a.get("name")})

        def query_profile(p):
            acc = acc_map.get((p.get("email") or "").lower()) or acc_map.get((p.get("name") or "").lower())
            if acc:
                q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid = fetch_single_account_quota(acc, force=False, cached_info=p)
            else:
                q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid = 0, "Không khớp", False, 0, "Không khớp", False
            return p["id"], q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(query_profile, profiles))

        def on_done():
            now = int(time.time())
            for pid, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid in results:
                win._update_row_quota(pid, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid)
                for p in win.data.get("profiles", []):
                    if p.get("id") == pid:
                        p["quota_5h_val"], p["quota_5h"], p["quota_5h_valid"] = q5_val, q5_text, q5_valid
                        p["quota_weekly_val"], p["quota_weekly"], p["quota_weekly_valid"] = qw_val, qw_text, qw_valid
                        p["quota_timestamp"] = now
                        break
            save_data(win.data)
            return False
        GLib.idle_add(on_done)
    threading.Thread(target=worker, daemon=True).start()
    return True
