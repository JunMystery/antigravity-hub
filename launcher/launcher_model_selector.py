# -*- coding: utf-8 -*-
"""
Widget tìm kiếm, query và chọn nhiều Model AI dựa trên danh sách tài khoản đã chọn.
Hiển thị indicator + tooltip chi tiết khi một model chưa được tất cả tài khoản hỗ trợ.
"""

from typing import Iterable, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from launcher_i18n import tr


class MultiModelSelector(QWidget):
    """Danh sách checkbox model theo tài khoản đã chọn kèm tìm kiếm và nút Query Model."""

    query_requested = pyqtSignal()

    def __init__(
        self,
        initial_patterns: Iterable[str] = (),
        saved_patterns: Iterable[str] = (),
        parent=None
    ):
        super().__init__(parent)
        self._checked_map = {}
        self._saved_patterns = []
        seen_saved = set()
        for raw in (initial_patterns or []):
            val = str(raw or "").strip()
            if val and val.lower() not in self._checked_map:
                self._checked_map[val.lower()] = val
        for raw in list(initial_patterns or []) + list(saved_patterns or []):
            val = str(raw or "").strip()
            if val and val.lower() not in seen_saved:
                seen_saved.add(val.lower())
                self._saved_patterns.append(val)

        self._selected_accounts = []
        self._scan_cache = {}
        self._is_querying = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.addWidget(QLabel(tr("model_rules.models_hint")))
        header.addStretch(1)
        self.btn_select_all = QPushButton(tr("model_rules.btn_select_all"))
        self.btn_select_all.setStyleSheet("padding: 2px 8px;")
        self.btn_select_all.clicked.connect(lambda: self.set_all_checked(True))
        self.btn_select_none = QPushButton(tr("model_rules.btn_select_none"))
        self.btn_select_none.setStyleSheet("padding: 2px 8px;")
        self.btn_select_none.clicked.connect(lambda: self.set_all_checked(False))
        header.addWidget(self.btn_select_all)
        header.addWidget(self.btn_select_none)
        layout.addLayout(header)

        toolbar = QHBoxLayout()
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText(tr("model_rules.search_placeholder"))
        self.edit_search.textChanged.connect(self._apply_filter)
        self.btn_query = QPushButton(tr("model_rules.btn_query_models"))
        self.btn_query.setStyleSheet("padding: 4px 10px;")
        self.btn_query.clicked.connect(self.query_requested.emit)
        toolbar.addWidget(self.edit_search, 1)
        toolbar.addWidget(self.btn_query)
        layout.addLayout(toolbar)

        self.lbl_empty = QLabel(tr("model_rules.select_account_first"))
        self.lbl_empty.setWordWrap(True)
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setStyleSheet("color: #a6adc8; padding: 14px;")
        layout.addWidget(self.lbl_empty, 1)

        self.list_models = QListWidget()
        self.list_models.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list_models, 1)

    def _on_item_changed(self, item: QListWidgetItem):
        pat = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not pat:
            return
        if item.checkState() == Qt.CheckState.Checked:
            self._checked_map[pat.lower()] = pat
        else:
            self._checked_map.pop(pat.lower(), None)

    def set_querying(self, querying: bool):
        self._is_querying = bool(querying)
        self.btn_query.setEnabled(not self._is_querying and bool(self._selected_accounts))
        self.btn_query.setText(
            tr("model_rules.querying_models") if self._is_querying else tr("model_rules.btn_query_models")
        )

    def _collect_candidate_models(self) -> List[str]:
        seen = set()
        candidates = []
        sources = list(self._checked_map.values()) + list(self._saved_patterns)
        for acc in self._selected_accounts:
            entry = self._scan_cache.get(str(acc.get("email") or "").lower()) or {}
            sources.extend(entry.get("models") or [])
        for raw in sources:
            val = str(raw or "").strip()
            if val and val.lower() not in seen:
                seen.add(val.lower())
                candidates.append(val)
        return sorted(candidates, key=str.lower)

    def refresh_models(self, selected_accounts: list, scan_cache: dict):
        self._selected_accounts = list(selected_accounts or [])
        self._scan_cache = dict(scan_cache or {})
        has_accounts = len(self._selected_accounts) > 0

        self.lbl_empty.setVisible(not has_accounts)
        self.list_models.setVisible(has_accounts)
        self.btn_select_all.setEnabled(has_accounts)
        self.btn_select_none.setEnabled(has_accounts)
        self.btn_query.setEnabled(has_accounts and not self._is_querying)

        self.list_models.blockSignals(True)
        try:
            self.list_models.clear()
            if not has_accounts:
                return

            acc_models_map = {
                str(acc.get("email") or "").lower(): {
                    str(m).lower() for m in (self._scan_cache[str(acc.get("email") or "").lower()].get("models") or [])
                }
                for acc in self._selected_accounts
                if str(acc.get("email") or "").lower() in self._scan_cache
            }

            total_accs = len(self._selected_accounts)
            for pat in self._collect_candidate_models():
                pat_key = pat.lower()
                supported, unsupported = [], []
                for acc in self._selected_accounts:
                    email = str(acc.get("email") or "")
                    key = email.lower()
                    if key not in acc_models_map:
                        continue
                    if pat_key in acc_models_map[key]:
                        supported.append(email)
                    else:
                        unsupported.append(email)

                item = QListWidgetItem()
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setData(Qt.ItemDataRole.UserRole, pat)
                item.setCheckState(Qt.CheckState.Checked if pat_key in self._checked_map else Qt.CheckState.Unchecked)
                if unsupported:
                    badge = tr("model_rules.model_partial_badge", missing=len(unsupported), total=total_accs)
                    item.setText(f"{pat}  {badge}")
                    item.setForeground(QColor("#f9e2af"))
                    item.setToolTip(tr(
                        "model_rules.model_unsupported_tip",
                        unsupported="\n".join(unsupported),
                        supported="\n".join(supported) or "-"
                    ))
                else:
                    item.setText(pat)
                    item.setToolTip(tr("model_rules.model_all_supported_tip", count=total_accs))
                self.list_models.addItem(item)
        finally:
            self.list_models.blockSignals(False)

        self._apply_filter()

    def _apply_filter(self):
        needle = self.edit_search.text().strip().lower()
        for idx in range(self.list_models.count()):
            item = self.list_models.item(idx)
            pat = str(item.data(Qt.ItemDataRole.UserRole) or "").lower()
            item.setHidden(bool(needle and needle not in pat))

    def set_all_checked(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for idx in range(self.list_models.count()):
            item = self.list_models.item(idx)
            if not item.isHidden():
                item.setCheckState(state)

    def get_selected_patterns(self) -> List[str]:
        if self.list_models.count() > 0:
            selected = []
            for idx in range(self.list_models.count()):
                item = self.list_models.item(idx)
                if item.checkState() == Qt.CheckState.Checked:
                    val = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
                    if val:
                        selected.append(val)
            return selected
        return list(self._checked_map.values())
