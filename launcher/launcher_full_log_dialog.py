# -*- coding: utf-8 -*-
"""
Hộp thoại xem Full Log không giới hạn (launcher_full_log_dialog.py).
Cung cấp bộ lọc tìm kiếm tức thì, làm mới và sao chép toàn bộ nội dung proxy.log.
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QPlainTextEdit, QLabel, QApplication
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer

from launcher_i18n import tr
from launcher_log_manager import get_log_path


class FullLogDialog(QDialog):
    """Hộp thoại độc lập xem toàn bộ tệp nhật ký proxy.log."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.full_log_title") or "Toàn bộ Nhật ký Hoạt động (Full Log)")
        self.resize(800, 560)
        self.setMinimumSize(600, 400)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Thanh công cụ: Tìm kiếm + Nút Làm mới + Nút Sao chép
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.txt_search = QLineEdit(self)
        self.txt_search.setPlaceholderText(tr("full_log.search_placeholder") or "Tìm kiếm trong log...")
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background-color: #181825; border: 1px solid #313244;
                border-radius: 6px; padding: 5px 10px; color: #cdd6f4;
            }
            QLineEdit:focus { border: 1px solid #89b4fa; }
        """)
        self.txt_search.textChanged.connect(self._filter_logs)
        toolbar.addWidget(self.txt_search, stretch=1)

        self.btn_refresh = QPushButton("↻ " + (tr("full_log.btn_refresh") or "Làm mới"), self)
        self.btn_refresh.setStyleSheet("background-color: #313244; border-radius: 6px; padding: 6px 12px;")
        self.btn_refresh.clicked.connect(self.load_logs)
        toolbar.addWidget(self.btn_refresh)

        self.btn_copy = QPushButton(tr("full_log.btn_copy") or "Sao chép", self)
        self.btn_copy.setStyleSheet("background-color: #313244; border-radius: 6px; padding: 6px 12px;")
        self.btn_copy.clicked.connect(self._copy_all)
        toolbar.addWidget(self.btn_copy)

        layout.addLayout(toolbar)

        # Vùng xem text log
        self.log_viewer = QPlainTextEdit(self)
        self.log_viewer.setReadOnly(True)
        mono_font = QFont("Monospace", 9)
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self.log_viewer.setFont(mono_font)
        self.log_viewer.setStyleSheet("""
            QPlainTextEdit {
                background-color: #11111b; border: 1px solid #313244;
                border-radius: 6px; padding: 8px; color: #cdd6f4; line-height: 1.4;
            }
        """)
        layout.addWidget(self.log_viewer, stretch=1)

        # Thanh trạng thái dưới đáy
        footer = QHBoxLayout()
        self.lbl_status = QLabel("", self)
        self.lbl_status.setStyleSheet("color: #a6adc8; font-size: 11px;")
        footer.addWidget(self.lbl_status)
        footer.addStretch()

        self.btn_close = QPushButton(tr("btn.cancel") or "Đóng", self)
        self.btn_close.setStyleSheet("background-color: #45475a; border-radius: 6px; padding: 6px 16px;")
        self.btn_close.clicked.connect(self.accept)
        footer.addWidget(self.btn_close)

        layout.addLayout(footer)

        self._all_lines = []
        self.load_logs()

    def load_logs(self):
        """Đọc toàn bộ file log và hiển thị lên trình xem."""
        log_path = get_log_path()
        if not os.path.exists(log_path):
            self.log_viewer.setPlainText("--- Chưa có nhật ký hoạt động nào ---")
            self.lbl_status.setText("0 dòng (0 KB)")
            return

        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                self._all_lines = f.readlines()
            sz_kb = round(os.path.getsize(log_path) / 1024, 1)
            self._filter_logs(self.txt_search.text())
            self.lbl_status.setText(f"Tổng: {len(self._all_lines)} dòng ({sz_kb} KB)")
        except Exception as e:
            self.log_viewer.setPlainText(f"Lỗi đọc file log: {str(e)}")

    def _filter_logs(self, query: str = ""):
        """Lọc các dòng log theo từ khóa tìm kiếm."""
        q = (query or "").strip().lower()
        if not q:
            display_text = "".join(self._all_lines)
        else:
            filtered = [line for line in self._all_lines if q in line.lower()]
            display_text = "".join(filtered)
        self.log_viewer.setPlainText(display_text)
        self.log_viewer.verticalScrollBar().setValue(self.log_viewer.verticalScrollBar().maximum())

    def _copy_all(self):
        """Sao chép nội dung log đang hiển thị vào clipboard."""
        text = self.log_viewer.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            orig_txt = self.btn_copy.text()
            self.btn_copy.setText(tr("full_log.copied") or "Đã sao chép!")
            QTimer.singleShot(2000, lambda: self.btn_copy.setText(orig_txt))
