# -*- coding: utf-8 -*-
"""
Module xử lý quy trình đăng nhập Google OAuth 2.0 PKCE cho Antigravity Launcher (PyQt6).
Cung cấp cơ chế Multi-signal Detection tự động đóng dialog trong < 300ms khi nhận token.
"""

import os
import sys
import time
import json
import webbrowser
import urllib.request
import urllib.parse

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QMessageBox, QApplication
)
from PyQt6.QtCore import QTimer, Qt

from launcher_i18n import tr, get_current_language
from launcher_storage import (
    CONFIG_DIR, ACCOUNTS_FILE, load_accounts, load_data
)
from launcher_proxy import ensure_proxy_running
from launcher_browser_close import try_close_oauth_browser_tab

STATUS_FILE = os.path.join(CONFIG_DIR, "live_status.json")


def _resolve_launcher_lang(parent_window) -> str:
    if hasattr(parent_window, "data") and isinstance(parent_window.data, dict):
        lang = parent_window.data.get("settings", {}).get("language")
        if lang:
            return str(lang).lower()
    return (get_current_language() or "vi").lower()


def start_google_oauth_flow(parent_window):
    """Mở hộp thoại đăng nhập OAuth và lắng nghe callback từ Micro-Proxy."""
    cur_lang = _resolve_launcher_lang(parent_window)
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        QApplication.processEvents()
        ensure_proxy_running()
        QApplication.processEvents()
        qs = urllib.parse.urlencode({"lang": cur_lang})
        req = urllib.request.Request(f"http://127.0.0.1:20130/_oauth/start?{qs}")
        with urllib.request.urlopen(req, timeout=5) as r:
            oauth_data = json.loads(r.read().decode())
        auth_url = oauth_data.get("authUrl")
    except Exception as e:
        QApplication.restoreOverrideCursor()
        QMessageBox.critical(
            parent_window,
            tr("oauth.proxy_error_title"),
            tr("oauth.proxy_error_desc", error=str(e))
        )
        return
    finally:
        try:
            QApplication.restoreOverrideCursor()
        except Exception:
            pass

    webbrowser.open(auth_url)

    dialog = QDialog(parent_window)
    dialog.setWindowTitle(tr("oauth.dialog_title"))
    dialog.setModal(True)
    dialog.setMinimumWidth(440)

    layout = QVBoxLayout(dialog)
    layout.setSpacing(10)
    layout.setContentsMargins(18, 16, 18, 16)

    lbl_title = QLabel(f"<b><span style='font-size:14px; color:#89b4fa;'>{tr('oauth.opened_browser_title')}</span></b>")
    layout.addWidget(lbl_title)

    lbl_sub = QLabel(tr("oauth.instruction"))
    lbl_sub.setWordWrap(True)
    layout.addWidget(lbl_sub)

    btn_copy = QPushButton(tr("oauth.copy_link"))
    def on_copy_clicked():
        QApplication.clipboard().setText(auth_url)
        btn_copy.setText(tr("oauth.link_copied"))
        QTimer.singleShot(2000, lambda: btn_copy.setText(tr("oauth.copy_link")))
    btn_copy.clicked.connect(on_copy_clicked)
    layout.addWidget(btn_copy)

    # Multi-signal Detection Snapshot
    start_time_ms = int(time.time() * 1000)
    initial_mtime = os.path.getmtime(ACCOUNTS_FILE) if os.path.exists(ACCOUNTS_FILE) else 0
    initial_accs = load_accounts()
    initial_snapshot = {
        (a.get("id") or a.get("email") or "").lower(): a.get("accessToken")
        for a in initial_accs
    }

    is_done = False

    def complete_oauth():
        nonlocal is_done
        if is_done:
            return
        is_done = True
        poll_timer.stop()
        if sys.platform != "win32":
            dialog.accept()
            return
        attempts = {"count": 0}
        close_timer = QTimer(dialog)

        def attempt_close():
            attempts["count"] += 1
            if try_close_oauth_browser_tab():
                close_timer.stop()
                QTimer.singleShot(100, dialog.accept)
            elif attempts["count"] >= 10:
                close_timer.stop()
                dialog.accept()

        close_timer.timeout.connect(attempt_close)
        close_timer.start(100)
        attempt_close()

    def check_poll():
        if is_done:
            return

        # Signal 1: Kiểm tra live_status.json do Proxy ghi khi nhận OAuth callback
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, "r", encoding="utf-8") as sf:
                    st = json.load(sf)
                if st.get("status") == "account_added" and st.get("timestamp", 0) >= (start_time_ms - 2000):
                    complete_oauth()
                    return
            except Exception:
                pass

        # Signal 2: Kiểm tra thay đổi mtime & nội dung accounts.json
        if os.path.exists(ACCOUNTS_FILE):
            try:
                cur_mtime = os.path.getmtime(ACCOUNTS_FILE)
                if cur_mtime > initial_mtime:
                    cur_accs = load_accounts()
                    if len(cur_accs) > len(initial_accs):
                        complete_oauth()
                        return
                    for a in cur_accs:
                        k = (a.get("id") or a.get("email") or "").lower()
                        if k not in initial_snapshot or initial_snapshot[k] != a.get("accessToken"):
                            complete_oauth()
                            return
            except Exception:
                pass

    poll_timer = QTimer(dialog)
    poll_timer.timeout.connect(check_poll)
    poll_timer.start(250)

    btn_cancel = QPushButton(tr("btn.cancel"))
    btn_cancel.clicked.connect(dialog.reject)
    layout.addWidget(btn_cancel)

    result = dialog.exec()
    is_done = True
    poll_timer.stop()

    if result == QDialog.DialogCode.Accepted:
        parent_window.data = load_data()
        parent_window._refresh_list()
        parent_window.on_refresh_all_quota()
        parent_window.lbl_info.setText(f"<b><span style='color:#a6e3a1;'>{tr('oauth.success_info')}</span></b>")
        if hasattr(parent_window, "activate_window"):
            parent_window.activate_window()
