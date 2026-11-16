# -*- coding: utf-8 -*-
"""
View Nhật ký Hoạt động (LogsView) độc lập cho Antigravity Launcher.
Gộp toàn bộ luồng request thành 1 bảng cấu trúc duy nhất 5 cột: Thời gian, Luồng, Tác vụ/Model, Email, Tokens.
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
from launcher_log_manager import get_log_path, clear_log
from launcher_token_delegate import TokenInOutDelegate

MAX_LOGS = 100

class LogsView(QWidget):
    """View hiển thị 100 nhật ký hoạt động gần nhất có cấu trúc siêu nhẹ."""

    def __init__(self, win=None, parent=None):
        super().__init__(parent)
        self.win = win
        self.setObjectName("logs_view")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#logs_view { background-color: #1e1e2e; color: #cdd6f4; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Toolbar: Tìm kiếm + Làm mới + Mở tệp Log + Sao chép + Xóa log
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.txt_search = QLineEdit(self)
        self.txt_search.setPlaceholderText(tr("logs.search_placeholder") or "Tìm kiếm theo từ khóa...")
        self.txt_search.setStyleSheet(
            "QLineEdit { background-color: #181825; border: 1px solid #313244; "
            "border-radius: 6px; padding: 5px 10px; color: #cdd6f4; } "
            "QLineEdit:focus { border: 1px solid #89b4fa; }"
        )
        self.txt_search.textChanged.connect(self._filter_table)
        toolbar.addWidget(self.txt_search, stretch=1)

        self.btn_refresh = QPushButton("↻ " + (tr("full_log.btn_refresh") or "Làm mới"), self)
        self.btn_refresh.setStyleSheet("background-color: #313244; border-radius: 6px; padding: 6px 12px; color: #cdd6f4;")
        self.btn_refresh.clicked.connect(self.load_logs)
        toolbar.addWidget(self.btn_refresh)

        self.btn_open_file = QPushButton(tr("logs.btn_open_file") or "Mở tệp Log", self)
        self.btn_open_file.setStyleSheet("background-color: #313244; border-radius: 6px; padding: 6px 12px; color: #cdd6f4;")
        self.btn_open_file.clicked.connect(self._open_log_file)
        toolbar.addWidget(self.btn_open_file)

        self.btn_copy = QPushButton(tr("full_log.btn_copy") or "Sao chép", self)
        self.btn_copy.setStyleSheet("background-color: #313244; border-radius: 6px; padding: 6px 12px; color: #cdd6f4;")
        self.btn_copy.clicked.connect(self._copy_logs)
        toolbar.addWidget(self.btn_copy)

        self.btn_clear = QPushButton(tr("btn.clear_log") or "Xóa Log", self)
        self.btn_clear.setStyleSheet(
            "QPushButton { background-color: rgba(243, 139, 168, 0.15); color: #f38ba8; "
            "border: 1px solid #f38ba8; border-radius: 6px; padding: 6px 12px; } "
            "QPushButton:hover { background-color: rgba(243, 139, 168, 0.25); }"
        )
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        toolbar.addWidget(self.btn_clear)

        layout.addLayout(toolbar)

        # Unified Lightweight Table: Time | Thread | Model | Account | Tokens (5 cols)
        self.table = QTableWidget(0, 5, self)
        self._setup_table_headers()
        self.table.setItemDelegateForColumn(4, TokenInOutDelegate(self.table))
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(4, 280)
        hdr.setStretchLastSection(False)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(
            "QTableWidget { background-color: #181825; border: 1px solid #313244; "
            "border-radius: 6px; color: #cdd6f4; } "
            "QHeaderView { background-color: #24273a; border-top-left-radius: 5px; border-top-right-radius: 5px; border: none; } "
            "QHeaderView::section { background-color: #24273a; color: #a6adc8; font-weight: bold; padding: 4px 8px; border: none; } "
            "QTableCornerButton::section { background-color: #24273a; border: none; }"
        )
        layout.addWidget(self.table, stretch=1)
        self._entries: List[Dict[str, str]] = []
        self.load_logs()

    def _setup_table_headers(self):
        labels = [
            (tr("col.time") or "Thời gian", Qt.AlignmentFlag.AlignLeft),
            (tr("col.thread") or "Luồng", Qt.AlignmentFlag.AlignLeft),
            (tr("col.model") or "Model", Qt.AlignmentFlag.AlignLeft),
            (tr("col.email") or "Tài khoản", Qt.AlignmentFlag.AlignLeft),
            (tr("col.tokens") or "Tokens", Qt.AlignmentFlag.AlignCenter)
        ]
        for col_idx, (text, align) in enumerate(labels):
            item = QTableWidgetItem(text)
            item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            self.table.setHorizontalHeaderItem(col_idx, item)

    def load_logs(self):
        """Đọc và phân tích 100 bản ghi nhật ký gần nhất từ tệp proxy.log."""
        log_path = get_log_path()
        if not os.path.exists(log_path):
            self.table.setRowCount(0)
            return

        entries = []
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-500:]
        except Exception:
            return

        for line in lines:
            line_str = line.strip()
            if not line_str or any(k in line_str for k in ["====", "Socket Pool", "MITM-INIT", "Da nap"]):
                continue

            ts_m = re.search(r"\[(\d{2}:\d{2}:\d{2})\]", line_str)
            ts = ts_m.group(1) if ts_m else "--:--:--"

            if "[ROUND-ROBIN #" in line_str:
                thread = "SUBAGENT" if "[SUBAGENT]" in line_str else "MAIN"
                acc_m = re.search(r"\[ACC:\s*([^\]]+)\]", line_str)
                acc = acc_m.group(1).strip() if acc_m else "--"
                m_model = re.search(r"\[MODEL:\s*([^\]]+)\]", line_str)
                if m_model:
                    act = m_model.group(1).strip()
                else:
                    ep_m = re.search(r"(GET|POST|PUT|DELETE)\s+([^\s?]+)", line_str, re.IGNORECASE)
                    act = f"{ep_m.group(1).upper()} {ep_m.group(2).split(':')[-1].split('/')[-1]}" if ep_m else "Request"
                entries.append({"time": ts, "thread": thread, "action": act, "acc": acc, "tokens": "-- / --"})
            elif "[TOKENS]" in line_str:
                acc_m = re.search(r"\[([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\]", line_str)
                s_m = re.search(r"Sent:\s*([^\s|]+)", line_str)
                r_m = re.search(r"Recv:\s*([^\s|]+)", line_str)
                c_m = re.search(r"Cached:\s*([^\s|]+)", line_str)
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
                    entries.append({"time": ts, "thread": "MAIN", "action": "Tokens Recorded", "acc": acc or "--", "tokens": token_str})
            elif "[AUTH-" in line_str:
                action = "Refresh Token" if "AUTH-REFRESH" in line_str else ("Save Token" if "AUTH-PERSIST" in line_str else "Auth Action")
                acc_m = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", line_str)
                acc = acc_m.group(1) if acc_m else "--"
                entries.append({"time": ts, "thread": "MAIN", "action": action, "acc": acc, "tokens": "--"})
            elif "[CLIENT-ABORT]" in line_str:
                acc_m = re.search(r"\[([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\]", line_str)
                acc = acc_m.group(1) if acc_m else "--"
                entries.append({"time": ts, "thread": "MAIN", "action": "Client Abort", "acc": acc, "tokens": "--"})
            elif "[UPSTREAM-ERR]" in line_str or "[UPSTREAM-TIMEOUT]" in line_str:
                acc_m = re.search(r"\[([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\]", line_str)
                acc = acc_m.group(1) if acc_m else "--"
                action = "Timeout (45s)" if "TIMEOUT" in line_str else "Upstream Error"
                entries.append({"time": ts, "thread": "MAIN", "action": action, "acc": acc, "tokens": "--"})
            elif "[ROTATOR-RESTORE]" in line_str:
                acc_m = re.search(r"\[([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\]", line_str)
                acc = acc_m.group(1) if acc_m else "--"
                entries.append({"time": ts, "thread": "MAIN", "action": "Rotator Restore", "acc": acc, "tokens": "--"})

        self._entries = entries[-MAX_LOGS:]
        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(0)
        query = self.txt_search.text().strip().lower()

        for e in self._entries:
            row_vals = [e["time"], e["thread"], e["action"], e["acc"], e["tokens"]]
            if query and not any(query in v.lower() for v in row_vals):
                continue

            r = self.table.rowCount()
            self.table.insertRow(r)

            it_time = QTableWidgetItem(e["time"])
            it_time.setForeground(QColor("#a6adc8"))

            it_th = QTableWidgetItem(f"● {e['thread']}")
            it_th.setForeground(QColor("#cba6f7") if e["thread"] == "SUBAGENT" else QColor("#89b4fa"))

            it_act = QTableWidgetItem(e["action"])
            it_act.setForeground(QColor("#cdd6f4"))

            it_acc = QTableWidgetItem(e["acc"])
            it_acc.setForeground(QColor("#bac2de"))

            it_tok = QTableWidgetItem(e["tokens"])
            it_tok.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            it_tok.setForeground(QColor("#a6e3a1") if e["tokens"] not in ("-- / --", "--") else QColor("#6c7086"))

            self.table.setItem(r, 0, it_time)
            self.table.setItem(r, 1, it_th)
            self.table.setItem(r, 2, it_act)
            self.table.setItem(r, 3, it_acc)
            self.table.setItem(r, 4, it_tok)

        self.table.scrollToBottom()

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
            row_text = "\t".join(self.table.item(r, c).text() if self.table.item(r, c) else "" for c in range(5))
            rows.append(row_text)
        QApplication.clipboard().setText("\n".join(rows))

    def _on_clear_clicked(self):
        msg = tr("logs.clear_confirm") or "Bạn có chắc chắn muốn xóa toàn bộ lịch sử log không?"
        res = QMessageBox.question(self, tr("btn.clear_log"), msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            clear_log()
            self.load_logs()

    def retranslate_ui(self):
        self.txt_search.setPlaceholderText(tr("logs.search_placeholder") or "Tìm kiếm theo từ khóa...")
        self.btn_refresh.setText("↻ " + (tr("full_log.btn_refresh") or "Làm mới"))
        self.btn_open_file.setText(tr("logs.btn_open_file") or "Mở tệp Log")
        self.btn_copy.setText(tr("full_log.btn_copy") or "Sao chép")
        self.btn_clear.setText(tr("btn.clear_log") or "Xóa Log")
        self._setup_table_headers()
