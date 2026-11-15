# -*- coding: utf-8 -*-
"""
Panel hiển thị luồng nhật ký hoạt động tinh gọn (Unified Activity Logs Panel).
Hiển thị 1 bảng duy nhất, bỏ cột Tag, 20 dòng gần nhất, định dạng [Action/Endpoint] → [Email].
"""

import os
import re
from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt

from launcher_i18n import tr
from launcher_log_manager import get_log_path, parse_log_lines

def is_actionable_log(item: Dict[str, Any]) -> bool:
    """Loại bỏ các dòng phân cách, biểu ngữ khởi động để hiển thị danh sách request trong sáng."""
    raw = item.get("raw", "") or item.get("details", "")
    ignore_patterns = [
        "====", "Tai khoan tham gia", "Socket Pool", "[PROXY] Antigravity",
        "Tai khoan hien tai:", "Nguong chuyen doi:", "[MITM-INIT]", "[ROUND-ROBIN] Da nap",
        "Ngay tao:"
    ]
    return not any(pat in raw for pat in ignore_patterns)

def format_compact_details(details: str) -> str:
    """Rút gọn chi tiết log theo định dạng: [Endpoint/Action] → [Email], bỏ hậu tố (N/M)."""
    cleaned = (details or "").strip()
    cleaned = re.sub(r"^(\[(STICKY|NEW-SUB|MAIN|SUBAGENT)\]\s*)+", "", cleaned)

    # Khớp request round-robin: Method Endpoint -> [ACC: email]
    m = re.search(r"(GET|POST|PUT|DELETE)\s+([^\s?]+).*?->\s*\[ACC:\s*([^\]]+)\]", cleaned, re.IGNORECASE)
    if m:
        method = m.group(1).upper()
        raw_path = m.group(2)
        ep = raw_path.split(":")[-1].split("/")[-1] if (":" in raw_path or "/" in raw_path) else raw_path
        acc = m.group(3).strip()
        return f"{method} {ep} → {acc}"

    # Khớp Refresh Token
    if "AUTH-REFRESH" in cleaned:
        m_email = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", cleaned)
        email = m_email.group(1) if m_email else ""
        action = tr("log.refresh_token") or "Refresh Token"
        return f"{action} → {email} [OK]" if email else cleaned

    # Khớp Save Token
    if "AUTH-PERSIST" in cleaned:
        m_email = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", cleaned)
        email = m_email.group(1) if m_email else ""
        action = tr("log.save_token") or "Save Token"
        return f"{action} → {email} [OK]" if email else cleaned

    # Khớp ROTATOR-RESTORE
    if "ROTATOR-RESTORE" in cleaned:
        m_email = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", cleaned)
        email = m_email.group(1) if m_email else ""
        return f"Restore Account → {email}" if email else cleaned

    # Loại bỏ hậu tố (N/M req) nếu còn sót lại
    cleaned = re.sub(r"\s*\(\d+/\d+\s*req\)", "", cleaned)
    return cleaned

class ActivityLogsPanel(QWidget):
    """Bảng hiển thị nhật ký tinh gọn 1 bảng duy nhất, giới hạn 20 dòng."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_log_size = 0
        self.active_filter = "ALL"
        self._history = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.table = self._create_table()
        layout.addWidget(self.table)

        # Thuộc tính tương thích ngược
        self.table_chat = self.table
        self.table_subagent = self.table

    @property
    def table_feed(self) -> QTableWidget:
        return self.table

    def _create_table(self) -> QTableWidget:
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels([tr("col.time"), tr("col.details")])
        hdr = table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(28)
        table.setShowGrid(False)
        table.setStyleSheet("QTableWidget { background-color: #181825; border: 1px solid #313244; }")
        return table

    def _set_filter(self, tag: str):
        self.active_filter = tag.upper()

    def _populate_table(self, items: List[Dict[str, Any]]):
        self.table.setRowCount(0)
        for item in items:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(item.get("timestamp", "")))

            raw_details = item.get("details", "")
            compact_details = format_compact_details(raw_details)
            self.table.setItem(r, 1, QTableWidgetItem(compact_details))
        self.table.scrollToBottom()

    def update_logs(self, parsed_logs: List[Dict[str, Any]]) -> None:
        """Cập nhật nhật ký vào bảng duy nhất, duy trì tối đa 20 dòng gần nhất."""
        if parsed_logs:
            actionable = [p for p in parsed_logs if is_actionable_log(p)]
            if not actionable:
                actionable = [p for p in parsed_logs if "====" not in (p.get("raw", "") or "")]
            self._history = actionable[-20:]
            self._populate_table(self._history)

    def _read_recent_logs(self) -> None:
        """Đọc và phân tích các dòng log mới nhất từ file proxy.log."""
        log_path = get_log_path()
        if not os.path.exists(log_path):
            return
        try:
            sz = os.path.getsize(log_path)
            if sz == self._last_log_size:
                return
            self._last_log_size = sz
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-1000:]
            parsed = parse_log_lines(lines)
            self.update_logs(parsed)
        except Exception:
            pass

    def retranslate_ui(self):
        """Cập nhật tiêu đề bảng khi đổi ngôn ngữ."""
        self.table.setHorizontalHeaderLabels([tr("col.time"), tr("col.details")])
        if self._history:
            self._populate_table(self._history)
