# -*- coding: utf-8 -*-
"""
Panel hiển thị nhật ký hoạt động tinh gọn trên Dashboard (ActivityLogsPanel).
Hiển thị 3 cột duy nhất: Model | In / Out | When, tối đa 50 requests gần nhất.
"""

import os
import re
from typing import List, Dict, Any, Tuple
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from launcher_i18n import tr
from launcher_theme import get_palette
from launcher_log_manager import get_log_path, parse_log_lines, read_tail_lines
from launcher_token_delegate import TokenInOutDelegate

MAX_RECENT_LOGS = 50

def is_actionable_log(item: Dict[str, Any]) -> bool:
    """Loại bỏ các thông báo hệ thống, lỗi kết nối, biểu ngữ khởi động và token actions để Dashboard chỉ hiển thị AI Log."""
    text = (item.get("raw", "") or item.get("details", "")).strip()
    if not text or re.match(r"^\[\d{2}:\d{2}:\d{2}\]\s*$", text):
        return False
    upper = text.upper()
    ignore_patterns = [
        "====", "TAI KHOAN THAM GIA", "SOCKET POOL", "[PROXY] ANTIGRAVITY",
        "TAI KHOAN HIEN TAI:", "NGUONG CHUYEN DOI:", "[MITM-INIT]", "[ROUND-ROBIN] DA NAP",
        "NGAY TAO:", "[ROTATOR-RESTORE]", "[CLIENT-ABORT]", "[UPSTREAM-ERR]",
        "[UPSTREAM-TIMEOUT]", "[AUTH-", "REFRESH TOKEN", "SAVE TOKEN", "LƯU TOKEN",
        "CAP MOI TOKEN", "CẤP MỚI TOKEN"
    ]
    return not any(pat in upper for pat in ignore_patterns)

def format_compact_details(details: str) -> str:
    """Rút gọn chi tiết log theo định dạng: [Endpoint/Action] → [Email], hỗ trợ tương thích ngược."""
    cleaned = (details or "").strip()
    cleaned = re.sub(r"^(\[(STICKY|NEW-SUB|MAIN|SUBAGENT)\]\s*)+", "", cleaned)
    m = re.search(r"(GET|POST|PUT|DELETE)\s+([^\s?]+).*?->\s*\[ACC:\s*([^\]]+)\]", cleaned, re.IGNORECASE)
    if m:
        method = m.group(1).upper()
        raw_path = m.group(2)
        ep = raw_path.split(":")[-1].split("/")[-1] if (":" in raw_path or "/" in raw_path) else raw_path
        acc = m.group(3).strip()
        return f"{method} {ep} → {acc}"
    if "AUTH-REFRESH" in cleaned:
        m_email = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", cleaned)
        return f"Refresh Token → {m_email.group(1)} [OK]" if m_email else cleaned
    if "AUTH-PERSIST" in cleaned:
        m_email = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", cleaned)
        return f"Lưu Token → {m_email.group(1)} [OK]" if m_email else cleaned
    return re.sub(r"\s*\(\d+/\d+\s*req\)", "", cleaned)

def extract_model_and_tokens(details: str, raw: str = "") -> Tuple[str, str]:
    """Trích xuất tên Model/Endpoint và Tokens In/Out thuần túy không kèm cache."""
    text = f"{raw} {details}".strip()
    model = ""
    m_tag = re.search(r"\[MODEL:\s*([^\]]+)\]", text)
    if m_tag:
        model = m_tag.group(1).strip()
    else:
        m_model = re.search(r"models/([a-zA-Z0-9._-]+)", text)
        if m_model:
            model = m_model.group(1).split(":")[0]
        else:
            m_ep = re.search(r"(?:GET|POST|PUT|DELETE)\s+([^\s?]+)", text, re.IGNORECASE)
            if m_ep:
                raw_ep = m_ep.group(1)
                model = raw_ep.split(":")[-1].split("/")[-1] if (":" in raw_ep or "/" in raw_ep) else raw_ep
            else:
                model = "Request"

    s_m = re.search(r"Sent:\s*([^\s|]+)", text)
    r_m = re.search(r"Recv:\s*([^\s|]+)", text)
    in_out = f"{s_m.group(1)} / {r_m.group(1)}" if s_m and r_m else "-- / --"
    return model, in_out

class ActivityLogsPanel(QWidget):
    """Bảng hiển thị nhật ký tinh gọn 3 cột: Model | In / Out | When (tối đa 50 dòng)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._last_log_size = 0
        self._last_log_sig = None
        self.active_filter = "ALL"
        self._history: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        hdr_lay = QHBoxLayout()
        self.lbl_panel_title = QLabel(tr("activity.title") or "Hoạt động gần nhất (50 requests)")
        self.lbl_panel_title.setObjectName("status_title")
        hdr_lay.addWidget(self.lbl_panel_title)
        hdr_lay.addStretch()
        layout.addLayout(hdr_lay)

        self.table = self._create_table()
        layout.addWidget(self.table)

        self.table_chat = self.table
        self.table_subagent = self.table

    @property
    def table_feed(self) -> QTableWidget:
        return self.table

    def _setup_table_headers(self, table: QTableWidget):
        h0 = QTableWidgetItem(tr("col.model") or "Model")
        h0.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table.setHorizontalHeaderItem(0, h0)

        h1 = QTableWidgetItem(tr("col.in_out") or "In / Out")
        h1.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        table.setHorizontalHeaderItem(1, h1)

        h2 = QTableWidgetItem(tr("col.when") or "When")
        h2.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table.setHorizontalHeaderItem(2, h2)

    def _create_table(self) -> QTableWidget:
        table = QTableWidget(0, 3)
        table.setObjectName("activity_table")
        self._setup_table_headers(table)
        table.setItemDelegateForColumn(1, TokenInOutDelegate(table))
        hdr = table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(1, 240)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(28)
        table.setShowGrid(False)
        return table

    def _set_filter(self, tag: str):
        self.active_filter = tag.upper()

    def _populate_table(self, items: List[Dict[str, Any]]):
        p = get_palette()
        c_model, c_in_out, c_when = QColor(p["text"]), QColor(p["text_sub"]), QColor(p["text_muted"])
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(0)
            for item in items:
                r = self.table.rowCount()
                self.table.insertRow(r)
                model = item.get("model", "")
                in_out = item.get("in_out", "-- / --")
                when = item.get("timestamp", "")

                it_model = QTableWidgetItem(model)
                it_in_out = QTableWidgetItem(in_out)
                it_when = QTableWidgetItem(when)

                it_model.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                it_in_out.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                it_when.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                it_model.setForeground(c_model)
                it_in_out.setForeground(c_in_out)
                it_when.setForeground(c_when)

                self.table.setItem(r, 0, it_model)
                self.table.setItem(r, 1, it_in_out)
                self.table.setItem(r, 2, it_when)
            self.table.scrollToBottom()
        finally:
            self.table.setUpdatesEnabled(True)

    def update_logs(self, parsed_logs: List[Dict[str, Any]]) -> None:
        """Cập nhật nhật ký vào bảng 3 cột, gắn kết tokens và giới hạn 50 dòng."""
        if not parsed_logs:
            return

        requests: List[Dict[str, Any]] = []
        for p in parsed_logs:
            raw = p.get("raw", "")
            details = p.get("details", "")
            if not is_actionable_log(p):
                continue

            if "[TOKENS]" in (raw or details):
                # Tìm token và gắn vào request gần nhất của account
                acc_m = re.search(r"\[([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\]", raw or details)
                s_m = re.search(r"Sent:\s*([^\s|]+)", raw or details)
                r_m = re.search(r"Recv:\s*([^\s|]+)", raw or details)
                if acc_m and s_m and r_m and requests:
                    acc = acc_m.group(1)
                    tok_str = f"{s_m.group(1)} / {r_m.group(1)}"
                    for req in reversed(requests):
                        if req.get("acc") == acc and req.get("in_out") == "-- / --":
                            req["in_out"] = tok_str
                            break
                continue

            model, in_out = extract_model_and_tokens(details, raw)
            # Tuyệt đối không ghi nhận các action refresh token, save token hoặc fallback rỗng không phải AI request
            if model in ("Refresh Token", "Save Token"):
                continue
            if raw and model == "Request" and in_out == "-- / --" and not re.search(r"(GET|POST|PUT|DELETE)", raw, re.IGNORECASE):
                continue

            acc_m = re.search(r"\[ACC:\s*([^\]]+)\]", raw or details)
            acc = acc_m.group(1).strip() if acc_m else ""

            requests.append({
                "model": model,
                "in_out": in_out,
                "timestamp": p.get("timestamp", ""),
                "acc": acc,
                "raw": raw or details
            })

        self._history = requests[-MAX_RECENT_LOGS:]
        self._populate_table(self._history)

    def _read_recent_logs(self) -> None:
        """Đọc và phân tích các dòng log mới nhất từ file proxy.log."""
        log_path = get_log_path()
        if not os.path.exists(log_path):
            return
        try:
            st = os.stat(log_path)
            sig = (st.st_mtime_ns, st.st_size)
            if sig == self._last_log_sig:
                return
            self._last_log_sig = sig
            self._last_log_size = st.st_size
            lines = read_tail_lines(log_path, max_lines=1000)
            parsed = parse_log_lines(lines)
            self.update_logs(parsed)
        except Exception:
            pass

    def refresh_theme(self):
        """Đồng bộ màu chữ và vùng bảng khi đổi Theme Light/Dark."""
        if self._history:
            self._populate_table(self._history)
        self.table.viewport().update()

    def retranslate_ui(self):
        """Cập nhật tiêu đề bảng khi đổi ngôn ngữ."""
        self.lbl_panel_title.setText(tr("activity.title") or "Hoạt động gần nhất (50 requests)")
        self._setup_table_headers(self.table)
        if self._history:
            self._populate_table(self._history)
