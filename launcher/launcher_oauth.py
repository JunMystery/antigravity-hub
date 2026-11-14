# -*- coding: utf-8 -*-
"""
Module xử lý quy trình đăng nhập Google OAuth 2.0 PKCE cho Antigravity Launcher.
Cung cấp cơ chế Multi-signal Detection tự động đóng dialog trong < 300ms khi nhận token.
"""

import os
import time
import json
import threading
import webbrowser
import urllib.request
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from launcher_storage import (
    CONFIG_DIR, ACCOUNTS_FILE, load_accounts, load_data
)
from launcher_proxy import ensure_proxy_running

STATUS_FILE = os.path.join(CONFIG_DIR, "live_status.json")

def start_google_oauth_flow(parent_window):
    """Mở hộp thoại đăng nhập OAuth và lắng nghe callback từ Micro-Proxy."""
    ensure_proxy_running()
    try:
        req = urllib.request.Request("http://127.0.0.1:20130/_oauth/start")
        with urllib.request.urlopen(req, timeout=5) as r:
            oauth_data = json.loads(r.read().decode())
        auth_url = oauth_data.get("authUrl")
        state = oauth_data.get("state")
    except Exception as e:
        err_dialog = Gtk.MessageDialog(
            parent=parent_window,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            message_format="Lỗi kết nối Micro-Proxy"
        )
        err_dialog.format_secondary_text(f"Không thể khởi tạo phiên OAuth trên cổng 20130: {e}")
        err_dialog.run()
        err_dialog.destroy()
        return

    webbrowser.open(auth_url)

    wait_dialog = Gtk.Dialog(
        title="Đang chờ đăng nhập Google",
        parent=parent_window,
        flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT
    )
    wait_dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)

    box = wait_dialog.get_content_area()
    box.set_spacing(12)
    box.set_margin_top(16)
    box.set_margin_bottom(16)
    box.set_margin_start(18)
    box.set_margin_end(18)

    lbl_title = Gtk.Label()
    lbl_title.set_markup("<b><span size='large' color='#2980b9'>[Browser] Đã mở trình duyệt đăng nhập Google</span></b>")
    box.pack_start(lbl_title, False, False, 0)

    lbl_sub = Gtk.Label()
    lbl_sub.set_markup(
        "Vui lòng hoàn tất xác thực trên trình duyệt của bạn.\n"
        "Micro-Proxy sẽ tự động bắt callback và liên kết tài khoản."
    )
    lbl_sub.set_justify(Gtk.Justification.CENTER)
    box.pack_start(lbl_sub, False, False, 0)

    btn_copy = Gtk.Button.new_with_label("[Copy] Sao chép link đăng nhập")
    def on_copy_clicked(_):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(auth_url, -1)
        btn_copy.set_label("[OK] Đã sao chép link!")
        GLib.timeout_add_seconds(2, lambda: btn_copy.set_label("[Copy] Sao chép link đăng nhập") or False)
    btn_copy.connect("clicked", on_copy_clicked)
    box.pack_start(btn_copy, False, False, 0)

    sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
    box.pack_start(sep, False, False, 4)

    lbl_fb = Gtk.Label(label="Dán URL callback dự phòng (nếu trình duyệt không tự chuyển hướng):")
    lbl_fb.set_xalign(0)
    box.pack_start(lbl_fb, False, False, 0)

    entry_fb = Gtk.Entry()
    entry_fb.set_placeholder_text("http://localhost:20130/oauth/callback?code=...")
    box.pack_start(entry_fb, False, False, 0)

    btn_submit = Gtk.Button.new_with_label("Xác nhận mã/URL")
    box.pack_start(btn_submit, False, False, 0)

    # Multi-signal Detection Snapshot
    start_time_ms = int(time.time() * 1000)
    initial_mtime = os.path.getmtime(ACCOUNTS_FILE) if os.path.exists(ACCOUNTS_FILE) else 0
    initial_accs = load_accounts()
    initial_snapshot = {
        (a.get("id") or a.get("email") or "").lower(): a.get("accessToken")
        for a in initial_accs
    }

    is_done = False

    def check_poll():
        nonlocal is_done
        if is_done:
            return False

        # Signal 1: Kiểm tra live_status.json do Proxy ghi khi nhận OAuth callback
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, "r", encoding="utf-8") as sf:
                    st = json.load(sf)
                if st.get("status") == "account_added" and st.get("timestamp", 0) >= (start_time_ms - 2000):
                    is_done = True
                    wait_dialog.response(Gtk.ResponseType.OK)
                    return False
            except Exception:
                pass

        # Signal 2: Kiểm tra thay đổi mtime & nội dung accounts.json
        if os.path.exists(ACCOUNTS_FILE):
            try:
                cur_mtime = os.path.getmtime(ACCOUNTS_FILE)
                if cur_mtime > initial_mtime:
                    cur_accs = load_accounts()
                    if len(cur_accs) > len(initial_accs):
                        is_done = True
                        wait_dialog.response(Gtk.ResponseType.OK)
                        return False
                    for a in cur_accs:
                        k = (a.get("id") or a.get("email") or "").lower()
                        if k not in initial_snapshot or initial_snapshot[k] != a.get("accessToken"):
                            is_done = True
                            wait_dialog.response(Gtk.ResponseType.OK)
                            return False
            except Exception:
                pass

        return True

    # Polling chu kỳ 250ms để bắt tức thì sự kiện nhận token
    poll_id = GLib.timeout_add(250, check_poll)

    def on_submit_manual(_):
        nonlocal is_done
        text = entry_fb.get_text().strip()
        if not text:
            return
        btn_submit.set_sensitive(False)
        btn_submit.set_label("[...] Đang xử lý...")
        def worker():
            try:
                req_data = json.dumps({"callbackUrl": text, "state": state}).encode("utf-8")
                m_req = urllib.request.Request(
                    "http://127.0.0.1:20130/_oauth/manual",
                    data=req_data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(m_req, timeout=10) as m_res:
                    res_json = json.loads(m_res.read().decode())
                if res_json.get("success"):
                    def on_manual_ok():
                        nonlocal is_done
                        is_done = True
                        wait_dialog.response(Gtk.ResponseType.OK)
                    GLib.idle_add(on_manual_ok)
                else:
                    def on_manual_err():
                        btn_submit.set_sensitive(True)
                        btn_submit.set_label("Xác nhận mã/URL")
                        entry_fb.set_text("")
                        entry_fb.set_placeholder_text("Lỗi: Mã hoặc URL không hợp lệ")
                    GLib.idle_add(on_manual_err)
            except Exception as err:
                def on_exc():
                    btn_submit.set_sensitive(True)
                    btn_submit.set_label("Xác nhận mã/URL")
                    entry_fb.set_text("")
                    entry_fb.set_placeholder_text(f"Lỗi: {err}")
                GLib.idle_add(on_exc)
        threading.Thread(target=worker, daemon=True).start()

    btn_submit.connect("clicked", on_submit_manual)
    entry_fb.connect("activate", on_submit_manual)

    wait_dialog.show_all()
    res_wait = wait_dialog.run()
    is_done = True
    GLib.source_remove(poll_id)
    wait_dialog.destroy()

    if res_wait == Gtk.ResponseType.OK:
        parent_window.data = load_data()
        parent_window._refresh_list()
        parent_window.on_refresh_all_quota()
        parent_window.lbl_info.set_markup("<b><span color='#2ecc71'>[OK] Đã kết nối tài khoản Google mới thành công!</span></b>")
