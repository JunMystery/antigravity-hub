# -*- coding: utf-8 -*-
"""
Module điều phối các tác vụ quét Quota ngầm và đếm ngược Cooldown cho Launcher Window (PyQt6).
"""

import time
import threading
import concurrent.futures
from PyQt6.QtCore import QTimer

from launcher_storage import MANUAL_COOLDOWN, load_accounts, save_data
from launcher_quota_fetcher import fetch_single_account_quota

def get_quota_btn_label(loading: bool = False) -> str:
    """Trả về nhãn cho nút làm mới Quota trong hàng."""
    return "..." if loading else "⟳"

def start_refresh_cooldown(win, seconds=MANUAL_COOLDOWN):
    """Bắt đầu đếm ngược cooldown chống spam Google API."""
    win.cooldown_remaining = seconds
    if hasattr(win, "btn_refresh_all"):
        win.btn_refresh_all.setEnabled(False)
        win.btn_refresh_all.setText(f"{seconds}s")
    QTimer.singleShot(1000, lambda: cooldown_tick(win))

def cooldown_tick(win):
    """Mỗi giây giảm bộ đếm cooldown; mở lại nút khi hết thời gian chờ."""
    win.cooldown_remaining -= 1
    if win.cooldown_remaining <= 0:
        if hasattr(win, "btn_refresh_all"):
            win.btn_refresh_all.setText("⟳")
            win.btn_refresh_all.setEnabled(True)
        return
    if hasattr(win, "btn_refresh_all"):
        win.btn_refresh_all.setText(f"{win.cooldown_remaining}s")
    QTimer.singleShot(1000, lambda: cooldown_tick(win))

def refresh_single_row_quota(win, prof_id):
    """Quét Quota cho riêng một tài khoản được chọn."""
    prof = next((p for p in win.data.get("profiles", []) if p.get("id") == prof_id), None)
    if not prof:
        return
    prof_email = prof.get("email", "")

    # Đánh dấu ô Quota của hàng này sang trạng thái đang quét
    if hasattr(win, "mark_single_row_refreshing"):
        win.mark_single_row_refreshing(prof_id)
    else:
        from launcher_treeview import mark_single_row_refreshing
        mark_single_row_refreshing(win, prof_id)

    def worker():
        accs = load_accounts()
        target_email = (prof_email or "").lower()
        matched_acc = next((a for a in accs if a.get("email", "").lower() == target_email or a.get("name", "").lower() == target_email), None)
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
            if hasattr(win, "lbl_info"):
                win.lbl_info.setText(f"<b><span style='color:#a6e3a1;'>Đã làm mới Quota tài khoản {prof_email} lúc {time.strftime('%H:%M:%S')}</span></b>")
        QTimer.singleShot(0, on_done)
    threading.Thread(target=worker, daemon=True).start()

def refresh_all_quota(win, widget=None):
    """Quét Quota cho toàn bộ tài khoản bất đồng bộ với Multi-signal Visual Feedback."""
    if getattr(win, "is_refreshing_quota", False) or win.cooldown_remaining > 0:
        return

    profiles = win.data.get("profiles", [])
    if not profiles:
        return

    win.is_refreshing_quota = True

    # 1. Cập nhật nút bấm sang 'Đang quét...'
    if hasattr(win, "btn_refresh_all"):
        win.btn_refresh_all.setEnabled(False)
        win.btn_refresh_all.setText("Đang quét...")

    # 2. Cập nhật các ô trong bảng sang 'Đang quét...'
    from launcher_treeview import mark_all_rows_refreshing
    mark_all_rows_refreshing(win)

    # 3. Cập nhật thanh trạng thái
    if hasattr(win, "lbl_info"):
        win.lbl_info.setText(f"<b><span style='color:#89b4fa;'>Đang làm mới Quota cho {len(profiles)} tài khoản...</span></b>")

    def worker():
        try:
            accs = load_accounts()
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

                win.is_refreshing_quota = False
                if hasattr(win, "lbl_info"):
                    win.lbl_info.setText(f"<b><span style='color:#a6e3a1;'>Đã làm mới Quota {len(results)} tài khoản xong lúc {time.strftime('%H:%M:%S')}</span></b>")

                # Chỉ bắt đầu đếm ngược Cooldown SAU KHI toàn bộ truy vấn hoàn tất
                start_refresh_cooldown(win, MANUAL_COOLDOWN)
            QTimer.singleShot(0, on_all_done)
        except Exception:
            def on_err():
                win.is_refreshing_quota = False
                if hasattr(win, "btn_refresh_all"):
                    win.btn_refresh_all.setEnabled(True)
                    win.btn_refresh_all.setText("⟳")
            QTimer.singleShot(0, on_err)
    threading.Thread(target=worker, daemon=True).start()

def auto_refresh_quota(win):
    """Tự động quét ngầm theo Cache TTL 3 phút (chỉ chạy khi không đang chỉnh sửa)."""
    if getattr(win, "is_editing_order", False):
        return

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
        QTimer.singleShot(0, on_done)
    threading.Thread(target=worker, daemon=True).start()
