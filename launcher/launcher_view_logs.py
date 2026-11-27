# -*- coding: utf-8 -*-
"""
View Nhật ký Hoạt động (LogsView) độc lập cho Antigravity Launcher.
Gộp toàn bộ luồng request thành 1 bảng cấu trúc duy nhất 4 cột: Thời gian, Model, Tài khoản, Tokens.
"""

import os
import re
from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices

from launcher_i18n import tr
from launcher_theme import get_palette
from launcher_log_manager import get_log_path, clear_log, read_tail_lines
from launcher_token_delegate import TokenInOutDelegate

MAX_LOGS = 100
_NOISE_KEYS = ("====", "Socket Pool", "MITM-INIT", "Da nap")
_RE_TS = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]")
_RE_ACC = re.compile(r"\[ACC:\s*([^\]]+)\]")
_RE_MODEL = re.compile(r"\[MODEL:\s*([^\]]+)\]")
_RE_EP = re.compile(r"(GET|POST|PUT|DELETE)\s+([^\s?]+)", re.IGNORECASE)
_RE_EMAIL_BRACKET = re.compile(r"\[([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\]")
_RE_EMAIL = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
_RE_SENT = re.compile(r"Sent:\s*([^\s|]+)")
_RE_RECV = re.compile(r"Recv:\s*([^\s|]+)")
_RE_CACHED = re.compile(r"Cached:\s*([^\s|]+)")

class LogsView(QWidget):
    """View hiển thị 100 nhật ký hoạt động gần nhất có cấu trúc siêu nhẹ."""

    def __init__(self, win=None, parent=None):
        super().__init__(parent)
        self.win = win
        self.setObjectName("logs_view")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Toolbar: Tìm kiếm + Làm mới + Mở tệp Log + Sao chép + Xóa log
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.txt_search = QLineEdit(self)
        self.txt_search.setPlaceholderText(tr("logs.search_placeholder") or "Tìm kiếm theo từ khóa...")
        self.txt_search.textChanged.connect(self._filter_table)
        toolbar.addWidget(self.txt_search, stretch=1)

        self.btn_refresh = QPushButton("↻ " + (tr("full_log.btn_refresh") or "Làm mới"), self)
        self.btn_refresh.clicked.connect(lambda: self.load_logs(force=True))
        toolbar.addWidget(self.btn_refresh)

        self.btn_open_file = QPushButton(tr("logs.btn_open_file") or "Mở tệp Log", self)
        self.btn_open_file.clicked.connect(self._open_log_file)
        toolbar.addWidget(self.btn_open_file)

        self.btn_copy = QPushButton(tr("full_log.btn_copy") or "Sao chép", self)
        self.btn_copy.clicked.connect(self._copy_logs)
        toolbar.addWidget(self.btn_copy)

        self.btn_clear = QPushButton(tr("btn.clear_log") or "Xóa Log", self)
        self.btn_clear.setObjectName("btn_danger_outline")
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        toolbar.addWidget(self.btn_clear)

        layout.addLayout(toolbar)

        # Unified Lightweight Table: Time | Model | Account | Tokens (4 cols)
        self.table = QTableWidget(0, 4, self)
        self.table.setObjectName("logs_table")
        self._setup_table_headers()
        self.table.setItemDelegateForColumn(3, TokenInOutDelegate(self.table))
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(3, 280)
        hdr.setStretchLastSection(False)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setShowGrid(False)
        layout.addWidget(self.table, stretch=1)
        self._entries: List[Dict[str, str]] = []
        self._last_log_sig = None
        self.load_logs()

    def _setup_table_headers(self):
        labels = [
            (tr("col.time") or "Thời gian", Qt.AlignmentFlag.AlignLeft),
            (tr("col.model") or "Model", Qt.AlignmentFlag.AlignLeft),
            (tr("col.email") or "Tài khoản", Qt.AlignmentFlag.AlignLeft),
            (tr("col.tokens") or "Tokens", Qt.AlignmentFlag.AlignCenter)
        ]
        for col_idx, (text, align) in enumerate(labels):
            item = QTableWidgetItem(text)
            item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            self.table.setHorizontalHeaderItem(col_idx, item)

    def _parse_lines(self, lines: List[str]) -> List[Dict[str, str]]:
        entries: List[Dict[str, str]] = []
        for line in lines:
            line_str = line.strip()
            if not line_str or any(k in line_str for k in _NOISE_KEYS):
                continue

            ts_m = _RE_TS.search(line_str)
            ts = ts_m.group(1) if ts_m else "--:--:--"

            if "[ROUND-ROBIN #" in line_str:
                acc_m = _RE_ACC.search(line_str)
                acc = acc_m.group(1).strip() if acc_m else "--"
                m_model = _RE_MODEL.search(line_str)
                if m_model:
                    act = m_model.group(1).strip()
                else:
                    ep_m = _RE_EP.search(line_str)
                    act = f"{ep_m.group(1).upper()} {ep_m.group(2).split(':')[-1].split('/')[-1]}" if ep_m else "Request"
                entries.append({"time": ts, "action": act, "acc": acc, "tokens": "-- / --"})
            elif "[TOKENS]" in line_str:
                acc_m = _RE_EMAIL_BRACKET.search(line_str)
                s_m, r_m, c_m = _RE_SENT.search(line_str), _RE_RECV.search(line_str), _RE_CACHED.search(line_str)
                token_str = f"{s_m.group(1)} / {r_m.group(1)}" if s_m and r_m else ""
                if token_str and c_m and c_m.group(1) not in ("0", ""):
                    token_str += f" (+{c_m.group(1)})"
                acc = acc_m.group(1) if acc_m else ""
                matched = False
                for e in reversed(entries):
                    if acc and e["acc"] == acc and e["tokens"] == "-- / --":
                        e["tokens"] = token_str
                        matched = True
                        break
                if not matched and token_str:
                    entries.append({"time": ts, "action": "Tokens Recorded", "acc": acc or "--", "tokens": token_str})
            elif "[AUTH-" in line_str:
                action = "Refresh Token" if "AUTH-REFRESH" in line_str else ("Save Token" if "AUTH-PERSIST" in line_str else "Auth Action")
                acc_m = _RE_EMAIL.search(line_str)
                entries.append({"time": ts, "action": action, "acc": acc_m.group(1) if acc_m else "--", "tokens": "--"})
            elif "[CLIENT-ABORT]" in line_str:
                acc_m = _RE_EMAIL_BRACKET.search(line_str)
                entries.append({"time": ts, "action": "Client Abort", "acc": acc_m.group(1) if acc_m else "--", "tokens": "--"})
            elif "[UPSTREAM-ERR]" in line_str or "[UPSTREAM-TIMEOUT]" in line_str:
                acc_m = _RE_EMAIL_BRACKET.search(line_str)
                action = "Timeout (45s)" if "TIMEOUT" in line_str else "Upstream Error"
                entries.append({"time": ts, "action": action, "acc": acc_m.group(1) if acc_m else "--", "tokens": "--"})
            elif "[ROTATOR-RESTORE]" in line_str:
                acc_m = _RE_EMAIL_BRACKET.search(line_str)
                entries.append({"time": ts, "action": "Rotator Restore", "acc": acc_m.group(1) if acc_m else "--", "tokens": "--"})
        return entries

    def load_logs(self, force: bool = False):
        """Đọc và phân tích 100 bản ghi nhật ký gần nhất từ tệp proxy.log."""
        log_path = get_log_path()
        if not os.path.exists(log_path):
            self._last_log_sig = None
            self._entries = []
            self.table.setRowCount(0)
            return

        try:
            st = os.stat(log_path)
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            return
        if not force and sig == self._last_log_sig:
            return

        lines = read_tail_lines(log_path, max_lines=1000, max_bytes=512 * 1024)
        entries = self._parse_lines(lines)
        if len(entries) < MAX_LOGS and (st.st_size > 512 * 1024 or len(lines) >= 1000):
            lines = read_tail_lines(log_path, max_lines=4000, max_bytes=2 * 1024 * 1024)
            entries = self._parse_lines(lines)

        self._last_log_sig = sig
        self._entries = entries[-MAX_LOGS:]
        self._populate_table()

    def _populate_table(self):
        p = get_palette()
        c_time, c_act, c_acc = QColor(p["text_sub"]), QColor(p["text"]), QColor(p["text_secondary"])
        c_tok_ok, c_tok_dim = QColor(p["green"]), QColor(p["text_muted"])
        query = self.txt_search.text().strip().lower()
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(0)
            for e in self._entries:
                row_vals = [e["time"], e["action"], e["acc"], e["tokens"]]
                if query and not any(query in v.lower() for v in row_vals):
                    continue

                r = self.table.rowCount()
                self.table.insertRow(r)

                it_time = QTableWidgetItem(e["time"])
                it_time.setForeground(c_time)

                it_act = QTableWidgetItem(e["action"])
                it_act.setForeground(c_act)

                it_acc = QTableWidgetItem(e["acc"])
                it_acc.setForeground(c_acc)

                it_tok = QTableWidgetItem(e["tokens"])
                it_tok.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                it_tok.setForeground(c_tok_ok if e["tokens"] not in ("-- / --", "--") else c_tok_dim)

                self.table.setItem(r, 0, it_time)
                self.table.setItem(r, 1, it_act)
                self.table.setItem(r, 2, it_acc)
                self.table.setItem(r, 3, it_tok)

            self.table.scrollToBottom()
        finally:
            self.table.setUpdatesEnabled(True)

    def _filter_table(self, query: str = ""):
        self._populate_table()

    def _open_log_file(self):
        log_path = get_log_path()
        if os.path.exists(log_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(log_path))

    def _copy_logs(self):
        sel_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        rows_to_copy = sel_rows if sel_rows else range(self.table.rowCount())
        rows = []
        for r in rows_to_copy:
            row_text = "\t".join(self.table.item(r, c).text() if self.table.item(r, c) else "" for c in range(self.table.columnCount()))
            rows.append(row_text)
        QApplication.clipboard().setText("\n".join(rows))

    def _on_clear_clicked(self):
        msg = tr("logs.clear_confirm") or "Bạn có chắc chắn muốn xóa toàn bộ lịch sử log không?"
        res = QMessageBox.question(self, tr("btn.clear_log"), msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            clear_log()
            self._last_log_sig = None
            self.load_logs(force=True)

    def refresh_theme(self):
        """Đồng bộ màu chữ bảng Logs theo Theme hiện tại."""
        self._populate_table()
        self.table.viewport().update()

    def retranslate_ui(self):
        self.txt_search.setPlaceholderText(tr("logs.search_placeholder") or "Tìm kiếm theo từ khóa...")
        self.btn_refresh.setText("↻ " + (tr("full_log.btn_refresh") or "Làm mới"))
        self.btn_open_file.setText(tr("logs.btn_open_file") or "Mở tệp Log")
        self.btn_copy.setText(tr("full_log.btn_copy") or "Sao chép")
        self.btn_clear.setText(tr("btn.clear_log") or "Xóa Log")
        self._setup_table_headers()
