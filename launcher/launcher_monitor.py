# -*- coding: utf-8 -*-
"""
Module xây dựng và cập nhật khung giám sát thời gian thực (Realtime Monitor) cho Antigravity Launcher.
"""

import os
import time
import json
import urllib.request
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from launcher_storage import CONFIG_DIR, PROXY_PORT
from launcher_proxy import is_proxy_running

def build_monitor_frame(win):
    """Xây dựng Gtk.Frame giám sát thời gian thực cho Launcher Window."""
    monitor_frame = Gtk.Frame()
    monitor_frame.set_label(" [MONITOR] THEO DÕI REALTIME ROUND ROBIN ")
    monitor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    monitor_box.set_margin_top(8)
    monitor_box.set_margin_bottom(8)
    monitor_box.set_margin_start(12)
    monitor_box.set_margin_end(12)

    proxy_ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    win.lbl_proxy_status = Gtk.Label()
    win.lbl_proxy_status.set_xalign(0)
    proxy_ctrl_box.pack_start(win.lbl_proxy_status, True, True, 0)

    win.btn_next_account = Gtk.Button.new_with_label("[>>] Chuyển tiếp")
    win.btn_next_account.set_tooltip_text("Chủ động chuyển ngay sang tài khoản tiếp theo trong Round Robin")
    win.btn_next_account.connect("clicked", win.on_manual_next_account)
    win.btn_next_account.get_style_context().add_class("suggested-action")
    proxy_ctrl_box.pack_end(win.btn_next_account, False, False, 0)

    win.btn_proxy_ctrl = Gtk.Button()
    win.btn_proxy_ctrl.connect("clicked", win.on_toggle_proxy_btn)
    proxy_ctrl_box.pack_end(win.btn_proxy_ctrl, False, False, 0)
    monitor_box.pack_start(proxy_ctrl_box, False, False, 2)

    win.lbl_live_account = Gtk.Label()
    win.lbl_live_account.set_markup("<span color='#888888'>○</span> <b>Tài khoản gửi:</b> <span color='#888888'>Chờ request từ Antigravity...</span>")
    win.lbl_live_account.set_xalign(0)
    monitor_box.pack_start(win.lbl_live_account, False, False, 0)

    win.lbl_live_stats = Gtk.Label()
    win.lbl_live_stats.set_markup("<b>Lượt thực hiện trên Round Robin:</b> 0 / 1 request | <b>Tổng request:</b> 0")
    win.lbl_live_stats.set_xalign(0)
    monitor_box.pack_start(win.lbl_live_stats, False, False, 0)

    win.live_progress = Gtk.ProgressBar()
    win.live_progress.set_fraction(0.0)
    monitor_box.pack_start(win.live_progress, False, False, 2)

    win.hold_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    win.hold_box.set_no_show_all(True)

    win.lbl_hold_alert = Gtk.Label()
    win.lbl_hold_alert.set_xalign(0)
    win.hold_box.pack_start(win.lbl_hold_alert, False, False, 0)

    hold_btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    win.btn_hold_retry = Gtk.Button.new_with_label("[Retry] Thử lại tài khoản này")
    win.btn_hold_retry.connect("clicked", lambda w: send_proxy_cmd(win, "retry"))
    hold_btn_row.pack_start(win.btn_hold_retry, False, False, 0)

    win.btn_hold_next = Gtk.Button.new_with_label("[>>] Chuyển tiếp")
    win.btn_hold_next.connect("clicked", lambda w: send_proxy_cmd(win, "next"))
    win.btn_hold_next.get_style_context().add_class("suggested-action")
    hold_btn_row.pack_start(win.btn_hold_next, False, False, 0)

    win.hold_box.pack_start(hold_btn_row, False, False, 2)
    monitor_box.pack_start(win.hold_box, False, False, 4)

    monitor_frame.add(monitor_box)
    return monitor_frame

def send_proxy_cmd(win, cmd: str):
    """Gửi lệnh điều khiển (retry, next) tới Micro-Proxy qua IPC và HTTP."""
    cmd_file = os.path.join(CONFIG_DIR, "proxy_cmd.json")
    try:
        with open(cmd_file, "w", encoding="utf-8") as f:
            json.dump({"cmd": cmd, "timestamp": time.time()}, f)
    except Exception:
        pass
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PROXY_PORT}/_proxy_action?cmd={cmd}")
        urllib.request.urlopen(req, timeout=0.8)
    except Exception:
        pass
    update_monitor_view(win)

def update_monitor_view(win):
    """Cập nhật dữ liệu hiển thị realtime cho khung Monitor."""
    if getattr(win, "is_editing_order", False):
        return True

    proxy_active = is_proxy_running()
    if hasattr(win, "btn_next_account"):
        win.btn_next_account.set_sensitive(proxy_active)

    if proxy_active:
        win.btn_proxy_ctrl.set_label("[Stop] Dừng")
        win.btn_proxy_ctrl.get_style_context().remove_class("suggested-action")
        win.btn_proxy_ctrl.get_style_context().add_class("destructive-action")
        win.lbl_proxy_status.set_markup("<b>Trạng thái:</b> <span color='#2ecc71'>● Proxy đang chạy (127.0.0.1:20130)</span>")
    else:
        win.btn_proxy_ctrl.set_label("[Start] Chạy")
        win.btn_proxy_ctrl.get_style_context().remove_class("destructive-action")
        win.btn_proxy_ctrl.get_style_context().add_class("suggested-action")
        win.lbl_proxy_status.set_markup("<b>Trạng thái:</b> <span color='#e74c3c'>○ Proxy đã dừng</span>")
        win.lbl_live_account.set_markup(
            "<span color='#888888'>○</span> <b>Tài khoản gửi:</b> <span color='#888888'>Proxy chưa kích hoạt. Nhấn 'Chạy' để bắt đầu.</span>"
        )
        win.lbl_live_stats.set_markup("<b>Lượt thực hiện trên Round Robin:</b> 0 / 1 request | <b>Tổng request:</b> 0")
        win.live_progress.set_fraction(0.0)
        if hasattr(win, "hold_box"):
            win.hold_box.hide()
        return True

    status_file = os.path.join(CONFIG_DIR, "live_status.json")
    if not os.path.exists(status_file):
        win.lbl_live_account.set_markup("<span color='#888888'>○</span> <b>Tài khoản gửi:</b> <span color='#888888'>Chờ request từ Antigravity...</span>")
        win.lbl_live_stats.set_markup("<b>Lượt thực hiện trên Round Robin:</b> 0 / 1 request | <b>Tổng request:</b> 0")
        win.live_progress.set_fraction(0.0)
        if hasattr(win, "hold_box"):
            win.hold_box.hide()
        return True

    try:
        with open(status_file, "r", encoding="utf-8") as f:
            st = json.load(f)

        ts = st.get("timestamp", 0) / 1000.0
        now = time.time()
        is_recent = (now - ts) < 3.5

        acc_email = st.get("account_email", "N/A")
        current_req = st.get("current_req", 0)
        reqs_per_acc = max(1, st.get("requests_per_account", 1))
        total_reqs = st.get("total_requests", 0)
        endpoint = st.get("endpoint", "")
        method = st.get("method", "")
        status = st.get("status", "idle")
        is_active = st.get("active", False)

        if status == "HOLD":
            err_acc = st.get("error_account", acc_email)
            err_code = st.get("error_code", "Lỗi")
            dot = "<span color='#e74c3c' size='medium'><b>[!]</b></span>"
            status_desc = f"<b><span color='#e74c3c'>{err_acc} (BỊ LỖI {err_code})</span></b> <span size='small' color='#c0392b'>- ĐANG GIỮ (HOLD)</span>"
            win.lbl_live_account.set_markup(f"{dot} <b>Tài khoản gửi:</b> {status_desc}")
            win.lbl_hold_alert.set_markup(
                f"<b><span color='#e74c3c' size='medium'>[!] PHÁT HIỆN LỖI: Tài khoản {err_acc} bị lỗi {err_code}!</span></b>\n"
                f"<i>Request đang được giữ (HOLD). Bấm <b>Thử lại</b> hoặc <b>Chuyển tiếp</b> để tiếp tục:</i>"
            )
            if hasattr(win, "hold_box"):
                win.hold_box.show()
        elif status == "FAILOVER":
            if hasattr(win, "hold_box"):
                win.hold_box.hide()
            dot = "<span color='#f39c12' size='medium'><b>[*]</b></span>"
            msg = st.get("message", f"Tự động đổi từ {st.get('error_account', '')}")
            status_desc = f"<b><span color='#e67e22'>{acc_email}</span></b> <span size='small' color='#d35400'>({msg})</span>"
            win.lbl_live_account.set_markup(f"{dot} <b>Tài khoản gửi:</b> {status_desc}")
        elif status == "SWITCHED" and (now - ts) < 4.0:
            if hasattr(win, "hold_box"):
                win.hold_box.hide()
            dot = "<span color='#3498db'>●</span>"
            status_desc = f"<b><span color='#2980b9'>{acc_email}</span></b> <span size='small' color='#27ae60'>(Vừa chủ động chuyển sang tài khoản này)</span>"
            win.lbl_live_account.set_markup(f"{dot} <b>Tài khoản gửi:</b> {status_desc}")
        else:
            if hasattr(win, "hold_box"):
                win.hold_box.hide()

            if is_active and (now - ts) < 2.0:
                dot = "<span color='#2ecc71'>●</span>"
                status_desc = f"<b><span color='#27ae60'>{acc_email}</span></b> <span size='small' color='#2980b9'>(Đang gửi {method} {endpoint})</span>"
            elif is_recent:
                dot = "<span color='#3498db'>●</span>"
                status_desc = f"<b>{acc_email}</b> <span size='small' color='#7f8c8d'>(Vừa hoàn tất: {status})</span>"
            else:
                dot = "<span color='#95a5a6'>○</span>"
                status_desc = f"<b>{acc_email}</b> <span size='small' color='#7f8c8d'>(Sẵn sàng)</span>"

            win.lbl_live_account.set_markup(f"{dot} <b>Tài khoản gửi:</b> {status_desc}")

        frac = min(1.0, max(0.0, current_req / reqs_per_acc))
        win.live_progress.set_fraction(frac)
        win.lbl_live_stats.set_markup(
            f"<b>Lượt thực hiện trên Round Robin:</b> <b>{current_req} / {reqs_per_acc}</b> request | "
            f"<b>Tổng request:</b> <b>{total_reqs}</b>"
        )
    except Exception:
        pass
    return True
