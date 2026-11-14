# -*- coding: utf-8 -*-
"""
Module điều phối các tác vụ quét Quota ngầm và đếm ngược Cooldown cho Launcher Window (PyQt6).
Sử dụng QuotaSignalBridge (pyqtSignal) đảm bảo truyền dữ liệu đa luồng an toàn sang GUI thread.
"""

import time
import threading
import concurrent.futures
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from launcher_storage import MANUAL_COOLDOWN, load_accounts, save_data
from launcher_quota_fetcher import fetch_single_account_quota

class QuotaSignalBridge(QObject):
    """Cầu nối tín hiệu Qt truyền kết quả từ Worker thread sang Main GUI thread."""
    all_done_signal = pyqtSignal(list, int)
    single_done_signal = pyqtSignal(str, int, str, bool, int, str, bool)
    error_signal = pyqtSignal()

def ensure_bridge(win) -> QuotaSignalBridge:
    """Khởi tạo và kết nối các Slot nhận tín hiệu trên Main Window."""
    if not hasattr(win, "quota_bridge") or win.quota_bridge is None:
        bridge = QuotaSignalBridge()
        bridge.all_done_signal.connect(lambda results, now: handle_all_done(win, results, now))
        bridge.single_done_signal.connect(lambda pid, q5_v, q5_t, q5_ok, qw_v, qw_t, qw_ok: handle_single_done(win, pid, q5_v, q5_t, q5_ok, qw_v, qw_t, qw_ok))
        bridge.error_signal.connect(lambda: handle_error(win))
        win.quota_bridge = bridge
    return win.quota_bridge

SPINNER_FRAMES = ["◐", "◓", "◑", "◒"]

def start_spinner_animation(win):
    """Khởi động QTimer chạy hiệu ứng xoay spinner Unicode."""
    if not hasattr(win, "spinner_timer") or win.spinner_timer is None:
        win.spinner_timer = QTimer(win)
        win.spinner_timer.timeout.connect(lambda: spinner_tick(win))
    win.spinner_frame_idx = 0
    if not win.spinner_timer.isActive():
        win.spinner_timer.start(80)

def stop_spinner_animation(win):
    """Dừng QTimer hiệu ứng xoay spinner."""
    if hasattr(win, "spinner_timer") and win.spinner_timer and win.spinner_timer.isActive():
        win.spinner_timer.stop()

def spinner_tick(win):
    """Mỗi tick chuyển frame spinner tiếp theo cho nút làm mới và các hàng đang quét."""
    win.spinner_frame_idx = (getattr(win, "spinner_frame_idx", 0) + 1) % len(SPINNER_FRAMES)
    char = SPINNER_FRAMES[win.spinner_frame_idx]

    if getattr(win, "is_refreshing_quota", False) and hasattr(win, "btn_refresh_all"):
        win.btn_refresh_all.setText(char)

    from launcher_treeview import update_refreshing_spinners
    update_refreshing_spinners(win, char)

def handle_all_done(win, results, now):
    """Xử lý cập nhật toàn bộ Quota trên Main GUI Thread."""
    stop_spinner_animation(win)
    if hasattr(win, "refreshing_profile_ids"):
        win.refreshing_profile_ids.clear()

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

    start_refresh_cooldown(win, MANUAL_COOLDOWN)

def handle_single_done(win, pid, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid):
    """Xử lý cập nhật riêng lẻ Quota của một tài khoản trên Main GUI Thread."""
    if hasattr(win, "refreshing_profile_ids"):
        win.refreshing_profile_ids.discard(pid)
        if not win.refreshing_profile_ids and not getattr(win, "is_refreshing_quota", False):
            stop_spinner_animation(win)

    win._update_row_quota(pid, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid)
    prof_email = ""
    for p in win.data.get("profiles", []):
        if p.get("id") == pid:
            p["quota_5h_val"], p["quota_5h"], p["quota_5h_valid"] = q5_val, q5_text, q5_valid
            p["quota_weekly_val"], p["quota_weekly"], p["quota_weekly_valid"] = qw_val, qw_text, qw_valid
            p["quota_timestamp"] = int(time.time())
            prof_email = p.get("name") or p.get("email") or pid
            break
    save_data(win.data)
    if hasattr(win, "lbl_info"):
        win.lbl_info.setText(f"<b><span style='color:#a6e3a1;'>Đã làm mới Quota [{prof_email}] xong lúc {time.strftime('%H:%M:%S')}</span></b>")

def handle_error(win):
    """Xử lý khôi phục giao diện khi quá trình quét ngầm gặp ngoại lệ."""
    stop_spinner_animation(win)
    if hasattr(win, "refreshing_profile_ids"):
        win.refreshing_profile_ids.clear()
    win.is_refreshing_quota = False
    if hasattr(win, "btn_refresh_all"):
        win.btn_refresh_all.setEnabled(True)
        win.btn_refresh_all.setText("⟳")
    if hasattr(win, "lbl_info"):
        win.lbl_info.setText("<b><span style='color:#f38ba8;'>Quét Quota gặp lỗi. Vui lòng thử lại.</span></b>")

def get_quota_btn_label(loading: bool = False) -> str:
    """Trả về nhãn cho nút làm mới Quota trong hàng."""
    return "..." if loading else "⟳"

def start_refresh_cooldown(win, seconds=MANUAL_COOLDOWN):
    """Bắt đầu đếm ngược cooldown chống spam Google API."""
    stop_spinner_animation(win)
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
    if prof_id in getattr(win, "refreshing_profile_ids", set()):
        return

    prof = next((p for p in win.data.get("profiles", []) if p.get("id") == prof_id), None)
    if not prof:
        return
    prof_email = prof.get("email", "")
    bridge = ensure_bridge(win)

    from launcher_treeview import mark_single_row_refreshing
    mark_single_row_refreshing(win, prof_id, SPINNER_FRAMES[0])
    start_spinner_animation(win)

    def worker():
        try:
            accs = load_accounts()
            target_email = (prof_email or "").lower()
            matched_acc = next((a for a in accs if a.get("email", "").lower() == target_email or a.get("name", "").lower() == target_email or a.get("id") == prof_id), None)
            if matched_acc:
                q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid = fetch_single_account_quota(matched_acc, force=True, cached_info=prof)
            else:
                q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid = 0, "Không khớp", False, 0, "Không khớp", False
            bridge.single_done_signal.emit(prof_id, q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid)
        except Exception:
            bridge.error_signal.emit()

    threading.Thread(target=worker, daemon=True).start()

def refresh_all_quota(win, widget=None):
    """Quét Quota cho toàn bộ tài khoản bất đồng bộ với Multi-signal Visual Feedback."""
    if getattr(win, "is_refreshing_quota", False) or getattr(win, "cooldown_remaining", 0) > 0:
        return

    profiles = win.data.get("profiles", [])
    if not profiles:
        return

    win.is_refreshing_quota = True
    bridge = ensure_bridge(win)

    if hasattr(win, "btn_refresh_all"):
        win.btn_refresh_all.setEnabled(False)
        win.btn_refresh_all.setText(SPINNER_FRAMES[0])

    from launcher_treeview import mark_all_rows_refreshing
    mark_all_rows_refreshing(win, SPINNER_FRAMES[0])
    start_spinner_animation(win)

    if hasattr(win, "lbl_info"):
        win.lbl_info.setText(f"<b><span style='color:#89b4fa;'>Đang làm mới Quota cho {len(profiles)} tài khoản...</span></b>")

    def worker():
        try:
            accs = load_accounts()
            acc_map = {a["email"].lower(): a for a in accs if a.get("email")}
            acc_map.update({a["name"].lower(): a for a in accs if a.get("name")})

            def query_profile(p):
                acc = acc_map.get((p.get("email") or "").lower()) or acc_map.get((p.get("name") or "").lower())
                if not acc:
                    acc = next((a for a in accs if a.get("id") == p.get("id")), None)
                if acc:
                    q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid = fetch_single_account_quota(acc, force=True, cached_info=p)
                else:
                    q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid = 0, "Không khớp", False, 0, "Không khớp", False
                return p["id"], q5_val, q5_text, q5_valid, qw_val, qw_text, qw_valid

            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                results = list(executor.map(query_profile, profiles))

            now = int(time.time())
            bridge.all_done_signal.emit(results, now)
        except Exception:
            bridge.error_signal.emit()

    threading.Thread(target=worker, daemon=True).start()

def auto_refresh_quota(win):
    """Tự động quét ngầm theo Cache TTL 3 phút (chỉ chạy khi không đang chỉnh sửa)."""
    if getattr(win, "is_editing_order", False) or getattr(win, "is_refreshing_quota", False):
        return
    refresh_all_quota(win)
