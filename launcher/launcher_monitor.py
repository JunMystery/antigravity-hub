# -*- coding: utf-8 -*-
"""
Module xây dựng và điều khiển khung giám sát trực tiếp (Live Monitor) cho Launcher (PyQt6).
"""

import os
import json
import time
import urllib.request
import urllib.parse
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt

from launcher_storage import CONFIG_DIR, PROXY_PORT
from launcher_proxy import is_proxy_running, stop_proxy, ensure_proxy_running
from launcher_i18n import tr

STATUS_FILE = os.path.join(CONFIG_DIR, "live_status.json")
CMD_FILE = os.path.join(CONFIG_DIR, "proxy_cmd.json")

def send_proxy_cmd(win, cmd: str, params: dict = None) -> bool:
    """Gửi lệnh điều khiển trực tiếp tới Micro-Proxy qua HTTP hoặc tệp trung gian."""
    query = {"cmd": cmd}
    if isinstance(params, dict):
        for k, v in params.items():
            if v is not None and v != "":
                query[k] = v

    sent = False
    try:
        qs = urllib.parse.urlencode(query)
        url = f"http://127.0.0.1:{PROXY_PORT}/_proxy_action?{qs}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=0.25) as resp:
            if resp.status == 200:
                sent = True
    except Exception:
        sent = False

    if not sent:
        try:
            payload = dict(query)
            payload["ts"] = time.time()
            with open(CMD_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception:
            pass
    return sent

def build_monitor_frame(win) -> QGroupBox:
    """Tạo khung hiển thị trạng thái hoạt động trực tiếp của Micro-Proxy."""
    box = QGroupBox(tr("monitor.box_title"))
    layout = QVBoxLayout(box)
    layout.setSpacing(6)
    layout.setContentsMargins(10, 10, 10, 10)

    top_row = QHBoxLayout()
    win.mon_dot = QLabel("● STANDBY")
    win.mon_dot.setStyleSheet("color: #89b4fa; font-weight: bold;")
    top_row.addWidget(win.mon_dot)

    win.mon_ep = QLabel(tr("monitor.endpoint_ready"))
    win.mon_ep.setStyleSheet("color: #bac2de;")
    top_row.addWidget(win.mon_ep, 1)

    win.btn_proxy_next = QPushButton(tr("monitor.btn_next"))
    win.btn_proxy_next.setToolTip(tr("monitor.btn_next_tooltip"))
    win.btn_proxy_next.clicked.connect(win.on_manual_next_account)
    top_row.addWidget(win.btn_proxy_next)

    win.btn_proxy_toggle = QPushButton(tr("btn.pause_rotation"))
    win.btn_proxy_toggle.setToolTip(tr("tooltip.pause_rotation"))
    win.btn_proxy_toggle.clicked.connect(win.on_toggle_proxy_btn)
    top_row.addWidget(win.btn_proxy_toggle)
    layout.addLayout(top_row)

    bot_row = QHBoxLayout()
    win.mon_acc = QLabel(tr("monitor.acc_label") + "--")
    bot_row.addWidget(win.mon_acc, 2)

    win.mon_req = QLabel(tr("monitor.turn_label") + "0/1")
    bot_row.addWidget(win.mon_req, 1)

    win.mon_total = QLabel(tr("monitor.total_init"))
    bot_row.addWidget(win.mon_total, 1)
    layout.addLayout(bot_row)

    return box

def update_monitor_ui(win):
    """Cập nhật dữ liệu từ live_status.json lên giao diện Monitor."""
    if not is_proxy_running():
        win.mon_dot.setText("● STOPPED")
        win.mon_dot.setStyleSheet("color: #f38ba8; font-weight: bold;")
        win.mon_ep.setText(tr("monitor.proxy_stopped"))
        win.mon_acc.setText(tr("monitor.acc_label") + tr("monitor.acc_unavailable"))
        win.mon_req.setText(tr("monitor.turn_label") + "--")
        win.mon_total.setText(tr("monitor.total_label") + "--")
        win.btn_proxy_toggle.setText(tr("btn.start_proxy"))
        win.btn_proxy_toggle.setToolTip(tr("btn.start_proxy"))
        win.btn_proxy_next.setEnabled(False)
        return

    win.btn_proxy_next.setEnabled(True)

    if not os.path.exists(STATUS_FILE):
        win.mon_dot.setText("● STANDBY")
        win.mon_dot.setStyleSheet("color: #89b4fa; font-weight: bold;")
        win.mon_ep.setText(tr("monitor.listening_ready"))
        win.mon_acc.setText(tr("monitor.acc_label") + "--")
        win.mon_req.setText(tr("monitor.turn_label") + "0/1")
        win.mon_total.setText(tr("monitor.total_init"))
        win.btn_proxy_toggle.setText(tr("btn.pause_rotation"))
        win.btn_proxy_toggle.setToolTip(tr("tooltip.pause_rotation"))
        return

    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        status = data.get("status", "standby")
        is_paused = bool(data.get("paused", False) or status == "paused")
        account_name = data.get("account_name", data.get("account_email", "Chưa có"))
        current_req = data.get("current_req", 0)
        max_req = data.get("requests_per_account", 1)
        total_req = data.get("total_requests", 0)
        endpoint = data.get("endpoint", "")
        method = data.get("method", "")

        # Cập nhật nút Pause / Resume
        if is_paused:
            win.btn_proxy_toggle.setText(tr("btn.resume_rotation"))
            win.btn_proxy_toggle.setToolTip(tr("tooltip.resume_rotation"))
        else:
            win.btn_proxy_toggle.setText(tr("btn.pause_rotation"))
            win.btn_proxy_toggle.setToolTip(tr("tooltip.pause_rotation"))

        # Cập nhật đèn trạng thái
        if status == "sending":
            win.mon_dot.setText("● ACTIVE")
            win.mon_dot.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            if endpoint:
                ep_html = endpoint.replace("[SUBAGENT]", "<span style='color:#cba6f7;font-weight:bold;'>[SUBAGENT]</span>").replace("[CHAT]", "<span style='color:#89b4fa;font-weight:bold;'>[CHAT]</span>")
                win.mon_ep.setText(f"{method} {ep_html}")
            else:
                win.mon_ep.setText(tr("monitor.forwarding"))
        elif status == "FAILOVER":
            win.mon_dot.setText("● FAILOVER")
            win.mon_dot.setStyleSheet("color: #fab387; font-weight: bold;")
            win.mon_ep.setText(data.get("message", tr("monitor.forwarding")))
        elif is_paused:
            win.mon_dot.setText("● PAUSED")
            win.mon_dot.setStyleSheet("color: #f9e2af; font-weight: bold;")
            win.mon_ep.setText(tr("monitor.paused_desc"))
        else:
            win.mon_dot.setText("● STANDBY")
            win.mon_dot.setStyleSheet("color: #89b4fa; font-weight: bold;")
            win.mon_ep.setText(tr("monitor.listening_ready"))

        win.mon_acc.setText(f"{tr('monitor.acc_label')}<b>{account_name}</b>")
        turn_display = str(current_req) if is_paused else f"{current_req}/{max_req}"
        win.mon_req.setText(f"{tr('monitor.turn_label')}<b>{turn_display}</b> req")
        win.mon_total.setText(f"{tr('monitor.total_label')}<b>{total_req}</b> req")
    except Exception:
        pass
